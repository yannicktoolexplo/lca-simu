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

Ce résultat concerne le carnet figé sans les deux options complémentaires
décrites plus bas. Il reste conservé pour distinguer les interventions.

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

## Calendrier de travail et carnet initial hypothétique

La métadonnée optionnelle `manufacturing_work_calendar` décrit les jours
travaillés par usine. Exemple d'hypothèse connue au démarrage :

```json
{
  "schema_version": 1,
  "rows": [{
    "node_id": "M-1430",
    "working_weekdays": [0, 1, 2, 3, 4],
    "known_day": 0,
    "provenance": "Hypothèse lundi-vendredi ; calendrier industriel non mesuré"
  }]
}
```

Les jours sont numérotés de lundi 0 à dimanche 6. Cette règle contraint la
capacité planifiée et physique, y compris les ordres initiaux et les campagnes
déjà commencées. Un lot peut commencer vendredi, conserver son travail en cours
durant le week-end et reprendre lundi. La marge `tau_process` reste calendaire :
elle ne devient pas une exigence de travail continu. Les fermetures historiques
gardent leur règle antérieure sur l'intervalle de planification. Les calendriers
de contrôle, transport et sécurité restent séparés.

L'option `--production-frozen-opening-policy j0_net_plan_hypothesis_v1` nécessite
le carnet figé. Elle construit **une hypothèse d'engagements antérieurs au
démarrage**, pas une observation industrielle. Au soir de J0 seulement, le MRP
recalcule son plan sans la barrière d'admission initiale, après déduction des
stocks utilisables et des ordres natifs. Les lots dont le lancement calculé
est compris entre J1 inclus et la fin de l'horizon figé exclue sont engagés aux
dates et quantités calculées. Les autres propositions restent révisables.

L'enregistrement n'ajoute aucun stock, aucune consommation ni travail physique.
Le lancement reste soumis aux matières, à la capacité et aux contrôles habituels.
Un second chargement du carnet est refusé. Les événements
`initial_hypothesis_adopted` et l'origine `hypothesized_initial_plan` distinguent
ces engagements des ordres industriels observés ; `frozen_production_initial_plan.json`
conserve les propositions nettes et leurs engagements adoptés. Les prévisions et
leurs replis documentés restent soumis à la connaissance disponible à J0.

Ces deux options sont désactivées par défaut. Le protocole compare séparément
le calendrier actuel, les jours travaillés seuls, puis les jours travaillés avec
le complément initial. Le but est d'évaluer couverture des besoins, retards et
stocks sous ressources déclarées ; une meilleure proximité d'une courbe réelle
ne suffit pas à promouvoir une référence. Les preuves de cette comparaison sont
conservées dans
[`calendrier_carnet_20261117`](../../artifacts/testing/calendrier_carnet_20261117/protocol.json).

La contre-vérification de cette première étape a identifié un prélèvement de
107 801 étuis pour un lot de 107 800 PF : les arrondis étaient répétés à chaque
journée de travail. Les avancements fractionnaires étaient, eux, conformes au
contrat existant ; ce sont les stocks, composants prélevés et PF libérés qui
doivent être entiers. Le refus de vérification initial et l'essai interrompu
restent conservés, sans être comptés comme réussites.

Une seconde étape compare les trois cas avec l'option commune
`--production-component-issue-policy batch_cumulative_v1`. Le prélèvement des
composants `UN` est désormais calculé sur le cumul du lot, en tenant compte des
quantités déjà incorporées, comme pour les ordres initiaux. Cette option ne
transforme pas l'avancement de travail en unités physiques finies. Le protocole
et le budget global, incluant les tentatives antérieures, sont conservés dans
[`calendrier_carnet_corrige_20261117`](../../artifacts/testing/calendrier_carnet_corrige_20261117/protocol.json).

Les sources de Muret ne changent pas de sens : la colonne « Sorties » du
classeur agrégé contient des mouvements signés nets. Elle ne suffit pas à
mesurer les expéditions brutes vers les clients. Le rapprochement au réel
conserve les semaines inconnues et les photos de stock aux dates communes.

### Pourquoi cinq jours travaillés font avancer la production

La comparaison des plans connus au 1er janvier donne les mêmes 15 lots de
107 800 unités dans les deux cas. À la cadence hypothétique de 7 700 unités
par jour, ils nécessitent 210 jours de travail. Après la zone figée, le
calendrier lundi–vendredi n'offre que 203 jours entre J56 et J338. Le placement
à capacité finie anticipe donc les premiers lots pour limiter les retards de
la fin de séquence ; il ne supprime pas toute insuffisance de capacité.

Le premier lot est prévu J103–J116 dans le témoin, contre J56–J75 avec cinq
jours travaillés, pour un même besoin à J116. Dans le second cas, il devient
ferme à J1. Dans le témoin, il subit 40 révisions, devient ferme à J63 et
commence effectivement à J118. Le calendrier et le gel interagissent donc :
l'avance ne s'explique pas uniquement par deux jours chômés par semaine.
Les preuves sont conservées dans
[`diagnostic_calendar`](../../artifacts/testing/calendrier_carnet_corrige_20261117/diagnostic_calendar/current_control_binding.json).

