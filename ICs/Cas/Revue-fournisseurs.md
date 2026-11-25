# Quels fournisseurs retenir quand la revue ne compte que cinq places ?

Ce cas de simulation compare des règles de sélection avec un même budget de cinq dossiers. La décision consiste à repérer les fournisseurs dont une perturbation dégrade le service. Les dossiers nominatifs et les données de commande ne font pas partie du jeu public.

## Une question à poser en réunion achats

Une référence confiée à une seule source qualifiée peut bloquer la production même si elle coûte peu. Demander quelle autre source est déjà qualifiée, combien de jours couvre le stock utilisable et quel ordre de fabrication serait le premier touché permet de préparer la revue. Une étude publiée sur la chaîne automobile montre comment évaluer l’effet d’un arrêt fournisseur avant d’en estimer la fréquence. [Publication dans *Interfaces*](https://doi.org/10.1287/inte.2015.0804)

## Comment le test a été construit

Sur 29 fournisseurs représentés dans la simulation, 27 ont un résultat exploitable. Deux résultats manquent. Parmi les 13 fournisseurs classés mono-source, cinq perturbations font baisser le service, dont trois d’au moins 20 points de pourcentage. Sur les 14 autres, une perturbation le fait baisser d’au moins 20 points.

Une liste choisie uniformément sans remise parmi les 27 fournisseurs sert de témoin. Six autres plans réservent de zéro à cinq places au groupe mono-source. Les places sont tirées au hasard à l’intérieur de chaque groupe. Deux règles fixes prennent respectivement les cinq délais les plus longs et les cinq premières priorités d’action. Chaque fournisseur compte une fois dans une liste.

| Règle | Listes possibles | Listes sans baisse détectée | Listes sans baisse d’au moins 20 points détectée |
| --- | ---: | ---: | ---: |
| Tirage uniforme | 80 730 | 20 349 (25,21 %) | 33 649 (41,68 %) |
| Trois mono-source et deux autres | 26 026 | 4 368 (16,78 %) | 9 360 (35,96 %) |
| Quatre mono-source et un autre | 10 010 | 910 (9,09 %) | 2 730 (27,27 %) |
| Cinq mono-source | 1 287 | 56 (4,35 %) | 252 (19,58 %) |
| Cinq délais les plus longs | 1 | 1 (100 %) | 1 (100 %) |

## Ce que la revue peut en tirer

Réserver quatre places au groupe mono-source et une aux autres réduit de 16,12 points la probabilité de manquer tous les cas de baisse, par rapport au témoin. Une liste exclusivement mono-source fait encore mieux sur cet indicateur. Elle écarte toutefois d’office le cas important qui se trouve dans l’autre groupe. Le choix dépend donc aussi de la nécessité d’examiner cet autre groupe.

Pour refaire le calcul du plan quatre plus un, on dispose de huit mono-source et treize autres fournisseurs sans baisse. Il existe 70 façons de choisir quatre dossiers parmi les huit et treize façons de compléter la liste. Cela donne 910 sélections sans cas. Le nombre total de sélections de ce plan est 715 × 14 = 10 010. Les résultats des neuf règles pour les deux seuils figurent dans le [tableau des sélections](revues-fournisseurs.csv). Les champs de places sont vides lorsque la règle n’impose aucun quota.

Les probabilités portent sur le choix des dossiers parmi les cas simulés. Elles ne donnent pas la fréquence de panne d’un fournisseur. Les deux dossiers sans essai restent à qualifier. Sur un nouveau portefeuille, figer d’abord les groupes, les seuils et la perturbation de référence, puis évaluer aussi les fournisseurs qui ne seraient pas visités. C’est ainsi qu’on peut recompter les cas manqués.
