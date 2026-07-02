# Agent validation visuelle

## Mission

Vérifier automatiquement les figures générées.

## À vérifier

- fichier existe ;
- fichier non vide ;
- dimensions image correctes ;
- titre présent dans la spec ;
- axes présents dans la spec ;
- nombre de points attendu ;
- absence de NaN dans les données tracées ;
- cohérence entre dimensions de la figure et `visual_spec`.

## Sortie attendue

- `visual_report.json` ;
- erreurs critiques ;
- warnings ;
- recommandations de lisibilité.

## Limite

L’agent peut vérifier des critères objectifs. La qualité esthétique finale reste à valider humainement si nécessaire.
