# Écarts de calendrier et de disponibilité en 2025

Deux simulations de **96 jours**, du 1er janvier au 6 avril, ont été
comparées au même début de l’essai qualifié de 152 jours. Les demandes,
les sécurités, les stocks initiaux et les requêtes de prélèvements
historiques sont identiques. Chaque variante est comparée à ce témoin
sur les mêmes relevés de stock. Les tests de transferts et de versions
MRP couvrent aussi des périodes plus longues en lecture seule.
[Courbes interactives](../../resultats/resolution_ecarts_2025_20261121.html)

## Résultat des deux simulations courtes

| Intervention | Article et site | Écart absolu moyen du stock physique, témoin → essai |
| --- | --- | ---: |
| Rejeu des réceptions d’achats une fois leur semaine close | 021081, D1450 | 393 690 → **77 077 kg** |
| Même essai | 042342, D1430 | 21 969 629 → **6 154 748 unités** |
| Même essai, propagation à l’aval | 268967, D1920 | 28 106 → **35 471 unités** |
| Possibilité de transférer les lots d’ouverture dès leur fin physique, avec le contrôle de D1920 conservé | 268091, D1920 | 184 398 → **214 738 unités** |

Sur **30 couples** comparables, le rejeu des achats rapproche six
stocks, en éloigne quatre et laisse vingt écarts moyens identiques.
Le second essai change seulement l’écart moyen du 268091 à D1920. Il
le réduit de 117 145 à 70 867 unités en janvier–février et le porte
de 274 069 à 406 567 en mars–avril. Les nouvelles fabrications
du 268091 restent identiques en date et quantité. Le délai atelier
fait donc bien partie du calendrier modélisé, et sa seule suppression
déplace le surplus sans le résorber.

Dans les deux essais, les volumes livrés simulés sont identiques jour
par jour pour les deux PF. La demande cumulée est de 902 858 unités
pour 268091 et de 435 397 pour 268967, avec un retard simulé identique
en cours de période et entièrement résorbé à la clôture. Il s’agit
du service simulé. Les mouvements nets de D1920 ne donnent pas les
expéditions clientes brutes réelles.
[Comparaison achats](../../artifacts/testing/resolution_ecarts_2025_20261121/native_receipts/comparison.json) · [Comparaison contrôle PF](../../artifacts/testing/resolution_ecarts_2025_20261121/native_pf_release/comparison.json)

## Achats, dissocier échéance, réception et utilisation

**042342.** L’entrée de 30 millions prévue pour la semaine du 13
janvier disparaît du MRP du 12 janvier. Le journal industriel
renseigne zéro réception pour cette semaine. Le témoin exécute le
carnet initial. Sur les 49 groupes article-site-semaine du carnet
effectivement représentés, **13** avaient un volume du carnet repris
dans une première version et explicitement ramené à zéro par la
dernière version avant la semaine. Les **12** semaines observables ont
toutes zéro réception. La treizième demeure inconnue. Sur la période
ultérieure de mars–avril, le résultat se retrouve sur **7 cas sur 7**.
Le signal permet de rouvrir la date promise en conservant la quantité
au carnet. Une entrée maintenue au MRP reste une confirmation faible.
Dans **15 cas sur 36**, elle est positive et l’entrée réelle est nulle.

**021081.** Les six premières échéances s’accumulent jusqu’à
620 000 kg au plan avant le premier rattrapage enregistré. Le retard
est visible sans retrait de l’entrée au MRP. Le 16 février, le MRP
place 333 930 kg dans la semaine courante et 619 640 kg plus tard.
Le total coïncide avec la photo réelle suivante. Le témoin affiche
999 060 kg utilisables et 620 000 retenus. Le rejeu enlève une part de
l’excès physique. La consommation en D1450 reste identique pour ce
composant sur les 96 jours.

Dans le rejeu, les réceptions hebdomadaires positives sont révélées le
lundi suivant et affectées par ordre des échéances aux achats
d’ouverture. Cette convention préserve les volumes et leur date de
connaissance dans l’essai. L’identité réelle des commandes et le jour
exact de la réception restent inconnus. Le moteur applique le délai
de réception du carnet à chaque fragment.
[Test sur les versions MRP](../../artifacts/testing/resolution_ecarts_2025_20261121/opening_signal_holdout.json) · [Entrées du rejeu](../../artifacts/testing/resolution_ecarts_2025_20261121/native_receipts/preflight.json)

**La libération explique la propagation de 042342.** Les 23 millions
reçus la semaine du 17 mars restent en contrôle jusqu’au 11 avril dans
le rejeu. Le 25 mars, il manque du 042342 utilisable pendant le travail
du premier lot 268967. Aucun achèvement avant le 6 avril, alors que
le témoin termine **107 800 PF le 28 mars**. D1920 garde au moins
**666 137 unités utilisables** dans les deux cas. Les 107 800 unités
reçues par le témoin seraient encore retenues à la clôture.

Le bilan industriel se ferme à **21,25 millions d’unités** le 24 mars.
Le MRP du 23 mars range **19,75 millions** en semaine courante. À
périmètre identique, ce stock courant comprend au minimum **13 millions**
de l’entrée de la semaine, même si tout le stock antérieur y figure
encore. La perte de fabrication simulée dépend donc du délai appliqué
dans cet essai. La date réelle de libération par lot reste inconnue.
[Oracle indépendant des réceptions et de la libération](../../artifacts/testing/resolution_ecarts_2025_20261121/oracle/march_042342_discriminating_oracle.json)

## 268091, écart de calendrier et écart de quantités

