# Map Payload Modes

Generated maps can use three payload modes.

## Autonomous raw HTML

Default mode. The full `DATA` object is embedded as plain JSON.

- Pros: works everywhere as a single file.
- Cons: very large HTML files.

## Autonomous compressed HTML

Use:

```bash
python etudecas/visualization/maps/build_supplychain_worldmap.py --compress-embedded-payload
```

or post-process an existing map:

```bash
python etudecas/visualization/maps/compress_html_payload.py --input map.html --execute
```

The map remains a single HTML file. The `DATA` payload is embedded as gzip/base64
and inflated in the browser before initialization.

Requires a recent browser with `DecompressionStream("gzip")`, such as recent
Edge or Chrome.

## Autonomous chunked HTML

Recommended for large 5-year maps:

```bash
python etudecas/visualization/maps/build_supplychain_worldmap.py --chunked-embedded-payload
```

or post-process an existing map:

```bash
python etudecas/visualization/maps/chunk_html_payload.py --input map.html --execute
```

The map remains a single HTML file, but every top-level `DATA` key is stored as
a separate gzip/base64 block with a manifest.

This is the recommended user-facing mode today: it preserves the existing map
UI, tabs, Plotly interactions, lot tracing and risk panels. Current generated
maps load all blocks before initialization for compatibility. The format is
ready for future panel-level lazy loading through
`loadEmbeddedChunkedMapGroup(groupName)`.

Typical 5-year map result observed:

- raw autonomous HTML: about 147 MB;
- compressed autonomous HTML: about 9.9 MB;
- chunked autonomous HTML: about 9.4 MB.

## External JSON payload

Use:

```bash
python etudecas/visualization/maps/build_supplychain_worldmap.py --externalize-payload
```

or post-process an existing map:

```bash
python etudecas/visualization/maps/externalize_html_payload.py --input map.html --execute
```

This produces a small HTML file and a sibling JSON payload. It is best for web
serving, but it is not fully autonomous.

## Supplier what-if panel

Use on an existing interactive autonomous map:

```bash
python etudecas/visualization/maps/inject_supplier_what_if.py --input map.interactive_autonomous.html --execute
```

This injects a floating `What-if fournisseurs` panel backed by normalized
sensitivity results, for example
`etudecas/simulation/experiments/result/supplier_parameter_ingested/metrics.csv`.

This is a precomputed what-if explorer: changing a slider selects a simulated
scenario already present in `metrics.csv`. It does not run the Python simulation
engine inside the browser. It also displays the standard simulation request
contract for the selected scenario. A truly live simulator should be implemented
as a local API or a Pyodide/WebWorker app layer on top of that same contract.

## Audit fournisseur et criticité

La carte analyse par défaut les classeurs d'audit fournisseur placés dans
`etudecas/data/source/`. Le fichier
`Trame d'audit fournisseur finalisé.xlsx` est prioritaire sur une ancienne trame
portant le même identifiant fournisseur.
Lorsqu'un identifiant fournisseur `VD...` est trouvé dans la trame :

- les 28 critères et les 6 familles d'audit sont ajoutés à la fiche du fournisseur
  dans le mode `Criticité fournisseurs` ;
- l'onglet `Audit fournisseur`, affiché en premier, donne accès à la synthèse,
  au `Contexte public`, aux trois radars par famille (`Maturité`, `Criticité`,
  `Résilience`) et au tableau complet des 28 critères ;
- maturité, criticité `P x I` et délai de résilience sont ramenés sur une échelle
  commune par la formule documentée dans la fiche ;
- un indice croisé indicatif conserve 70 % de criticité structurelle et ajoute
  30 % d'audit réel ou d'estimation ; le rang principal reste 100 % structurel
  afin de rester comparable entre les 29 fournisseurs.

Le référentiel est présenté sur la fiche de tous les fournisseurs du graphe. Si
un fournisseur n'a pas encore de trame renseignée, ses 28 critères sont estimés
par des proxys documentés (simulation, concentration des sources, délais et
contexte public). Le statut `estimation proxy` et la confiance empêchent toute
confusion avec un audit ; les réponses d'un autre fournisseur ne sont jamais
recopiées.

Le sélecteur et les fiches n'affichent que les matricules `SDC-VD...`. Les noms,
adresses et raisons sociales utilisés pour la recherche documentaire ne sont pas
présentés dans l'interface.

Les faits documentaires retenus sont conservés dans
`etudecas/data/source/supplier_public_evidence.csv`. Chaque ligne est rattachée
au seul matricule et précise le type de signal, la date, la portée (site, entité,
groupe ou réseau), le niveau de confiance, le statut de vérification, une synthèse
anonymisée et la référence source. Les URL restent dans ce registre interne et
ne sont ni embarquées ni affichées dans la carte. L'absence de fait retenu n'est
jamais interprétée comme une absence d'incident.

Le sélecteur `Audit fournisseur` permet d'ouvrir directement les 29 fiches, y
compris celles des fournisseurs sans coordonnées et donc sans marqueur sur la carte.

Pour ajouter les audits restants, placer un classeur renseigné par fournisseur
dans ce dossier avec son identifiant `VD...`. Un fichier ou un autre dossier peut
aussi être fourni avec `--supplier-audit-xlsx`; une valeur vide désactive la
source. Chaque classeur doit avoir été recalculé et enregistré dans Excel, car le
lecteur utilise les résultats de formules mis en cache dans le XLSX.
