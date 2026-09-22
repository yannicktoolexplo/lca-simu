# Matières, réceptions et préparation des incidents — 19 septembre 2026

La [carte à ouvrir](../../simulation/result/_reruns/corrected_map_20260918/maps/supply_graph_corrected_map_20260918_materials.html)
regroupe les réceptions par article et distingue le lot fabricant, les identités
simulées, les contenants et les propositions de transport. Le [guide métier et
technique](../MATIERES_LOTS_ET_INCIDENTS.md) décrit les données complémentaires,
les règles et les limites.

## Résultat vérifiable

Pour PBATCH-411EC755D7110AE0, l'article 338929 présente quatre réceptions de
5 000 UN. Les quantités consommées restent 2 000, 5 000, 5 000 et 2 400 UN.
Les numéros fabricant et contenants ne sont pas inventés.

L'exploration d'un rappel de LEVT-00002017 / SHIP-00000203 retrouve deux
fabrications : PBATCH-4EAC88EC6CB8555D à J278 et PBATCH-411EC755D7110AE0 à J279.
Le même périmètre est retrouvé indépendamment dans les liens CSV. Une autre
fabrication sans lien demeure hors de ce périmètre.

Le nominal contient 13 683 entrées de stock, sans origine fabricant documentée.
Le scénario de risques contient 14 637 entrées et 396 identifiants d'incident
natifs, dont 293 avec une descendance de production. Ces chiffres décrivent une
couverture de traçabilité, pas un nombre de lots défectueux ni des pertes causées.

## Vérification effectuée

- Suite ciblée traçabilité, logistique, risques, documentation et contrats : **99 tests réussis, 2 ignorés, 18 sous-tests réussis**. Les deux contrôles ignorés sont les tests optionnels de cinq ans ; la carte actuelle a été vérifiée séparément dans Chromium.
- Le dernier ajustement conserve le jour de décision J0 lorsqu'une expédition part plus tard. Le contrat matières et l'intégration ont été revérifiés dans `final-contract-tests.log`.
- **12 contrôles navigateur spécifiques** : quantités, origines inconnues, contenants inconnus, estimation camion, périmètre de rappel indépendant, mise en évidence, navigation, exclusion des lots sans lien, effacement et empreintes physiques inchangées.
- Qualification de la carte actuelle : invariants indépendants du nominal et **9 contrôles navigateur de traçabilité préexistants**. Les quatre calculs historiques n'ont pas été rejoués pour une modification de données descriptives et de rendu.
- Documentation générée et contrôlée pour dix domaines. Les changements d'empreinte documentaire examinés sont conservés dans `documentation-review.json`.
- Analyse statique des noms Python non définis ou utilisés avant affectation : réussie.

Le premier contrôle navigateur spécifique a échoué parce que le test tentait
d'accéder à une variable JavaScript interne à la fonction de chargement ; cette
erreur du test est conservée dans `browser-initial.json`. Une tentative suivante
de comparaison transférait un très gros JSON du navigateur vers Python et a été
interrompue ; le contrôle final calcule des empreintes SHA-256 par blocs dans le
navigateur et ne retourne que les empreintes. Les preuves finales indiquent le
résultat effectivement vérifié.

Les contrôles et captures sont dans
[`artifacts/testing/materials_20260919`](../../artifacts/testing/materials_20260919/).
La provenance lie la nouvelle carte, les CSV comparés, le graphe et le code de
construction. La carte précédente et les résultats physiques restent conservés.

## Portée restante

Le bouton de rappel explore la généalogie existante. Il n'ajoute ni défaut
physique, ni quarantaine effective, ni retard, ni recalcul de coût ou de service.
Les mélanges sans prélèvement détaillé donnent un périmètre possible à examiner,
sans quantité défectueuse attribuée arbitrairement. Les nouveaux incidents
physiques devront passer par une exécution du moteur avec un état daté et des
tests de conservation adaptés.
