# Archives Etudecas

Pour travailler : [comprendre le code](../README.md), [exécuter une étude](../OPERATIONS.md),
[consulter les règles métier](../docs/README.md), [ouvrir les quatre cartes](../index.html).

Les anciens dossiers ne sont plus dispersés à la racine. Deux archives gardent
leurs éléments utiles avec les chemins d'origine :

| Archive | Contenu |
|---|---|
| [Anciens temporaires](anciens_temporaires_20260925.zip) | Scripts, différences de sources, graphes, paramètres et entrées des essais `tmp`. Les CSV de résultats, cartes et images générés ont été supprimés. |
| [Preuves et documents historiques](preuves_et_documents_20260925.zip) | Anciennes preuves de contrôle, audits, comptes rendus, procédures remplacées du pack et capsules de sources antérieures. |

Le [relevé du rangement](rangement_20260925.json) donne les chemins, quantités,
empreintes et vérifications réellement effectuées. Chaque ZIP contient aussi
son inventaire. Les membres ont été comparés à leurs originaux avant retrait.
Les anciennes commandes ne sont pas toutes compatibles avec le code courant.

L'archive `preuves_et_documents_20260925.zip` reste uniquement sur ce poste :
ses 207 Mo dépassent la limite de GitHub pour un fichier Git ordinaire.
Elle est exclue du suivi Git et ne sera donc pas disponible dans un nouveau
clone du dépôt. Son empreinte reste indiquée dans le relevé du rangement.

Les [dernières preuves de simplification et de simulation](../artifacts/testing/simplification_campagnes_20260928/simplification.json),
les outils de comparaison encore utilisés et les
[pièces de l'incident Sophos](../artifacts/testing/research_triage_20260923/)
restent dépliés. Les capsules de sources directement référencées restent dans
`config/reproduction_20260920/sources/`. Les autres capsules sont dans l'archive
historique, sous leur chemin d'origine.

Le fichier `worstcase/input_case_worst_fill.json` reste une entrée historique.
Les recalculs courants utilisent `etudecas.regenerate` ; voir le
[guide de reconstruction](../docs/REGENERER_RESULTATS.md).

Les procédures de tests archivées décrivent leur époque. Les consignes actuelles,
notamment les exclusions décidées après Sophos, sont celles du projet courant.

La tranche de regroupement du 28 septembre conserve ses neuf anciens chemins
Python dans la capsule `751eeb379d930441fc7a7ee44ca457caadbf5ed396f8f109a448f14de4c183e7.zip`
sous `etudecas/config/reproduction_20260920/sources/`. Quatre chemins rejoignent
trois modules courants ; les quatre superviseurs V5/V6 et leur test exclusif
restent historiques. Les correspondances sont dans `docs/ARBORESCENCE_CIBLE.csv`.
