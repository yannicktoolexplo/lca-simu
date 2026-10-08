# Cicalfate 268091 : diagnostic du démarrage C8R

Analyse des exports historiques 2025 conservés, sans nouvelle simulation ni
modification du moteur ou des données industrielles.

## Constats vérifiés

Le stock initial Muret est correct : **430 538 UN** dans la source et dans
l'ouverture simulée. La divergence apparaît après le début des opérations.

| Photo | Stock réel Muret | Stock simulé, clôture de la veille |
|---|---:|---:|
| 01/01/2025 | 430 538 | 430 538, ouverture |
| 06/01/2025 | 423 434 | 326 886 |
| 13/01/2025 | 601 026 | 80 686 |
| 27/01/2025 | 534 829 | 129 600 |

Au 12 janvier, la simulation a expédié **349 852 UN** depuis Muret, pour une
demande cumulée de **45 219 UN**. L'avance de **304 633 UN** se retrouve
exactement dans le stock client simulé (**293 813**) et le transit (**10 820**).
Ce stock client n'a pas de mesure industrielle indépendante dans ces sources.
Au 25 janvier, Muret est vide mais le client détient encore 181 782 UN et
80 686 UN sont en transit vers lui. Il n'y a pas de perte de matière dans les bilans.

## Mécanisme de prévision au démarrage

`Flow_Data_Customer_Demand.xlsx!Projection!A2:E2` donne, dans la version connue
du 30 décembre 2024, **329 532 UN** pour la semaine du 6 au 12 janvier.
`Historique!A3:D3` porte **35 719 UN** pour cette même semaine : un rapport de
9,23 entre prévision et réalisation. La prévision provient bien de la source ;
aucune lecture d'une version future n'est démontrée.

1. La semaine initiale du 30 décembre n'a pas de prévision dans cette version.
   Le modèle emprunte la période connue la plus proche : 329 532 / 7 =
   47 076 UN/jour. Le 1er janvier, il expédie 96 052 UN : 1 900 de demande
   en attente et 94 152 pour les deux jours de couverture prévisionnelle.
2. Durant la semaine du 6 janvier, il retire la demande arrivée du budget
   prévisionnel hebdomadaire, puis répartit le solde sur les jours restants.
   Le 11 janvier : 329 532 − 30 616 = **298 916 UN** sur un seul jour futur.
   Cette projection alimente le besoin de transport physique vers le client.
3. Le 12 janvier, **293 813 UN** de prévision non consommée expirent, mais
   les produits déjà livrés restent chez le client. L'expiration de la
   prévision ne peut pas annuler ces mouvements physiques.

Le code courant réalise la politique documentée. Ce diagnostic établit le
mécanisme historique, pas une erreur de somme ou une correction certaine à
appliquer automatiquement. Le code courant et le moteur historique C8R n'ont
plus une empreinte identique.

La validation actuelle des prévisions impose une version à partir de J−6 et
un horizon commençant au moins sept jours après cette version. Elle ne permet
donc pas de fournir une version du 23 décembre (J−9) couvrant la semaine
d'ouverture du 30 décembre. Le repli initial est structurel dans ce contrat ;
cela ne prouve pas qu'une telle prévision antérieure existe dans les données.

## Réceptions usine : autre point à traiter

La première réception simulée à Muret arrive le **26 janvier : 129 600 UN**.
Elle suit la première disponibilité usine puis deux jours de transport. Le
modèle applique l'attente de dix jours ouvrés à l'usine avant expédition.
Cette localisation et l'absence de transit initial observé restent des
hypothèses. Les photos réelles montrent déjà une hausse du stock entre le
6 et le 13 janvier (+177 592 UN). Les mouvements nets ne permettent pas
d'identifier à eux seuls les réceptions et les sorties brutes de cette semaine.

## Suite proposée

La première règle à réexaminer est le lien entre prévision résiduelle et
expédition client : préciser si une livraison répond à une commande datée
ou à un programme prévisionnel de livraison. Prévoir explicitement la
couverture de la semaine d'ouverture, puis vérifier le carnet de réceptions
et le transit initial. La prévision ne doit pas être remplacée arbitrairement
par la demande future réalisée ni une absence remplacée par zéro pour faire
coïncider les courbes. Aucun paramètre de sécurité n'est modifié ici.

[Figure](demarrage_cicalfate.png) · [Données journalières](diagnostic_journalier.csv)
· [Manifeste](../../artifacts/testing/cicalfate_startup_20261008/manifest.json)