Le témoin applique une attente de dix jours ouvrés en usine sur le
carnet d’ouverture, puis dix jours à D1920 après transfert. Les vingt
positions d’ouverture d’D1810 représentent 1 945 715 unités, suivies
une fois jusqu’au dépôt dans les journaux. Les sources donnent les
dates prévues en usine ainsi que la règle générale de contrôle PF au
dépôt. Le statut réel des lots à l’expédition reste inconnu. L’essai
à un seul contrôle n’a pas réduit le surplus sur toute la fenêtre.

La courbe de « production » prenait la date où le lot devenait
utilisable. Sur la semaine du 17 février, elle indiquait zéro là où
le registre compte **294 895 fins physiques** et les étuis observés
285 600 unités équivalentes. Sur 21 semaines documentées,
l’erreur moyenne du 268091 face aux retraits d’étuis passe de
**129 040 à 88 985 unités par semaine** en prenant les fins physiques.
Le cumul simulé est identique à cette coupure. Les deux dates donnent
la même série pour 268967 sur l’essai. À D1450, les fins physiques
dépassent les libérations de **1 200 kg pour 693055** et **9 600 kg pour
773474** à la clôture des 152 jours. Les retraits d’emballages restent
un indicateur indirect d’activité.

La semaine du 3 mars garde un écart de quantité même avec le bon
jalon. Les retraits d’étuis équivalent à **51 600 PF**. Le scénario
finit **60 695 PF** d’ouverture et **259 200 PF** issus de huit autres
ordres, dont 249 205 atteignent D1920 avant le relevé du 10 mars.
Le changement de prévision connu le 27 janvier ramène les huit ordres
au même premier jour de lancement autorisé après le gel. Ils étaient
prévus le 24 février. Dans le scénario, le 001893 est alors à zéro
utilisable malgré 95 680 kg en contrôle. La libération de 71 760 kg
le 6 mars débloque les premiers lancements. Le 338928 limite le dernier
groupe. Le MRP industriel du 23 février porte déjà du 001893 dans la
semaine courante et les mouvements enregistrent des prélèvements,
sans détail sur leur affectation aux OF. Lors des cinq revues qui
suivent le gel, les 40 examens de ces ordres refusent leur réduction
pour un motif de couverture datée.
[Oracle des fins physiques](../../artifacts/testing/resolution_ecarts_2025_20261121/oracle/production_markers.json) · [Contrôle des libérations usine](../../artifacts/testing/resolution_ecarts_2025_20261121/oracle/reported_availability.json) · [Journal des ordres de mars](../../artifacts/testing/resolution_ecarts_2025_20261121/march_and_packaging.json)

## Transferts et prochaine règle à tester

- **773474 vers D1430.** Déplacer les mêmes 6 400 kg vers la semaine
  observée fait passer l’écart de 3 518 à 872 kg sur six photos, à
  flux constants. Le stock utilisable du receveur permet les mêmes
  prélèvements. L’arrivée était déjà visible au MRP au début de janvier.
- **693055 vers D1810.** Regrouper 590 et 600 kg dans la semaine
  observée fait passer l’écart de 238 à 0 kg sur cinq photos à D1810.
  Selon le jour de réception, il peut manquer jusqu’à 103 kg après
  application du contrôle existant. Le résultat de stock physique
  est identique sur toutes ces dates à l’intérieur de la semaine.
- **Contrôle sur les deux routes.** Les 37 semaines avec entrée
  positive donnent exactement la même quantité en sortie de D1450
  et entrée à destination. Les semaines ne permettent pas de choisir
  entre un trajet court et des écritures synchronisées. Sur le reste
  de 2025, 10 des 27 semaines positives au MRP de 773474 ne donnent
  aucune entrée observée. Un signal du plan doit être rapproché de
  l’origine et de l’engagement avant de devenir une réception ferme.
- **Emballage 338929.** Passer à 14 jours pour les onze nouveaux
  achats arrivés après 42 jours fait passer l’écart de 195 087 à
  595 843 unités sur 21 photos, à flux constants. Une voie rapide
  conditionnée à un stock prêt chez le fournisseur reste une autre
  hypothèse. Le volume prêt et sa disponibilité réelle sont inconnus.

La priorité suivante est de tester **la disponibilité du stock déjà
présent**, en utilisant la dernière version connue et en exigeant le
rapprochement du périmètre. Sur **1 615 comparaisons** portant sur
32 couples, les postes de stock courant et futur du MRP se réconcilient
exactement avec **1 131 photos**. **241** de ces photos montrent du stock
reporté dans le plan. Pour le 021081, **50 photos sur 52** se réconcilient.
Pour le 001893 à D1810, **45 sur 52**, dont 28 avec un stock reporté.
Pour le 042342, le différentiel récurrent de 1,5 million avec la photo
doit rester explicite. L’objectif est de tester une règle commune qui
sépare quantité présente, état d’utilisation et date de confirmation.
[Transferts avec conservation des volumes](../../artifacts/testing/resolution_ecarts_2025_20261121/transfer_intervals.json) · [Rapprochement des états du stock](../../artifacts/testing/resolution_ecarts_2025_20261121/source_stock_state_coverage.json)

## Vérification et décision

Les deux essais natifs de 96 jours passent les contrôles indépendants
de qualification. Sept tests ciblés vérifient la politique de réceptions
d’ouverture. Deux autres vérifient la séparation des jalons de
production. Chromium a vérifié les courbes et leurs détails cliquables
hors ligne sur ordinateur et mobile. Les deux essais restent des variantes. La comparaison
n’établit aucune règle unique qui améliore le modèle sur toute la
chaîne. La vérification documentaire générale signale des contrats
générés déjà désynchronisés sur le commit initial.
[Manifeste](../../artifacts/testing/resolution_ecarts_2025_20261121/final_manifest.json)
