# Prévision et demande connue après la semaine

Étude du 16 novembre 2026, fondée sur le témoin conservé au commit
`4f7c505ace4b39cd6cc427052753eb1664b5e06b`. Les comparaisons précédentes
restent conservées. Le nouveau mode est une option expérimentale ; il ne
remplace pas la référence active.

## Ce que les fichiers permettent d'affirmer

`Flow_Data_Customer_Demand.xlsx` sépare deux tables :

| Table | Information | Date |
|---|---|---|
| `Projection` | `Forecasted Demand`, prévision de demande | semaine de version et semaine visée |
| `Historique` | `Actual Demand`, quantité historique | premier jour de la semaine concernée |

La demande historique est interprétée comme la **quantité demandée par les
clients**, conformément à la précision de l'utilisateur. Le fichier ne contient
ni numéro de commande, ni date de livraison, ni statut permettant de confirmer
des ventes effectivement livrées. Il ne constitue pas un journal de fabrication.
La production réelle comparée provient d'une autre source : les retraits
d'étuis enregistrés dans les mouvements d'inventaire. C'est un indicateur
indirect de production, pas un journal des ordres terminés.

La date de connaissance en fin de semaine vient de la précision de
l'utilisateur ; elle n'est pas horodatée dans le classeur. Le lundi suivant
est la première décision quotidienne de simulation utilisant le total clôturé.
Le classeur `demand_PF.xlsx` ne fournit pas une comparaison indépendante :
ses colonnes de demande prévisionnelle et réelle sont identiques sur 104 lignes.

## Défaut et correction testée

Le témoin répartissait le total historique de la semaine dès le premier jour.
Il utilisait ces demandes reconstruites dans le besoin du jour, les expéditions,
le stock et les reliquats. La revue hebdomadaire du budget mensuel ne suffisait
donc pas à empêcher cette connaissance anticipée : sur 304 lignes examinées,
260 exposaient une valeur avant la clôture, dont 242 valeurs positives.

Le mode `weekly_close_next_day_v1` publie le total le lundi suivant et conserve
la prévision pour le besoin du jour. Le reliquat mensuel consomme seulement les
demandes déjà publiées, attribuées au mois de leur date d'effet. La règle et ses
formules figurent dans [REGLES_MRP.md](REGLES_MRP.md).

Les dates des commandes individuelles étant absentes, leur exécution physique
est aussi regroupée le lundi. **Ce changement affecte les stocks et le service :
la comparaison n'isole pas le seul effet d'information.** Les lots, capacités,
stocks initiaux, ordres engagés et classeurs sources sont conservés.

Exemples vérifiés : 1 000 prévus moins 300 demandés donnent 700 à répartir ;
sur un mois de quatre semaines, cela donne 700/3 par semaine restante. En
janvier 2025, une revue le 13 janvier laisse réellement 19 jours. Une demande
de 301 du 27 janvier au 2 février se répartit en 215 pour janvier et 86 pour
février, même lorsqu'elle n'est publiée que le 3 février.

## Périmètre et preuves

Le protocole impose un oracle en mémoire, une activation native de 14 jours,
puis deux essais de 152 jours, du 1er janvier au 1er juin 2025 inclus. La
production est rapprochée sur les mêmes semaines complètes documentées :
21 pour 268091, 13 pour 268967. Les stocks sont rapprochés sur les mêmes
22 photographies par produit, à la clôture simulée de la veille. Une semaine
absente reste inconnue ; aucune interpolation n'entre dans le score.

La demande du 26 mai au 1er juin devient connue le 2 juin, après l'horizon :
77 899 unités de 268091 et zéro de 268967 restent non publiés. Ce zéro est une
observation ultérieure, pas une information disponible pendant le calcul.
Les quantités non publiées sont conservées séparément et ne sont pas présentées
comme une réduction des ruptures.

