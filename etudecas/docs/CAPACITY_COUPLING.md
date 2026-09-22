# Besoins de production et capacités fournisseurs

Le passage d'un besoin statique à un besoin calculé depuis le programme de
production et la nomenclature ne modifie pas nécessairement le seul calcul MRP.
Le besoin peut aussi entrer dans le calcul des capacités fournisseurs et des
approvisionnements amont. Une comparaison doit identifier ces effets avant
d'attribuer une variation du service au seul changement de calcul des besoins.

## Relecture analytique des capacités

L'audit reconstruit une capacité directe nominale en privilégiant une capacité
explicite, puis une capacité de processus. À défaut, un besoin positif intervient
avec un facteur 1,25, en concurrence avec le stock initial rapporté à la période
de revue et un minimum de 1. Sans besoin positif, le stock initial et ce minimum
restent les bases de repli. Les quantités sont exprimées dans l'unité de l'article,
et les capacités en quantité par jour.

Un indice fondé sur la taille de lot et l'horizon de couverture peut relever cette
capacité nominale lorsqu'il reste entre un quart et quatre fois celle-ci. Un
facteur de capacité est ensuite appliqué. En l'absence de capacité explicite,
la capacité effective ne descend pas sous la taille de lot standard positive.

Pour l'amont non modélisé, le besoin journalier est le maximum entre zéro,
le besoin de référence et la taille de lot rapportée au maximum de la période
de revue et du délai de couverture. La capacité nominale est ce besoin divisé
par le taux d'utilisation cible ; un besoin positif avec un taux nul ou négatif
est refusé.

Ces formules sont celles du module de relecture analytique. Leur documentation
ne prouve pas une équivalence permanente avec toutes les branches du moteur.
Un changement du moteur exige aussi une revue de l'audit.

## Rattachement de l'audit au protocole

Le protocole exige un audit qui désigne les mêmes chemins et empreintes de graphe,
de planchers fournisseurs et de profils avant/après. Les fichiers produits doivent
correspondre à leurs empreintes ; le snapshot des paramètres fournisseurs doit
être interne à l'audit et rester intact. Un audit valide dans un autre dossier
de travail ne peut pas être associé implicitement à de nouvelles entrées.

Dans les données de régression conservées, l'audit retrouve 33 lignes fournisseurs,
dont 27 dans le périmètre de besoins modifiés, 22 capacités directes modifiées et
21 capacités amont modifiées. Ce sont des résultats analytiques de ces données,
pas une propriété universelle des réseaux. L'attribution au seul MRP est refusée.

## Limites des preuves

Les tests reconstruisent l'audit depuis les fichiers conservés et des copies
temporaires du graphe et des profils versionnés. Ils contrôlent aussi le refus
d'un graphe différent et d'un snapshot altéré. Ils n'exécutent pas une campagne
scientifique. La documentation générée relie ces règles aux fonctions et tests ;
elle signale leur évolution sans décider automatiquement de leur validité métier.
