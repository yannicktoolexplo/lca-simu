# Donnees du cas Etudecas

Ce dossier contient les donnees actives du cas.

- `source/` : fichiers metier source et graphe JSON de base.
- `geocoded/` : graphe geocode et rapports de geocodage.
- `reports/` : rapports d'enrichissement de donnees.
- `MANIFEST.json` : inventaire court des donnees canoniques et des anciens chemins remplaces.

Les scripts doivent pointer vers ces dossiers plutot que vers les anciens
chemins `donnees/` ou `result_geocodage/`.

Le dossier historique `etudecas/donnees/` n'est plus une source canonique. S'il
reste visible localement, c'est uniquement parce qu'un fichier Excel peut encore
etre ouvert par un processus externe. Fermer Excel permet de le supprimer
localement sans perte, puisque `source/Extract_En_cours.xlsx` est la copie active.
