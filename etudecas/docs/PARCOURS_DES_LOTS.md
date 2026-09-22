# Parcours des lots dans les deux sens

Dans la carte, sélectionnez un lot puis cliquez sur **Parcours simplifié des lots**, à côté de **Suivi de lots**. Cette option ouvre sa propre fenêtre ; le suivi existant conserve son affichage et ses commandes. **Origines** remonte vers les matières ; **Destinations** suit les usages ; **Les deux sens** présente les ascendants et descendants du point sélectionné. La recherche couvre PBATCH/BATCH, LOT, LOCC, STOCKLOT, SHIP, article, site et origines ou contenants renseignés. Les identités présentes dans les mélanges restent recherchables. Voir le [guide de l’explorateur](EXPLORATEUR_DES_LOTS.md) pour les filtres, dates et bilans réseau.

Chaque carte représente une occurrence physique : réception fournisseur, fabrication, stock au dépôt ou réception client. Cliquez sur une étape pour ses mouvements, quantités, départs et arrivées, puis sur **Recentrer sur cette occurrence** pour continuer l'exploration. Une réception client ouvre ses origines, y compris les autres PF présents dans une livraison mélangée. Le bouton **Revenir au lot principal** retrouve la sélection à l'ouverture. Le recentrage reste propre à cette fenêtre et ne change pas la sélection du suivi existant.

## Lecture des quantités et des identités

Les panneaux [transports et impacts](TRANSPORTS_ET_IMPACTS.md) donnent accès au contenu complet des expéditions, aux regroupements camion et au périmètre aval potentiel d'une occurrence ou d'un lot fournisseur renseigné.

La [fiche récapitulative](FICHE_LOT.md), à droite du graphe, affiche le bilan de l'occurrence choisie à la date de lecture, ou après tout son historique. Cliquer sur une étape change la fiche, avec un contour vert distinct du point de départ bleu. Les réservations en attente de départ restent distinctes des expéditions. Les onglets donnent accès aux identités, états et mouvements.

- **Total** désigne la quantité initiale de l'occurrence. **Part du PF suivi** est la contribution du PF sélectionné, calculée par le modèle causal existant : une réception client peut contenir plusieurs PF.
- Le détail d'une fabrication distingue la matière consommée, dans son unité, et la production totale, dans l'unité du PF. La présence de matière dans un PF n'établit pas une quantité de PF attribuable à cette matière.
- Le détail indique le dernier solde enregistré de l'occurrence et son jour. Le service client enregistré concerne l'occurrence entière, éventuellement mélangée ; il reste distinct de sa réception.
- Un SHIP identifie une expédition simulée et son trajet. Les estimations hebdomadaires de palettes et camions restent dans le détail logistique ; un SHIP n'identifie pas un camion réel.
- Un stock initial ne renseigne pas son histoire avant J0. Un numéro de lot fabricant absent reste inconnu. L'absence de lien aval ne prouve pas une livraison : le lot peut rester en stock.

## Règles techniques

Le code `visualization/maps/lot_journey.js` indexe les liens physiques positifs de production et de transport. Deux parcours dirigés distincts remontent les parents et descendent les enfants. Leur union n'ajoute ni les autres usages d'un stock ancêtre, ni les co-origines d'un descendant mélangé. Pour voir toutes les origines de ce descendant, il faut le recentrer.

Les colonnes suivent l'ordre des opérations dans le graphe. Chaque occurrence reste séparée, même au même dépôt pour le même article : fusionner deux stocks créerait visuellement des chemins inexistants entre productions et clients. Les cycles sont signalés explicitement. Les grands parcours affichent d'abord 60 étapes, conservent le focus et indiquent le compteur en tête ainsi que la possibilité d'en afficher davantage. La recherche offre des pages de 30 résultats, triées par création, et des filtres site, article, type, identité et période.

La navigation est en lecture seule. Les contributions PF réutilisent le modèle causal ; aucune répartition matière vers PF n'est inventée. Aucune quarantaine ni perte physique nouvelle n'est appliquée par cette vue.

## Vérification et documentation automatique

Les tests JavaScript utilisent des petits cas calculables à la main : deux branches partageant un fournisseur, réception client mélangée, absence d'origine, unités différentes et cycle volontaire. La vérification Chromium de la carte rapproche les parcours des CSV, contrôle les quantités du PF signalé, puis la réception SHIP-00000203 et ses deux fabrications. Les contrôles existants du registre, du détail des matières et de la carte restent applicables.

Le registre `docs/rules/material_traceability.json` relie cette règle à l'intégration, à la livraison et aux tests. Le guide et le JavaScript sont suivis par empreinte de texte normalisé ; les références Python le sont par AST. Une modification requiert une revue de la règle avant d'accepter une nouvelle empreinte. Ces empreintes détectent les changements ; elles ne remplacent pas l'exécution des tests.

Voir le [bilan de livraison](changes/2026-09-19-lot-journey.md) et les [preuves de séparation des vues](../artifacts/testing/journey_separate_20260919/verification-summary.json).
