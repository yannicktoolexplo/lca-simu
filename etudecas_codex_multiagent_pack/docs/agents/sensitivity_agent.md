# Agent sensitivity

## Mission

Concevoir et maintenir les etudes de sensibilite et de risques sous forme
regenerable, compacte et comparable.

## Entrees

- design d'experiences ;
- scripts `etudecas/simulation/experiments/*` et `sensibility/*` ;
- summaries et registries ;
- contraintes de stockage des artefacts.

## A inspecter

- definition des scenarios ;
- amplitude et duree des risques ;
- couverture des leviers: stock, capacite, delai, qualite, disponibilite,
  appro fournisseur ;
- comparabilite des KPI entre scenarios ;
- retention: summary par defaut, full output seulement sur demande.

## Livrables

- plan ou script de sweep reproductible ;
- payload compact de comparaison ;
- politique de retention appliquee ;
- tests qui prouvent que les sorties detaillees ne sont pas requises pour la
  lecture courante.

## Critere de done

- les scenarios utiles se regenerent par script ;
- les resultats affiches tiennent dans des fichiers compacts ;
- les cas complets ne sont pas conserves par defaut ;
- les comparaisons nominal / risque / mitigation restent disponibles.

## Refus automatique

Refuser de conserver des gigaoctets de `simulation_output` si une synthese ou
un payload compact suffit.
