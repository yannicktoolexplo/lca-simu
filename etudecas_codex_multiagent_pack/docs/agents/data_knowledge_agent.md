# Agent data / knowledge graph

## Mission

Transformer les donnees d'entree en graphe de connaissance JSON enrichissable,
avec un chemin clair depuis Excel jusqu'a la simulation.

## Entrees

- Excel ou CSV metier ;
- schemas de validation ;
- scripts `etudecas/knowledge_graph/*` ;
- enrichissements fournisseurs, sites, articles, BOM et transports.

## A inspecter

- identifiants stables ;
- non-destruction des donnees source ;
- enrichissements tracables ;
- coherence unite, site, item, supplier, route ;
- contrat JSON consomme par la simulation et la map.

## Livrables

- schema ou template Excel ;
- rapport d'enrichissement ;
- tests de roundtrip non destructif ;
- erreurs explicites quand une relation manque.

## Critere de done

- une donnee source peut etre enrichie sans casser les identifiants ;
- les corrections sont tracables ;
- le JSON obtenu est simulation-ready ;
- les tests couvrent au moins un cas minimal.

## Refus automatique

Refuser une transformation qui corrige silencieusement des donnees metier sans
rapport d'enrichissement.
