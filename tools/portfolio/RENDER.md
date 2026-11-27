# Supports de réunion

Python 3.11+ prépare la sélection. Le PowerPoint utilise Node.js 18+ et PptxGenJS 4.0.1, installés uniquement pour l’export. Depuis la racine :

```bash
npm ci --prefix tools/portfolio
python tools/portfolio/render.py --review revue.json --audience science --out sortie-science
python tools/portfolio/render.py --review revue.json --audience operations --out sortie-client --public-question "Quelles règles de lotissement tester en premier ?"
```

Prendre un nouveau dossier de sortie par réunion. Chaque export contient un PowerPoint éditable avec notes et un brief Markdown (ordre du jour de 30 minutes, cas discutés, questions, décisions à consigner). Pour un atelier scientifique avec un partenaire extérieur, ajouter `--external`. `--audience mixte` prépare un atelier commun recherche/opérations. `--focus ID` (répétable) sélectionne les capacités du rendez-vous et les lacunes reliées par `capability_ids`. Sans sélection, toutes les fiches relues pour ce public sont présentées. Les autres pistes du recensement restent à qualifier.

En interne, `--question` personnalise la couverture et le brief. Pour les supports externes (opérations, mixte, science avec `--external`), `--public-question` est la question affichée, à fournir dans sa formulation diffusable. En mode externe, ajouter `--private-out chemin/notes.md` pour utiliser aussi `--question`. Le chemin désigne un **nouveau fichier hors du dossier de diffusion** ; sa destination doit être choisie explicitement. Le dossier externe contient exclusivement `presentation.pptx` et `brief.md`.

## Contenu à préparer

Chaque capacité a un niveau de preuve, un nom, une famille, une décision, une méthode, un constat, une limite, un prochain essai et une liste de pièces. En interne, les notes PowerPoint et le brief donnent les références complètes branche, commit et chemin. La diffusion externe exige `external_ok: true` et un objet `public` contenant séparément `name`, `family`, `decision`, `method`, `finding`, `limit`, `next_test` et la figure éventuellement autorisée. Relire chaque libellé, chaque chiffre et les possibilités de réidentification avant de valider cette vue. Le niveau de preuve interne affiché doit s’appliquer au constat diffusé. Les lacunes destinées à un partenaire utilisent la même validation avec un objet `public` contenant `title`, `priority`, `impact`, `test`. Le générateur n’exporte aucun autre champ de la vue interne en mode externe, hormis le niveau de preuve.

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

Utiliser `line` pour une série ordonnée à pas régulier. Les catégories sont également espacées dans le graphique. Fournir les quantiles comme séries distinctes et indiquer la population de simulations et le niveau des quantiles dans la légende. Une valeur manquante demande une explication ou un autre découpage des séries. Le générateur refuse les longueurs incompatibles ou les valeurs non finies. Il pagine les longues comparaisons de catégories et les séries multiples. Le panorama compte uniquement les capacités relues de la sélection. Les notes et le brief conservent les textes complets lorsque leur longueur oblige à les abréger sur la diapositive.


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