- [Protocole local](../artifacts/testing/demande_connue_20261116/protocol.json).
- [Diagnostic du témoin](../artifacts/testing/demande_connue_20261116/engine_diagnosis/diagnostic.json).
- [Tests ciblés : 62 réussites](../artifacts/testing/demande_connue_20261116/tests/tests-6fcc50c979ec49608064b5693cc4bd64/manifest.json).
- [Contre-vérification avant calcul](../artifacts/testing/demande_connue_20261116/validator/pre_run_review.json).
- [Activation native : 521 contrôles indépendants](../artifacts/testing/demande_connue_20261116/validator/activation_review.json).
- [Qualification physique du calcul court](../artifacts/testing/demande_connue_20261116/qualification/activation/qualify-bd82ad1901c04642b586150117c09d34/manifest.json).

## Résultats des deux essais de 152 jours

Le [rapport cliquable](../resultats/demande_connue_20261116.html) présente
production hebdomadaire, cumul documenté, demande et stocks. Une semaine
sélectionnée ouvre les quantités quotidiennes et leurs cellules source.

| Produit / mesure | Témoin conservé | Réel connu après la semaine |
|---|---:|---:|
| 268091 : volume sur 21 semaines observées, réel 2 409 100 | 2 579 315 (+7,07 %) | 2 392 115 (−0,71 %) |
| 268091 : erreur moyenne de production par semaine | 44 147 | 48 605 |
| 268091 : erreur moyenne de stock sur 22 photos | 184 843 | 143 374 |
| 268967 : volume sur 13 semaines observées, réel 402 500 | 323 400 (−19,65 %) | 323 400 (−19,65 %) |
| 268967 : erreur moyenne de production par semaine | 11 323 | 11 323 |
| 268967 : erreur moyenne de stock sur 22 photos | 19 737 | 36 456 |

Quantités en unités de produits finis. Les erreurs moyennes additionnent les
écarts sans tenir compte de leur signe, puis divisent par le nombre d'observations.
Ce ne sont pas des résultats annuels. Pour 268091, le biais moyen signé des stocks
augmente néanmoins de +2,62 % à +6,84 % : la diminution de l'erreur moyenne ne
signifie pas que tous les indicateurs de stock s'améliorent.

Le nouveau témoin reproduit **exactement les 53 CSV** du précédent témoin.
Les 20 ordres initiaux, soit 1 945 715 unités de 268091, gardent leurs quantités
et leurs dates. Les nouvelles fabrications de 268091 passent de 633 600 à
446 400 unités, toujours sur neuf lancements. La baisse de fabrication est de
187 200 unités ; le stock final ne baisse que de 109 301, car 77 899 unités de
demande ne sont pas encore publiées et donc pas expédiées. L'identité est :
−187 200 + 77 899 = −109 301. Aucun gain de service réel n'en est déduit.

Pour 268967, les trois campagnes de 107 800 unités subsistent. Les besoins
calculés changent, mais la première et la troisième fabrication gardent leurs
dates ; la deuxième est décalée d'un jour, du 14 au 15 avril. Les dates de
lancement proposées par le calcul MRP changent davantage que les lancements
effectivement autorisés. La correction de demande ne résout donc pas le
calendrier des campagnes. Les 107 800 unités encore en transport vers Muret
à la fin restent comptées séparément du stock reçu.

Sur chacune des 22 photos de 268967, le supplément de stock du candidat est
exactement égal à la demande de la semaine clôturée, encore non publiée dans
ce scénario. Les réceptions cumulées à Muret sont identiques à ces dates ; les
expéditions sont décalées. La somme des suppléments vaut 623 081 unités sur les
22 photos, soit 28 322 unités en moyenne. La dégradation de ce score de stock
est donc expliquée par le regroupement physique des demandes le lundi, sans
démontrer une nouvelle erreur de fabrication. Les trajectoires entre photos
peuvent différer, notamment pour le deuxième lot décalé d'un jour.
Voir les [22 rapprochements indépendants](../artifacts/testing/demande_connue_20261116/validator/stock_timing_review.json).

