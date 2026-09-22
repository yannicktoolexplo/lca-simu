# Fiche récapitulative du lot — 19 septembre 2026

Le parcours simplifié possède une fiche par occurrence. Elle affiche les entrées, consommations, expéditions, service client, pertes éventuelles, réservations encore en attente et dernier solde au site. Cliquer sur une étape sélectionne sa fiche. La fenêtre « Suivi de lots » conserve son rendu et ses commandes.

La fiche rapproche chaque solde du registre. Elle ne compte pas deux fois une réservation suivie d'un départ. Le bilan porte sur toute l'occurrence au site, même si le diagramme n'affiche qu'une partie de ses liens. Une réception mélangée conserve son total ; les contributions du PF restent séparées dans le diagramme. Un registre absent ou incohérent ne produit pas de totaux présentés comme fiables.

Les tests incluent des bilans calculables à la main et des anomalies volontaires. Les cinq fiches comparées aux CSV couvrent PBATCH-411EC755D7110AE0, une réception client mélangée, SHIP-00000203, un stock fournisseur avec réservation et une matière en KG. Les contrôles de la carte, des matières et des stocks exportés sont également exécutés. Les résultats de simulation ne sont pas recalculés.

Voir le [guide métier et technique](../FICHE_LOT.md) et les [preuves exactes de livraison](../../artifacts/testing/lot_summary_20260919/verification-summary.json). Les limites restent explicites : ce solde local n'est pas une quantité restante sur tout le réseau, ni une valeur recalculée au jour du curseur principal.
