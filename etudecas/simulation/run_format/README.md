# Contrat de validation des résultats

Un package décrit un résultat de simulation et permet à un consommateur de
retrouver ses fichiers. La validation contrôle son intégrité structurelle.
Elle ne certifie ni la pertinence des hypothèses ni la justesse des résultats métier.

## Garanties

- Le manifeste et les documents référencés doivent être des fichiers JSON
  lisibles, du type attendu. Les constantes NaN et Infinity sont refusées.
- Les nœuds et flux sont non vides, avec des identifiants textuels uniques.
  Chaque origine et destination de flux référence un nœud du package.
- Chaque entrée d'artefact possède un nom unique. Son indicateur `exists`
  doit correspondre à la présence physique d'un fichier ; `required` et
  `exists` sont des booléens. Un fichier facultatif absent reste autorisé.
- Les CSV présents sont parcourus intégralement : en-tête non vide et sans
  doublons, même nombre de champs par ligne, colonnes et nombre de lignes
  identiques à l'index. Les lignes blanches sont ignorées comme à l'export.
  Les JSON présents sont lus et leur taille vérifiée lorsqu'elle est indexée.
- Les trois CSV obligatoires du schéma restent obligatoires même si leur entrée
  est supprimée ou si `required` est falsifié : indicateurs quotidiens, événements
  de lots et généalogie. Ils doivent contenir des données. Les deux CSV de lots
  peuvent ne contenir que leur en-tête si `lot_trace_enabled` vaut exactement
  `false`. Une chaîne `"false"` ne désactive pas ce contrôle.
- Les index par groupe doivent reproduire les entrées correspondantes de
  l'index principal, dans le même ordre.

Les chemins des documents sont relatifs au dossier du package. Les chemins
d'artefacts sont relatifs à `output_dir` du manifeste, ou au parent du package
si cette valeur est absente. Les chemins absolus restent acceptés, conformément
au chargeur. Un package peut donc être situé hors du dossier des résultats.
Déplacer uniquement le package ne rend pas ses données transportables.

## Utilisation et limites

```powershell
python -m etudecas.simulation.run_format.cli validate --package-dir chemin/vers/run
```

Les commandes `validate` et `export` retournent 1 si un contrôle échoue.
L'export conserve le package écrit pour permettre le diagnostic.
L'API `validate_run_package` retourne les contrôles et leurs détails ;
`assert_run_package_valid` lève une exception contenant les échecs.
La validation ne répare pas et ne régénère pas les résultats.

Le coût de lecture est proportionnel au volume des fichiers présents ; les
lignes CSV ne sont pas conservées en mémoire. Les sorties doivent être stables
pendant la validation : aucun verrouillage ni instantané n'est créé.

Ce contrat ne contrôle pas encore les unités, les quantités, les valeurs de
chaque cellule CSV, les plages de jours déclarées, les échantillons d'entités,
les jointures entre lots, ni la provenance scientifique. Un fichier modifié
avec les mêmes colonnes et le même nombre de lignes peut passer ces contrôles.
Les KPI peuvent être un objet vide. Les résumés JSON découverts à l'export sont
contrôlés lorsqu'ils sont indexés ; leur exhaustivité n'est pas certifiée.
Les empreintes documentaires servent à détecter une modification du code,
pas à authentifier les résultats de simulation.
