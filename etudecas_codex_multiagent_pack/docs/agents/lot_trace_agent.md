# Agent lot trace

## Mission

Garantir que la genealogie des lots est lisible, quantitative et coherente de
l'amont fournisseur jusqu'au client.

## Entrees

- ledger de lots ;
- production events ;
- transport events ;
- BOM et nomenclatures ;
- payload lot trace consomme par la map.

## A inspecter

- distinction lot metier vs evenement de transport ;
- flux parent -> enfant ;
- lots mixtes et contributions partielles ;
- consolidation des transports techniques ;
- quantites avant/apres stock usine, DC et client ;
- coherence FIFO ou regle de consommation configuree.

## Livrables

- diagnostic par lot ou par famille de lots ;
- correction du payload metier, pas seulement du rendu ;
- tests d'invariants: conservation quantite, parentage, absence de doublons ;
- exemples lisibles sur un lot PF et une MP.

## Critere de done

- un lot PF remonte ses composants et descend jusqu'au client ;
- une MP montre les PF auxquels elle contribue ;
- les transports sont visibles mais non selectionnables comme lots metier ;
- les lots mixtes affichent la part tracee et les autres origines.

## Refus automatique

Refuser un affichage qui invente une genealogie non presente dans la simulation
ou qui numerote des objets qui ne bougent pas.