Ce mécanisme est vérifié dans le modèle, sans démonstration d'un calendrier
industriel optimal. La cadence et les jours alloués restent hypothétiques.
Des interruptions physiques liées au composant 042342 subsistent ; l'absence
d'événement de blocage dans le carnet ne suffit pas à les exclure.

Le stock disponible à Muret protège le service à court terme. Un gain éventuel
du carnet initial après J151 ne peut donc pas être écarté sur la seule absence
de gain client pendant ces 152 jours. Il faut distinguer charge future prévue,
exécution effectivement observée et accumulation de stock.

### Résultat des trois essais sur 152 jours

La [comparaison visuelle](../../resultats/calendrier_carnet_20261117.html)
conserve le même masque d'observation : 13 semaines de production estimée
pour 268967, 21 pour 268091 et 22 photos de stock par produit. Les semaines
absentes restent inconnues. A est le témoin avec prélèvements corrigés ; B
ajoute cinq jours travaillés à 1430 ; C ajoute aussi le carnet initial net.

| 268967 — unités | A | B | C |
|---|---:|---:|---:|
| Écart cumulé au réel sur les 13 semaines connues | −271 601 | +35 915 | +36 400 |
| Erreur absolue moyenne par semaine | 26 584,54 | 29 319,62 | 31 726,15 |
| Erreur absolue moyenne du stock à Muret | 74 335,68 | 82 525,32 | 116 825,32 |
| Produits finis utilisables à l'usine sur 152 jours | 107 800 | 431 200 | 539 000 |
| Fabrication en cours finale, équivalent unités | 77 000 | 61 600 | 0 |
| Stock physique final à Muret, contrôle inclus | 586 253 | 909 653 | 1 017 453 |
| Quantités demandées et servies dans la fenêtre | 623 081 | 623 081 | 623 081 |

**Le cumul se rapproche du réel, mais les écarts hebdomadaires et les écarts
de stock augmentent. Aucun des deux candidats ne remplace le témoin.** C
supprime les cinq retards du plan machine initial : la dernière disponibilité
prévue passe de J349 à J338, à quantité identique. Il ajoute toutefois
107 800 unités à Muret et 4 743 200 unités·jours de stock par rapport à B,
sans gain de volume client ni réduction de l'attente sur les cinq mois.
Ce résultat n'établit ni un bénéfice annuel ni l'inutilité d'un vrai carnet
industriel initial ; le carnet expérimenté reste hypothétique.

268091 reste inchangé : 3 097 715 unités fabriquées et devenues utilisables,
dont 1 945 715 issues des ordres initiaux. Sur ses semaines documentées,
l'erreur hebdomadaire moyenne est de 82 128,33 unités ; l'erreur moyenne de
stock est de 292 144,86 unités. Ce surplus persistant reste à traiter dans
une investigation distincte.

Les demandes en attente cumulées sont identiques entre variantes. Elles
incluent le transport normal : elles ne constituent pas une mesure de retard
par rapport à une date promise au client. Les coûts connus restent des
sous-totaux ; les produits finis de Muret ne sont pas valorisés dans ce calcul.

La correction des arrondis élimine la consommation supplémentaire liée au
découpage du travail en journées. Dans C, 39 lots terminés et 122 couples
lot/composant dénombrable ferment exactement. Une limite numérique intermédiaire
à J124 demeure documentée : l'avancement continu dépasse la borne décimale
source d'environ 4,6 × 10⁻¹² unité équivalente, moins qu'un dernier chiffre
représentable à cette échelle. Le contrat binaire passe ; un plafond décimal
exact à chaque étape n'est pas certifié. Aucune tolérance d'une unité physique
n'a été ajoutée à l'oracle.

Les [preuves finales](../../artifacts/testing/calendrier_carnet_corrige_20261117/final_manifest.json)
rassemblent 93 tests ciblés réussis, trois simulations finales de 152 jours,
leurs qualifications, les oracles indépendants et les limites. Les deux
simulations arrêtées et le premier lanceur d'analyse sans code retour restent
conservés, sans être comptés comme réussites. Le contrôle documentaire global
reste en échec sur les cinq registres antérieurement désynchronisés ; navigateur
et tests d'altération de fichiers n'ont pas été exécutés. La référence active
et les anciennes comparaisons HTML sont préservées.

La prochaine question discriminante est le compromis imposé par le placement
à capacité finie : quelle anticipation est réellement nécessaire pour respecter
les engagements, et quelle part provient de prévisions encore révisables ?
La vérifier sur des petits cas de calendrier et sur les versions MRP datées
précède toute nouvelle simulation longue ou modification des sécurités sources.
