# Essai MRP : besoins anticipés par la sécurité source

Ce checkpoint conserve un essai séparé, pas un nouveau nominal. Sur les 22 achats
externes, 7 références améliorent leur erreur de stock et 15 la dégradent face
au comparateur précédent. Voir le rapport métier et l'oracle archivés.

## Contenu et prérequis

- Trois graphes et leurs commandes exactes de 1 825 jours : référence acceptée
  007923, comparateur safety_total_all, candidat besoins anticipés.
- Six fichiers de code à superposer dans une copie de travail du dépôt au commit
  `32d403792d4edc718cc8bc299403cfea1b9175bf`, plus le rapport métier final.
- Scripts de rendu et leurs deux helpers historiques, petites preuves techniques,
  résultats d'oracle et trace conservée du premier échec d'export, corrigé ensuite.
- Aucun CSV de simulation, gros HTML, payload de carte ni fichier Excel.
  Les six classeurs restent dans `etudecas/data/source` ; leurs SHA-256 sont dans
  `checkpoint/recipes.json`. Les autres dépendances sont celles du dépôt indiqué.

Extraire le ZIP dans une copie de travail séparée de ce dépôt. Les entrées gardent
leurs chemins relatifs au dépôt. Examiner les six snapshots avant superposition.
`checkpoint/contents.json` contient le SHA-256 de chaque entrée archivée.

## Rejouer les trois calculs

Depuis la racine de cette copie, lire les commandes de `checkpoint/recipes.json`.
Elles sont les commandes réellement exécutées, avec leurs paramètres complets.
Remplacer seulement le premier argument par le Python local et choisir un dossier
de sortie neuf via `--output-dir`. Toujours conserver `-B`. Ne pas écraser un calcul.
Les graphes sont autonomes : il n'est pas nécessaire de rejouer la longue chaîne
de scripts de préparation des anciens artifacts.

Exemple de lancement Python, après examen de la recette choisie :

```python
import json, subprocess, sys
from pathlib import Path
recipes = json.loads(Path('checkpoint/recipes.json').read_text(encoding='utf-8'))
command = list(recipes['runs']['candidate']['command'])
command[0] = sys.executable
output = Path('etudecas/artifacts/testing/replay_need_dates/run_candidate')
assert not output.exists()
command[command.index('--output-dir') + 1] = str(output)
subprocess.run(command, check=True)
```

Les deux références ont été calculées avec l'ancien moteur. Le candidat est
opt-in : les tests du comportement par défaut passent, mais ces deux références
n'ont pas été resimulées à l'identique avec les six snapshots archivés. Un rejeu
sur le nouveau code doit être qualifié ; aucune identité bit à bit n'est promise.

## Refaire la comparaison HTML

Pour la comparaison autonome, `build_comparison_payload` et
`comparison_document` suffisent, avec les trois nouvelles sorties et les deux
classeurs Flow. Cela ne dépend pas d'une ancienne carte :

```python
from pathlib import Path
from etudecas.visualization.maps.source_comparison import build_comparison_payload
from etudecas.visualization.maps.portable_diagnostic import comparison_document
source = Path('etudecas/data/source')
runs = {'nominal': Path('CHEMIN_REFERENCE_REJOUEE'),
        'total': Path('CHEMIN_COMPARATEUR_REJOUE'),
        'safety': Path('CHEMIN_CANDIDAT_REJOUE')}
payload = build_comparison_payload(source/'Flow_Data_Inventory_and_Replenishment_rules.xlsx',
                                   source/'Flow_Data_MRP_results.xlsx', runs)
with Path('comparaison_rejouee.html').open('x', encoding='utf-8') as stream:
    stream.write(comparison_document(payload))
```

Le rendu complet livré (tableau de synthèse et insertion dans la carte) est dans
`artifacts/testing/mrp_need_dates_20261001/deliver.py`. Il dépend des helpers
`mrp_global_rules_20261001/deliver.py` et `check_view.py`, tous deux archivés.
Adapter ses chemins de sorties neuves et produire de nouvelles preuves avant
d'utiliser son contrôle navigateur. Ce script exige également la coque historique
`etudecas/resultats/regroupement_001757_20260929/carte_mrp_001893_007923.html`,
non archivée ici. Son SHA-256 figure dans `map_delivery.json`. Ses anciens panneaux
et suivis de lots restent historiques ; seul le panneau comparatif est actualisé.
Sans cette coque, la comparaison autonome ci-dessus reste reproductible.

## Limites des preuves conservées

Le dernier calcul réussit en 664,015 s, avec code et entrées inchangés. Le premier
lancement a échoué sur une colonne optionnelle CSV ; sa trace reste conservée.
Un calcul normal d'un jour a ensuite vérifié les 22 achats et les champs vides
des autres paires, puis le calcul complet a été exécuté et qualifié.
Les preuves natives, la comparaison numérique et le navigateur sont archivés.
Les CSV, captures et gros fichiers référencés ne sont pas tous conservés : ces
manifestes documentent l'exécution d'origine, pas une nouvelle qualification
autonome après extraction. Refaire les contrôles sur les résultats régénérés.
Ne jamais relancer les anciens tests d'altération de fichiers ou de dates.
