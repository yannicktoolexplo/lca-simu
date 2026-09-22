# Livraison du 20 septembre 2026 — les quatre priorités du suivi

Le parcours simplifié permet de retrouver une identité jusque dans les mélanges, de consulter une fiche à côté du graphe et de localiser les quantités à une date. Le suivi détaillé reste conservé. Aucun calcul du moteur, stock de sécurité ni incident physique nouveau n’a été appliqué.

1. Recherche des identifiants, fabricants et contenants renseignés ; filtres et pages de résultats ; étape inspectée distincte du point de départ ; retour au recentrage précédent.
2. Graphe visible à 1366 × 768 pour le PF signalé, fiche latérale à onglets, compteur d’étapes, zoom/cadrage et flèches ouvrant les transports.
3. Bilan de fin de journée au site et sur le réseau. Les réservations ne sont pas comptées deux fois. Les mélanges sans allocation certaine produisent des bornes entières en UN ; la conservation resserre ces bornes, notamment lorsque tout le mélange a été servi.
4. Identités, provenance et états physiques explicites ; qualité et péremption inconnues quand absentes ; stocks initiaux, épuisement et substitutions ; explorateur distinct du scénario de risque existant avec ses propres CSV et son graphe d’entrée.

La documentation décrit les règles et leurs limites dans le [guide](../EXPLORATEUR_DES_LOTS.md). Le registre des règles relie les modules JavaScript, l’export du scénario, les tests et les revues navigateur. Les nouvelles empreintes sont acceptées après revue des changements concernés ; les manifestes historiques restent inchangés.

## Vérifications et corrections pendant le développement

- Les contrôles antérieurs ont été adaptés à l’accès par onglets, avec conservation de leurs assertions sur généalogie, quantités et transports.
- Une énumération indépendante des allocations possibles vérifie les bornes d’un mélange de 60 unités suivies et 40 autres, dont 50 sont servies.
- Un premier calcul cumulatif gardait des bornes trop larges après service complet du mélange. La conservation globale les resserre désormais jusqu’à la valeur exacte quand elle est déterminable.
- Le contrôle sur toutes les occurrences a détecté une amplification de résidus numériques pour les KG. Les resserrements tolèrent les résidus inférieurs à la tolérance existante sans les réinjecter comme déficits successifs. Un test dédié couvre ce cas.
- Le navigateur a détecté un événement `change` répété lors du retrait du champ de date. La mise à jour identique est ignorée pour éviter une seconde reconstruction pendant la première.
- Le premier export du scénario utilisait le graphe source général au lieu de son graphe préparé ; le contrôle de cohérence des routes l’a refusé. L’export utilise maintenant le graphe du manifeste et refuse explicitement toute divergence. Aucun CSV de trajet n’a été modifié.

Les [preuves exécutées et empreintes](../../artifacts/testing/explorer_20260920/verification-summary.json) donnent les résultats finaux, les fichiers vérifiés, les limites et les captures. Le contrôle global des bilans utilise l’implémentation de l’interface ; les petits cas et les rapprochements datés aux CSV apportent les vérifications indépendantes complémentaires.

Les effets physiques d’une nouvelle quarantaine, d’un rebut ou d’un retard ciblé sont reportés à une prochaine étape, comme demandé. L’exposition généalogique et les incidents déjà enregistrés restent consultables.
