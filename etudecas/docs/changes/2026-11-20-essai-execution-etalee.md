# Essai d'un lot exécuté sur plusieurs jours ouvrés

L'enquête D1920–usine indique que les prélèvements de composants et les
arrivées au dépôt suivent des calendriers différents. Le moteur utilisé
pour l'essai d'engagement usine termine, lui, un lot entier dans la journée
en mode sans plafond. Un débit machine positif activerait une autre logique
qui réserve la capacité et séquence les ordres. Pour isoler la durée, cet
essai conserve l'ordre de 107 800 unités, son lancement du 17 mars et son
kit complet. Il répartit le travail sur 1, 5 ou 10 jours ouvrés.
[Origine de la question](2026-11-19-remontee-D1920-reel.md)

Le calcul court rejoue le travail et les stocks sur les 120 jours de
l'essai qualifié avec engagement. La même quantité de chaque composant
est réservée au lancement, puis prélevée par travail cumulé. Les huit
quantités finales sont conservées. Le lot entier quitte l'usine à la
fin du travail. Il arrive deux jours calendaires plus tard et devient
utilisable après 15 jours ouvrés de contrôle. Les autres flux restent
ceux du témoin. Le cas d'une journée reproduit exactement les dates,
les courbes et l'état quotidien de stock du témoin.

| Travail du lot | Fin de travail | Arrivée à D1920 | Disponible à D1920 | Écart moyen étuis sur 10 semaines | Écart moyen stock sur 17 photos |
| --- | --- | --- | --- | ---: | ---: |
| 1 jour, témoin | 17 mars | 19 mars | 9 avril | 28 955 | 36 964 |
| 5 jours ouvrés | 21 mars | 23 mars | 11 avril | 28 955 | 36 964 |
| 10 jours ouvrés | 28 mars | 30 mars | 18 avril | 18 175 | 32 172 |

Les indicateurs sont en unités physiques de produit fini ou équivalent
étuis. En dix jours, le lot consomme 53 900 étuis par semaine, pour
49 250 et 60 000 observés. L'écart hebdomadaire baisse de **37 %**.
Le cumul reste de **107 800 unités** pour **280 250 estimées sur
les semaines documentées jusqu'à fin avril**. L'amélioration du stock
provient entièrement de la photo du **24 mars**. Le témoin affiche
838 190 unités, l'essai dix jours 730 390 et la photo 743 556.
[Comparaison graphique](../../resultats/essai_execution_etalee_268967_20261120.png)

## Effet sur la planification et les clients

Le calcul MRP du 30 mars à D1920 est rejoué à l'identique. La quantité
ferme de 107 800 unités garde son identité et demeure indisponible
jusqu'à sa nouvelle date. Retarder sa disponibilité du 9 au 11 ou au
18 avril laisse les **208 propositions** identiques et ne crée aucun
déficit de protection. Le stock hors lot suffit à couvrir chaque départ
du témoin dans le bilan conditionnel. Le même flux simulé de
**508 921 unités livrées** reste donc réalisable sur la fenêtre.
Cette preuve concerne les départs enregistrés dans le scénario et
une décision de calcul MRP. Les réactions ultérieures de la chaîne
à un étalement physique ne sont pas rejouées.
[Rejeu du MRP](../../artifacts/testing/essai_execution_etalee_20261120/depot_mrp_replay.json)

## Ce que la durée ne résout pas

Deux semaines distinctes présentent des hausses nettes de stock à
D1920 de **8 089 et 31 986 unités**, avec ajustements nuls et bilan
exact. Si les seules opérations sont des entrées et des sorties
physiques, il faut un apport dans chacune de ces semaines. Les
apports reconstruits sous hypothèse de demande servie totalisent
**110 248 unités**, au-delà de la taille du lot simulé de 107 800.
Une seule réception du lot ne suffit donc pas à expliquer la série.
Un autre lot, des arrivées fractionnées ou des flux hors du
périmètre apparent restent possibles. Les journaux disponibles
ne permettent pas de choisir.

La relation entre retrait d'étuis et baisse du besoin MRP n'est pas
universelle. Sur les semaines de 2025 réunissant un prélèvement non
nul et deux versions consécutives comparables, les deux quantités
coïncident dans 6 cas sur 24 pour 268967 et 1 sur 32 pour 268091.
Les 20 dates prévues des ordres de 268091 correspondent à un délai
de réception de dix jours ouvrés selon le calendrier source.
Ce délai renseigne la disponibilité prévue, indépendamment de la durée
de travail en usine.

Le test soutient une évolution de **l'exécution**. Le lancement,
le travail du lot, la fin physique, le départ et la libération
doivent avoir des dates distinctes. Le MRP doit réutiliser la
date de disponibilité prévue du lot une seule fois. Les mesures
ne justifient pas de fixer dix jours comme durée nominale, de
fractionner les expéditions industrielles ou de changer les
règles MRP du dépôt. Pour trancher, il faut les dates journalières
de travail et les expéditions reliées au même ordre ou lot.

## Reproduction locale

```powershell
python -B -m etudecas.analysis.from_simulation.compare_single_lot_timing --protocol etudecas/artifacts/testing/essai_execution_etalee_20261120/protocol.json --output <nouveau-dossier>/comparison.json
```

Les tests d'exécution sur un lot et le rejeu de planification court
conservent les sources et les paramètres de référence. La
contrelecture indépendante repart des Excel et des journaux natifs.
[Manifeste des preuves](../../artifacts/testing/essai_execution_etalee_20261120/final_manifest.json)
