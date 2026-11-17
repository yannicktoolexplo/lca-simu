# Programme de fabrication figé : 1810 et 1430

Les durées ont été confirmées par l'utilisateur le 17 novembre 2026 :
**28 jours à 1810, 56 jours à 1430**. La prévision connue pilote toujours les
besoins. Le bilan hebdomadaire consomme cette prévision avec la demande réelle
devenue connue après clôture ; il ne réécrit pas les ordres déjà figés.

## Contrat de la variante

L'option `--production-frozen-horizon-policy industrial_frozen_order_book_v1`
active un carnet persistant pour les fabrications des deux usines. Le défaut
reste inchangé. Le parcours expérimental exige la planification datée, le
programme de plusieurs jours avec capacité finie, les engagements au lancement
physique et `weekly_close_next_day_v1`. Il est limité à l'année source, sans
préchauffage. Les autres sites conservent leur politique.

À chaque jour de décision, les ordres du carnet précédent dont le lancement
entre dans la période figée sont protégés **avant** le nouveau calcul. Date
prévue et quantité restent identiques ; les ordres hors de cette période
restent révisables. Un nouvel ordre ne peut pas être ajouté dans la période
figée. Un ordre arrivé à échéance peut démarrer, sous réserve des matières et
de la capacité physiques. Son attente ne crée ni un deuxième ordre ni un
nouveau crédit de stock. Les ordres initiaux continuent dans leur parcours
existant ; ils ne sont pas réimportés dans le nouveau carnet.

**Convention d'essai, à distinguer de la durée confirmée :** le gel porte sur
la date de lancement, avec une borne de fin exclue. Au jour 10, pour une usine
figée sur 28 jours, un nouveau lancement au jour 37 est refusé ; le jour 38
est admissible. Les exceptions industrielles et une éventuelle ancre de fin
de production ne sont pas documentées.

Les engagements figés couvrent une seule fois les besoins de produit fini,
réservent une charge et émettent des besoins de composants. Une réservation
n'est ni une consommation de matière ni une réception physique. Au lancement,
le suivi natif de campagne et des lots prend le relais sans second engagement.
Les retards doivent conserver la date gelée dans le journal, séparément de
la date de travail réellement exécuté.

Pour un ordre non démarré en retard, la projection de disponibilité décale
la durée calendaire prévue initialement ; elle ne promet pas automatiquement
la réception dès le lendemain. Cette estimation ne garantit ni les matières
ni le calendrier futur. La réservation de composants reste un besoin daté de
planification : elle ne constitue pas un blocage physique de tous les usages
partagés. Les journaux conservent ces limites.

Le premier travail physique est contrôlé localement pour les ordres de ce
carnet, y compris lorsque le témoin n'active pas l'ancienne option globale
d'engagement au premier travail. Le journal de révision natif garde sa
convention antérieure ; il ne doit pas être présenté comme un taux de révision
du nouveau carnet. Les événements dédiés sont nécessaires à ce calcul.

## Interprétation de la comparaison

Le nouveau carnet remplace, dans son périmètre, l'autorisation expérimentale
fondée sur les budgets de composants de la semaine courante. La comparaison
porte sur **cette logique d'engagement complète** ; elle ne mesure pas le seul
effet isolé des nombres 28 et 56. Les anciennes options de sélection d'un lot
déjà dû ou de budget non contraignant ne sont pas ajoutées silencieusement.

Cette substitution retire aussi le contrôle spécifique de l'ancien pilote
qui exigeait les composants de **tout le lot**, après protection des ordres
initiaux, avant son lancement. Le nouveau carnet conserve les besoins de
composants dans le MRP et le contrôle physique natif de chaque travail exécuté,
mais peut démarrer un travail partiel. Une réservation datée dans le plan
ne garantit donc pas une mise à l'écart physique des composants pour tous les
ordres futurs. Cette différence fait partie de l'intervention à évaluer ; les
dates et quantités des ordres initiaux doivent être rapprochées séparément.

Le filtre de lancement le week-end propre à l'ancien pilote hebdomadaire
disparaît également. Les fermetures d'usine déclarées restent appliquées par
la capacité physique ; ce graphe ne déclare pas de fermeture hebdomadaire de
ces usines. Le calendrier réel des jours travaillés reste donc inconnu.
Les jours de sécurité et de contrôle lundi–vendredi ne sont pas modifiés.

