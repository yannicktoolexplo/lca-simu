# Couverture documentaire : acquis et angles morts

Les neuf registres décrivent des conventions précises ; ils ne couvrent pas
toutes les lignes ni tous les mécanismes du simulateur. Les nombres de règles
et de références sont disponibles dans le rapport `reference_status` ; ce ne
sont pas des pourcentages de couverture fonctionnelle ou scientifique.

| Domaine surveillé | Ce qui est relié au code et aux tests |
|---|---|
| Lots et risques | Identités, expéditions et exposition |
| Packages | Contrat des sorties, intégrité et provenance |
| Fournisseurs | Distinction entre candidats descriptifs et autorisation d'action |
| Besoins/capacités | Contrat du couplage dans le domaine enregistré |
| Calibrations | Publication, reprise et écritures atomiques V2 |
| Entrées/API | Types, graphe, accès local et limites d'exécution |
| Comparaisons | Score descriptif, écarts et restitution du navigateur |
| Diagnostic/sensibilités | FIFO, pertes, blocages, essais isolés et livraison |
| Exécution/vérification | UN entiers, stocks et registre, causalité par lot, refus de livraison sans preuves |

## Ce qui reste partiel

- **Calcul MRP et cibles de sécurité** : mécanisme expliqué dans le guide de
  diagnostic, mais les branches du calcul principal ne sont pas toutes des
  références AST surveillées. La cible dépend des besoins et du temps de sécurité,
  pas seulement d'une quantité fixe d'entrée.
- **Nomenclatures, campagnes et stocks initiaux** : traces et tests existent,
  sans registre exhaustif couvrant chaque règle de transformation et d'amorçage.
- **Coûts** : les écarts sont contrôlés ; la couverture complète de la comptabilité
  du moteur et des bases de valorisation reste à formaliser.
- **Risques et Monte Carlo** : provenance contrôlée dans les domaines existants,
  mais ni calibration probabiliste complète ni qualification historique V8 acquise.

## Comment une modification devient visible

`check-all` compare les références AST enregistrées et les empreintes des textes
métier, puis contrôle les pages générées. `build-all` actualise les pages sans
accepter automatiquement les changements métier. `watch-all` surveille ces mêmes
sources ; il n'exécute pas les tests ni le simulateur.

Pour une référence enregistrée modifiée : lire les règles impactées, examiner
le code, exécuter les tests pertinents, corriger l'explication métier et seulement
alors mettre à jour la référence documentaire après revue. Les empreintes d'une
simulation figée et les signatures scientifiques historiques sont des contrats
différents : une mise à jour documentaire ne doit jamais les réaccepter.

Pour une fonction non enregistrée : le contrôle documentaire peut rester vert.
Avant de modifier un mécanisme essentiel non couvert, ajouter sa règle, ses
unités, ses limites et des tests significatifs au registre approprié. L'objectif
immédiat est de rendre les lacunes explicites, sans inventer une documentation
automatique exhaustive ni relancer les calculs existants.
