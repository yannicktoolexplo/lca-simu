# Agent simulation

## Mission

Verifier et faire evoluer le moteur de simulation dynamique Etudecas sans
transformer un cas particulier en logique codee en dur.

## Entrees

- demande metier ou bug de simulation ;
- configuration du run ;
- fichiers `etudecas/simulation/engine/*` ;
- sorties compactes `summaries/` et CSV utiles dans `data/`.

## A inspecter

- dynamique stocks, production, capacites, MRP, replanification ;
- contraintes de lot, taille de lot, limites hebdo, reports ;
- coherence entre decisions simulees et traces exportees ;
- options CLI et contrats `SimulationRequest`.

## Livrables

- correction ou proposition de refactor bornes aux modules simulation ;
- invariants metier explicites ;
- tests unitaires ou smoke tests courts ;
- impact attendu sur les sorties compactes.

## Critere de done

- le comportement nominal est conserve ;
- les reports, blocages et productions demarrees sont traçables ;
- les tests ciblant la simulation passent ;
- aucun gros resultat n'est versionne.

## Refus automatique

Refuser une correction qui masque une incoherence par une valeur par defaut
silencieuse ou qui ajoute une regle metier non documentee.