Le témoin reprend l'essai de demande connue après la semaine. Son regroupement
physique des demandes le lundi reste une convention expérimentale identique
dans les deux cas, pas une observation des commandes quotidiennes. Le carnet
initial industriel est incomplet, notamment pour 268967 : le premier plan
simulé utilise les informations disponibles, jamais les fabrications réelles
futures pour inventer des ordres initiaux.

## Résultat de l'essai du 1er janvier au 1er juin 2025

**Le carnet fonctionne, mais cette variante rapproche moins bien les courbes
du réel. Elle n'est pas promue en référence.** Le témoin est l'essai du
16 novembre utilisant la publication hebdomadaire de la demande, rejoué avec
le code final. Ses 54 CSV communs sont identiques à ceux conservés. Les
20 ordres initiaux, soit 1 945 715 unités, gardent leurs dates et quantités.

Les erreurs ci-dessous sont des moyennes d'écarts en unités, sans compensation
entre surplus et manque. La production est comparée sur les semaines où les
prélèvements d'étuis sont documentés ; le stock sur 22 photos communes.

| Indicateur | Témoin | Carnet figé |
|---|---:|---:|
| Erreur hebdomadaire de production, 268967 (13 semaines) | 11 323 | 26 585 |
| Erreur de stock à Muret, 268967 | 36 456 | 74 336 |
| Erreur hebdomadaire de production, 268091 (21 semaines) | 48 605 | 82 128 |
| Erreur de stock à Muret, 268091 | 143 374 | 292 145 |

![Production hebdomadaire comparée au réel](../../artifacts/testing/gel_programme_20261117/production_hebdomadaire.png)

Pour 268967, l'essai exécute 184 800 unités de travail sur les 152 jours :
107 800 sont terminées et 77 000 restent en cours. Sur les seules 13 semaines
documentées, il exécute 130 900 unités contre 402 500 estimées dans les données.
Ces deux périmètres ne doivent pas être confondus. Le premier lot démarre au
jour prévu 118, puis attend le composant 042342 pour finir au jour 141. Le
second, prévu au jour 137, démarre au jour 142. La pause est expliquée dans le
modèle par le stock utilisable nul pendant que 30 millions d'unités de ce
composant sont sous contrôle ; les autres usages qui l'ont consommé sont un
résidu reconstruit. **Aucune panne industrielle n'est identifiée.**

Pour 268091, la production passe de 2 392 115 à 3 097 715 unités : le surplus
de 705 600 se retrouve dans les stocks usine (+12 180), le transport vers Muret
(+86 400) et le stock de Muret (+607 020). Pour 268967, le recul de travail
de 138 600 unités se rapproche de +77 000 en cours, −107 800 en transport et
−107 800 à Muret. Les départs de Muret, les réceptions clients et les arriérés
simulés restent identiques chaque jour entre les deux cas. Les stocks absorbent
donc les différences de production sur cette fenêtre.

La suite utile est de séparer le gel des autres changements d'autorisation,
puis d'examiner la protection des composants d'une campagne engagée face aux
usages partagés. Le carnet initial industriel reste à compléter ; aucune
production réelle future ne doit servir à inventer des engagements initiaux.

## Preuves et portée

Le protocole, les oracles indépendants, les cas exécutables et les résultats
restent dans
[`gel_programme_20261117`](../../artifacts/testing/gel_programme_20261117/protocol.json).
L'[état final des contrôles](../../artifacts/testing/gel_programme_20261117/final_manifest.json)
recense 42 tests ciblés réussis, deux simulations finales de 152 jours,
leurs qualifications et la contre-vérification indépendante. Les contrôles
techniques passent ; ils ne certifient pas la calibration industrielle.
Le contrôle documentaire global reste en échec sur cinq registres déjà
désynchronisés. Aucun navigateur, aucune simulation sur plusieurs années ni test d'altération
de fichiers n'a été exécuté pour cette étude.
Les journaux natifs ajoutés sont `frozen_production_events.csv` et
`frozen_production_orders.json`. Ils distinguent création, révision, gel,
lancement et travail exécuté.

Les sources de Muret ne changent pas de sens : la colonne « Sorties » du
classeur agrégé contient des mouvements signés nets. Elle ne suffit pas à
mesurer les expéditions brutes vers les clients. Le rapprochement au réel
conserve les semaines inconnues et les photos de stock aux dates communes.
