# Supports de réunion

Python 3.11+ prépare la sélection. Le PowerPoint utilise Node.js 18+ et PptxGenJS 4.0.1, installés uniquement pour l’export. Le modèle français Scalian 2026 fournit sa couverture, ses dispositions de contenu, son thème et ses logos à chaque présentation.

Pour un clone Windows, indiquer une fois par session PowerShell l’emplacement du modèle du projet. Adapter le chemin à son emplacement réel.

```powershell
$env:SCALIAN_PPTX_TEMPLATE = "C:\Documents\Template Scalian - FR 2026.pptx"
```

Depuis la racine du dépôt :

```bash
npm ci --prefix tools/portfolio
python tools/portfolio/render.py --review revue.json --audience science --out sortie-science
python tools/portfolio/render.py --review revue.json --audience operations --out sortie-client --public-question "Quelles règles de lotissement tester en premier ?"
```

Prendre un nouveau dossier de sortie par réunion. Chaque export contient un PowerPoint éditable avec notes et un brief Markdown (ordre du jour de 30 minutes, cas discutés, questions, décisions à consigner). Pour un atelier scientifique avec un partenaire extérieur, ajouter `--external`. `--audience mixte` prépare un atelier commun recherche/opérations. `--focus ID` (répétable) sélectionne les capacités du rendez-vous et les lacunes reliées par `capability_ids`. Sans sélection, toutes les fiches relues pour ce public sont présentées. Les autres pistes du recensement restent à qualifier.

En interne, `--question` personnalise la couverture et le brief. Pour les supports externes (opérations, mixte, science avec `--external`), `--public-question` est la question affichée, à fournir dans sa formulation diffusable. En mode externe, ajouter `--private-out chemin/notes.md` pour utiliser aussi `--question`. Le chemin désigne un **nouveau fichier hors du dossier de diffusion** ; sa destination doit être choisie explicitement. Le dossier externe contient exclusivement `presentation.pptx` et `brief.md`.

## Contenu à préparer

Chaque capacité a un niveau de preuve, un nom, une famille, une décision, une méthode, un constat, une limite, un prochain essai et une liste de pièces. En interne, les notes PowerPoint et le brief donnent les références complètes branche, commit et chemin. Chaque fiche dispose d’un visuel principal `visual` et peut proposer des pièces complémentaires dans `exhibits`. La diffusion externe exige `external_ok: true` et un objet `public` contenant séparément `name`, `family`, `decision`, `method`, `finding`, `limit`, `next_test` et la figure éventuellement autorisée. Relire chaque libellé, chaque chiffre et les possibilités de réidentification avant de valider cette vue. Le niveau de preuve interne affiché doit s’appliquer au constat diffusé. Les lacunes destinées à un partenaire utilisent la même validation avec un objet `public` contenant `title`, `priority`, `impact`, `test`. Le générateur n’exporte aucun autre champ de la vue interne en mode externe, hormis le niveau de preuve.

Les valeurs suivantes illustrent uniquement la structure d’une figure. Dans une revue, employer des valeurs extraites d’une pièce référencée au commit et préciser le scénario, le dénominateur, l’horizon et la limite dans la fiche.

```json
{
  "kind": "bar",
  "title": "Commandes servies pendant la perturbation",
  "x_label": "Scénario",
  "unit": "Commandes servies (%)",
  "categories": ["Témoin", "Essai"],
  "series": [{"name": "Taux de service", "values": [80, 85]}],
  "caption": "Exemple de structure avec données fictives."
}
```

Utiliser `line` pour une série ordonnée à pas régulier. Les catégories sont également espacées dans le graphique. Pour une enveloppe, utiliser `kind: "band"` avec trois séries ordonnées (borne basse, médiane, borne haute). Indiquer la population simulée, le nombre de réplications et la convention de quantile. Les jalons doivent être régulièrement espacés. Étiqueter toute campagne distincte de celle décrite par la fiche. Une valeur manquante demande une explication ou un autre découpage des séries. Le générateur refuse les longueurs incompatibles ou les valeurs non finies. Il pagine les longues comparaisons de catégories et les séries multiples. Le panorama compte uniquement les capacités relues de la sélection. Les notes et le brief conservent les textes complets lorsque leur longueur oblige à les abréger sur la diapositive.


## Figures scientifiques déjà archivées

Pour reprendre un schéma ou une figure complexe dans sa forme publiée, utiliser un PNG fixe du dépôt. Ajouter la pièce dans `evidence` (branche, commit, chemin, blob). Dans la vue interne, désigner la même pièce :

```json
{
  "kind": "image",
  "title": "Stocks et demande en attente au fil des semaines",
  "caption": "La partie droite suit les stocks et les unités en attente sur le scénario simulé.",
  "evidence": {
    "branch": "dev_P0001",
    "path": "POC2026/outputs_sddlca_poc/images/poc_state_space_projection.png",
    "blob": "31c1fa975d2baac363a6d9765aaddaa5424f1c2e"
  }
}
```

Passer `--repo chemin/vers/lca-simu` si la commande est lancée hors du dépôt. Le générateur vérifie le couple commit/chemin puis lit le blob par son empreinte Git. Il conserve les proportions et intègre les pixels dans la diapositive. Les libellés incorporés restent dans l’image archivée. Les titres, légendes et notes demeurent éditables.

Pour diffuser une image, examiner les axes, légendes, annotations et identifiants **sur les pixels**. Dans `public.visual`, renseigner la version relue du titre et de la légende, la même référence et `approved_blob` égal à l’empreinte du PNG autorisé. Le support partageable conserve les pixels et les légendes autorisés. Les chemins Git et métadonnées textuelles du PNG restent hors du support externe. Un autre blob nécessite une nouvelle revue. Le mode graphique natif reste disponible pour des valeurs approuvées dont on souhaite rééditer les séries dans PowerPoint.


## Composer une planche de résultat

Choisir un graphique pour une évolution, un diagramme pour un mécanisme ou un tableau pour des hypothèses ou des résultats qui doivent être lus précisément. Dans le catalogue, le champ `visual` et les éléments de `exhibits` acceptent les graphiques `line`, `bar`, `band`, le format `image` et les formats éditables ci-dessous. Pour un visuel qui porte sur une expérience distincte, renseigner `observation`, `limit` et, si son niveau de preuve diffère, `status` avec un statut du catalogue. L’export externe prend exclusivement `public.visual` et `public.exhibits`.

| Format | Données | Usage |
|---|---|---|
| `table` | `title`, `caption`, `columns` (libellés) et `rows` (listes de cellules texte de même longueur) | Unité et périmètre des paramètres, témoin et intervention ou comparaison de résultats. |
| `flow` | `title`, `caption` et `steps` (suite d’objets `label`, `detail`) | Chronologie étayée, séquence de calcul ou parcours d’un lot. Préciser quelle interprétation s’applique. |

Placer la lecture attendue près du visuel. Donner dans les notes les preuves, limites et conditions du prochain essai. Pour la vérification, comparer un panneau de données à ses sorties sources, ouvrir le deck sur sa couverture et une page de contenu, puis vérifier les titres, unités et légendes dans le rendu.

Contrôle du fichier final contre le modèle utilisé (couverture, disposition de contenu, thème, actifs de marque, relations et notes) :

```sh
python tools/portfolio/test_template.py --template "Template Scalian - FR 2026.pptx" --presentation sortie-science/presentation.pptx
```
