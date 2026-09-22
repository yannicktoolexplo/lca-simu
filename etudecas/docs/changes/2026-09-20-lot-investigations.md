# Enquêtes conservées, fiches exportées et voisinage des lots

L’explorateur dispose désormais de fichiers d’enquête, d’un export HTML imprimable et d’un déploiement graphique par voisinage. Ces fonctions prolongent l’interactivité de la livraison précédente. Le suivi détaillé et les résultats physiques restent conservés ; les nouveaux incidents physiques sont toujours reportés.

Le fichier d’enquête contient la navigation et une empreinte des données. L’import valide intégralement le fichier avant de remplacer la vue. Les lots et expéditions sont locaux au scénario : une enquête nominale n’est pas acceptée dans le scénario de risque simplement parce que ses identifiants y existent aussi.

La fiche exportée présente les bilans datés et les liens du parcours complet dans une page sans script. Les limites de mélange, les unités, la différence entre date des bilans et historique des liens ainsi que la provenance sont explicites. L’état de navigation est capturé avant le calcul asynchrone de l’empreinte.

Le voisinage restreint uniquement les cartes visibles. Les voisins sont issus des liens réels du parcours ; les branches restent distinctes. Les bilans réseau et impacts potentiels restent complets. Les cartes sont choisies par proximité du point de départ avant pagination.

Les [preuves](../../artifacts/testing/lot_cases_20260920/verification-summary.json) rassemblent les tests, les essais hors ligne, les exports de démonstration et la préservation des résultats. Le [guide](../ENQUETES_LOTS.md) explique les actions et limites. Les règles métier et les sources sont suivies dans le registre documentaire existant.
