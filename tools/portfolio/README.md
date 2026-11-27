# Portefeuille des méthodes de simulation supply chain

Dans Codex, demander par exemple :

> Utilise supply-portfolio. Actualise toutes les branches de lca-simu. Pour une réunion de 30 minutes avec une responsable planification, prépare un PowerPoint sur les arbitrages entre stock, service et impact environnemental, puis un brief. Montre un résultat chiffré, sa limite et la décision qu’elle pourrait prendre. Indique les données nécessaires pour tester cette décision chez elle.

> Prépare une revue avec un laboratoire sur les cascades dépendantes de l’état. Compare les variantes par branche, distingue résultats archivés et reproduits, précise le témoin et propose une expérience qui permettrait de réfuter l’hypothèse. Le laboratoire est externe.

> Quels savoir-faire sont propres à une branche, quelles méthodes restent au stade de proposition, et quelles preuves faut-il acquérir en priorité pour notre prochain comité R&D ?

Le [panorama initial](panorama-initial.md) rassemble les 43 familles, les 160 outils candidats et les manques proposés sur les cinq branches de départ. Le registre qualifié se trouve dans [catalog.json](catalog.json). La [procédure de revue](protocole.md) indique ce qu’il faut vérifier pour parler d’une méthode à un scientifique, un planificateur ou un client.

## Lancer depuis la racine du dépôt

Python 3.11+ et Git suffisent pour l’inventaire et la revue. Chaque exécution utilise de nouveaux répertoires. Les chemins ci-dessous fonctionnent aussi sous PowerShell. Choisir un suffixe différent au prochain passage.

```sh
python -B tools/portfolio/scan.py --repo . --out ../portfolio-01/scan
python -B tools/portfolio/review.py --scan ../portfolio-01/scan --out ../portfolio-01/revue
```

Le scan en ligne récupère toutes les têtes du distant `origin`, même dans un clone initialement limité à une branche. Changer le distant avec `--remote NOM`. Le travail local et les modifications non commises ne font pas partie de cet instantané. En déplacement, ajouter `--offline` pour utiliser les références et objets disponibles en cache. Le mode figure dans `inventory.json`. Un réseau indisponible en mode en ligne produit une erreur.

Pour le PowerPoint éditable et le brief, installer une fois les dépendances de rendu avec Node.js 18+ et npm. Cette installation reste locale au harnais. Les exemples génèrent des supports différents à partir de la même revue.

```sh
npm ci --prefix tools/portfolio
python -B tools/portfolio/render.py --review ../portfolio-01/revue/review.json --audience science --out ../portfolio-01/science
python -B tools/portfolio/render.py --review ../portfolio-01/revue/review.json --audience operations --public-question "Quel stock protège les livraisons pendant une perturbation ?" --out ../portfolio-01/operations
python -B tools/portfolio/render.py --review ../portfolio-01/revue/review.json --audience mixte --out ../portfolio-01/mixte
```

Pour un laboratoire externe, ajouter `--external` au profil `science`. Pour une réunion courte, utiliser plusieurs `--focus ID` parmi les identifiants de fiches du portefeuille. La question personnalise le cadrage. Les choix de méthodes s’effectuent avec `--focus` ou avec Codex, qui sélectionne et instruit les fiches en fonction du besoin. Le [guide de rendu](RENDER.md) décrit les options, les graphiques et la diffusion.

## Ce que contient une exécution

| Fichier | Usage |
|---|---|
| `scan/inventory.json` | SHA et taille de chaque arbre, signaux par méthode, outils importés ou déclarés, exemples et couverture de lecture. |
| `scan/files.jsonl` | Manifeste des entrées Git par chemin/version, avec les branches qui les portent. Inclut les données, images, rapports, liens et entrées non interprétées. |
| `scan/review.jsonl` | Fichiers à examiner, dont les non classés et les contenus dont la lecture automatique est incomplète. |
| `revue/portefeuille.md` | Registre interne lisible des capacités, décisions, preuves, limites, essais proposés et signaux de méthodes/outils. |
| `revue/differences.tsv` | Matrice chemin × branche pour les divergences et présences partielles. Un identifiant de contenu identique signale le même contenu. |
| `revue/instruction.tsv` | État de la revue pour chaque méthode de la taxonomie, fiches associées et première vérification à entreprendre. |
| `revue/review.json` | Fiches utilisables, manques proposés et fiches suspendues après changement d’une source. Entrée du rendu. |
| `PUBLIC/presentation.pptx`, `PUBLIC/brief.md` | Diaporama avec notes et dossier de réunion adapté au profil choisi. Remplacer PUBLIC par le nom du dossier de sortie. |

## Actualiser le contenu scientifique

1. Commencer par les écarts de branches, le tableau d’instruction et les fichiers peu ou mal classés. Les signaux sont heuristiques. L’indexation couvre les chemins suivis par Git. La lecture du texte, des imports Python et des déclarations couvre un sous-ensemble explicite, avec ses limites dans `coverage`. Un PDF, une archive, des données Git LFS ou un sous-module peuvent nécessiter une investigation complémentaire. Les fichiers non versionnés et les services externes sont hors de l’instantané.
2. Retrouver les pièces au commit dans le manifeste. Utiliser `git show SHA:CHEMIN` pour un fichier texte, et la valeur `blob` du manifeste comme empreinte. Rechercher l’implémentation et les consommateurs, vérifier les unités et la décision que le modèle peut faire changer. Les travaux expérimentaux, les méthodes essayées sans avantage et les contre-exemples font partie du portefeuille.
3. Ajouter une entrée dans `catalog.json`, ou fournir une copie enrichie avec `review.py --catalog CHEMIN`. Indiquer `method_ids` de [taxonomy.json](taxonomy.json), `evidence` et le statut défini dans le [protocole](protocole.md). Pour `reproduit`, renseigner aussi `replay.command`, `environment`, `oracle`, `tolerance`, `observed` et `manifest`. Le manifeste doit être une des pièces citées. La revue ne lance pas le modèle.
4. Relier chaque manque à des `capability_ids` lorsqu’il concerne une fiche précise. Documenter l’impact et le test discriminant, puis préciser le domaine réellement couvert par ce test. Étendre la taxonomie dès qu’une technique inconnue est identifiée. Une recherche infructueuse dans les branches ne suffit pas à déclarer une compétence absente.
5. Pour toute fiche externe, créer sa projection `public`, relire le texte et approuver explicitement les valeurs de `public.visual` si présentes. Les réunions externes utilisent uniquement ces contenus dédiés. Conserver localement toute note client ou donnée non destinée au dépôt public.


## Vérifications ciblées

Depuis la racine, les commandes suivantes contrôlent la suspension des preuves périmées, la projection dédiée aux destinataires et la lecture des séries chiffrées dans les CSV archivés. Cette dernière vérification nécessite les commits sources. Elle relit les pièces, sans lancer de simulation.

```sh
python -B tools/portfolio/test_review.py
python -B tools/portfolio/test_render.py
python -B tools/portfolio/test_catalog_figures.py
```
