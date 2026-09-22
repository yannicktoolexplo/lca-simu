# Détail des transports et recherche d'impacts — 19 septembre 2026

Deux panneaux complètent le parcours simplifié : le contenu complet d'une expédition avec ses regroupements camion existants, et le périmètre aval potentiel d'une occurrence ou d'un lot fabricant renseigné. Ils restent indépendants de la fenêtre « Suivi de lots ».

Pour SHIP-00000203, le détail distingue les 5 000 UN parties à J60 et reçues à J65, ainsi que la réservation préalable. Le groupe hebdomadaire est affiché avec son estimation, ses hypothèses et les autres expéditions qu'il contient. Ces informations ne créent pas une identité de camion réel.

L'analyse de l'occurrence LOT-00000838 retrouve huit occurrences, dont deux fabrications et trois réceptions client. Son périmètre ne s'étend pas aux autres lots simplement présents dans le même camion ou dans une autre branche. Les réceptions mélangées sont incluses de manière conservatrice ; leurs quantités totales ne deviennent pas des quantités défectueuses.

Le détail de SHIP-00001396 présente les deux lots source et 13 251 UN expédiées, tandis que le parcours du PF PBATCH-411EC755D7110AE0 conserve sa contribution de 3 473 UN. Les sommes de départ sont séparées par article/unité et ne doublent ni réservations ni réceptions.

Les tests couvrent les mélanges, les unités distinctes, les données inconnues, les branches sans lien, les origines fabricant documentées ou possibles et les interactions de navigation/remise à zéro. Un premier cas de test d'origine inutilisée omettait l'index des réceptions du contexte ; la fixture a été complétée pour exercer effectivement l'erreur utilisateur attendue. Les contrôles Chromium comparent les expéditions et descendants aux CSV, et vérifient les empreintes du registre avant/après exploration.

Voir le [guide métier et technique](../TRANSPORTS_ET_IMPACTS.md) et les [preuves de livraison](../../artifacts/testing/transport_impacts_20260919/verification-summary.json). Cette recherche d'impacts n'applique aucune quarantaine et ne rejoue pas la simulation. Les stocks de sécurité et les résultats numériques restent inchangés.
