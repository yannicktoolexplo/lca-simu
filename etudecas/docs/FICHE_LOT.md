# Fiche récapitulative d'une occurrence de lot

Dans **Parcours simplifié des lots**, l’onglet **Bilan** de la fiche latérale résume le lot à l'ouverture. Cliquez sur une étape du diagramme pour consulter la fiche de cette occurrence, ou utilisez la recherche pour recentrer le parcours. Le bouton **Suivi de lots** et sa fenêtre détaillée sont conservés. Le [guide de l’explorateur](EXPLORATEUR_DES_LOTS.md) détaille le curseur temporel et le bilan réseau.

La fiche indique l'identité du lot, l'article, le site, l'unité, l'origine fabricant documentée ou inconnue, puis les quantités suivantes avec les dates des mouvements :

- Entrée initiale : stock initial, quantité reçue, quantité produite ou entrée estimée selon l'événement source.
- Consommation en fabrication, y compris les substitutions de référence.
- Quantité expédiée et quantité affectée au service client, séparément.
- Pertes ou rebuts enregistrés et réservations en attente de départ, lorsqu'ils existent.
- Solde au site, daté du dernier événement enregistré pour cette occurrence.

## Périmètre à respecter

Les quantités concernent **l'occurrence entière à ce site**, jusqu’à la fin du jour choisi dans le parcours simplifié, ou sur tout son historique en mode **Tout l’historique**. Elles ne dépendent pas du sens ou des branches actuellement visibles dans le diagramme. Une réception mélangée comporte plusieurs lots d'origine : sa fiche présente sa quantité totale ; la contribution du PF suivi reste indiquée séparément sur les cartes du parcours.

Le solde au site n'est ni une quantité restante sur tout le réseau ni un stock recalculé au jour choisi sur la carte principale. La date propre au parcours simplifié filtre les événements de la fiche ; elle reste indépendante de la carte principale. Un solde nul à l'usine peut simplement signifier que le lot a été expédié au dépôt. Le jour affiché sous le solde est celui du dernier mouvement retenu. Avant la création, la fiche indique explicitement que l’occurrence n’existe pas encore.

Une origine fabricant renseignée ne prouve pas que toute l'occurrence possède cette origine : les allocations et leurs quantités restent consultables dans le registre matières. L'histoire antérieure à J0 demeure inconnue pour les stocks initiaux.

## Bilan et réservations

Le moteur peut déduire une quantité lors de sa réservation pour une expédition future. Son départ ultérieur ne débite pas une seconde fois le stock. La fiche distingue les départs effectivement enregistrés et le reliquat réservé non encore parti.

Le bilan est :

**Entrée = consommation + expédition + service client + pertes + réservation en attente + solde au site.**

Exemple calculable à la main : une entrée de 100 UN, une réservation de 60, un départ partiel de 40 et une consommation de 10 donnent 40 expédiées, 20 réservées en attente et 30 en solde. La fiche ne présente pas les 60 réservées comme une seconde expédition.

## Contrôles

Le JavaScript `journeyLotBalance` vérifie l'identité article/site/unité, les identifiants d'événements, les valeurs finies, les quantités entières en UN, la présence d'une entrée initiale unique et chaque solde après mouvement. Les KG peuvent être fractionnaires. Un événement inconnu, une entrée absente, un doublon ou un solde incohérent empêche l'affichage du récapitulatif chiffré ; l'anomalie est visible. Sans événement, le bilan est indisponible, et non nul.

Les tests sur petits cas incluent des erreurs volontaires. Les contrôles Chromium rapprochent les fiches du PF signalé, d'une réception client mélangée, d'une réception matière, d'un lot réservé pour expédition et d'une matière en KG des CSV. La qualification existante rapproche aussi le registre des stocks exportés.

Cette évolution est en lecture seule : aucun paramètre de simulation, stock de sécurité ou mouvement n'est modifié. Voir les [preuves de livraison](../artifacts/testing/lot_summary_20260919/verification-summary.json).