**Décision : conserver la correction comme option vérifiée, sans promouvoir
ce scénario agrégé en référence industrielle.** Elle retire une anticipation
indue de l'historique, mais ne rapproche pas la production prioritaire 268967
et dégrade son rapprochement de stock. Les effets du regroupement physique
du lundi empêchent d'attribuer les différences au seul changement d'information.

La prochaine investigation doit expliquer les trois campagnes autorisées et
leur avance sur les dates de besoin, puis rapprocher le périmètre des prévisions
avec celui de la demande historique. Il faut des dates de commandes individuelles
pour dissocier la connaissance de la demande de son exécution physique ; une
nouvelle panne ajustée à la courbe ne comblerait pas ce manque.

- [Revue indépendante finale : 5 174 contrôles](../artifacts/testing/demande_connue_20261116/validator/final152_review.json).
- [Qualification du témoin](../artifacts/testing/demande_connue_20261116/qualification/control/qualify-c5b1716635124b15988fcb23dc381d1d/manifest.json).
- [Qualification du candidat](../artifacts/testing/demande_connue_20261116/qualification/weekly_publication/qualify-c17f177519624b4ab36a9856f385688b/manifest.json).
- [Contrôles numériques et statiques du HTML : 462](../artifacts/testing/demande_connue_20261116/report/static_numeric_review.json).
- [Contre-vérification du rapport : 7 452 contrôles](../artifacts/testing/demande_connue_20261116/validator/final_display_review.json).

La syntaxe JavaScript a été compilée dans V8, sans exécuter le DOM. Aucun
navigateur ni contrôle visuel automatisé n'a été exécuté, conformément à la
restriction conservée pour cette étude. Les invariants de bilan ne certifient
ni la qualité des prévisions sources, ni la causalité industrielle.

Le [contrôle documentaire global](../artifacts/testing/demande_connue_20261116/docs_final/docs-fe5da674038140a3a35f1d7978c4c6cd/manifest.json)
reste refusé sur les cinq domaines déjà signalés : risques et lots, comparaison
des scénarios, vérification d'exécution, traçabilité matière et sémantique
auditée. Leurs empreintes et documents générés nécessitent une revue distincte ;
ce refus n'est pas compté comme une réussite.

## Prévisions à expliquer

Le budget reconstruit au début d'avril pour 268967 vaut 165 111 unités, contre
68 688 historiquement demandées dans le mois ; en mai, 165 931 contre 114 160.
Pour 268091, janvier donne 1 079 096 contre 231 419. Les demandes mensuelles
sont reconstruites par répartition entière des totaux hebdomadaires ; les budgets
mensuels résultent des versions prévisionnelles connues à l'ouverture du mois.
Janvier comporte en outre cinq jours sans période directe, couverts par le
repli déclaré vers une prévision connue.

Ces écarts ne prouvent pas que les données sont erronées. Ils peuvent traduire
une erreur de prévision, un périmètre différent ou une convention source à
clarifier. Les valeurs ne sont pas corrigées pour obtenir le résultat attendu.
Voir l'[audit mensuel sourcé](../artifacts/testing/demande_connue_20261116/forecast_source_audit.json).

## Reproduire l'essai local

Le graphe est celui du témoin conservé, référencé avec son empreinte dans
`artifacts/testing/demande_connue_20261116/preparation.json`. Le lanceur natif
reste `etudecas.simulation.current_reference.run_engine` ; le candidat ajoute :

```text
--forecast-consumption-policy calendar_month_weekly_review_v1
--customer-demand-knowledge-policy weekly_close_next_day_v1
```

Les cas, arguments complets, gel des sources et budgets sont conservés dans le
dossier de preuves. Le mode est borné à 365 jours sans préchauffage et exige
l'historique client et la revue mensuelle hebdomadaire. Le comportement par
défaut `reconstructed_daily_v1` reste disponible pour reproduire les anciens
résultats. Aucun scénario annuel, aléa ou Monte Carlo supplémentaire n'est
justifié par cette seule correction de connaissance.
