# Roadmap Etudecas multi-agent

## PR 1 - Stabiliser les contrats simulation

- formaliser `SimulationRequest` et overrides ;
- isoler les sorties compactes ;
- tester un run court et un run 5 ans en smoke optionnel.

## PR 2 - Lot trace generique

- construire un payload metier independant du HTML ;
- couvrir PF -> MP et MP -> PF ;
- traiter lots mixtes et transports consolides ;
- ajouter invariants de conservation des quantites.

## PR 3 - Sensibilites regenerables

- standardiser les designs de scenarios ;
- produire summaries et payloads compacts ;
- supprimer les `simulation_output` complets par defaut ;
- comparer nominal, risques et mitigations sans stocker des GB.

## PR 4 - Map et payloads

- separer payload metier et rendu ;
- garder un HTML autonome raisonnable ;
- charger les blocs lourds a la demande ;
- tester les onglets critiques.

## PR 5 - Data / knowledge graph

- formaliser Excel d'entree et enrichissements ;
- valider schemas, unites, identifiants et relations ;
- generer un JSON simulation-ready ;
- tracer toutes les corrections.

## PR 6 - Validation transversale

- verifier simulation, lots, risques, couts, stocks et UI ;
- ajouter un rapport de validation compact ;
- bloquer les regressions et artefacts lourds.

## PR 7 - Documentation d'exploitation

- documenter comment regenerer les runs ;
- expliquer les roles agents ;
- definir quoi garder et quoi supprimer.
