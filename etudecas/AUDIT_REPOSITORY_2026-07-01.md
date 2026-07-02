# Audit etudecas - organisation, donnees, simulation et prochaines optimisations

Date: 2026-07-01  
Racine analysee: `C:\dev\lca-simu`  
Mode: audit local + agents specialises simulation, lotification, carte/payload, donnees/knowledge graph.

## Synthese

Le projet est maintenant dans un etat exploitable pour continuer: les gros artefacts inutiles ont ete nettoyes, les tests principaux passent, la lotification est devenue une vraie brique metier, et le format Excel -> JSON -> graphe enrichi existe. Le probleme principal n'est plus la faisabilite, mais l'ordre du code et des contrats.

L'objectif cible doit etre:

1. partir d'une source de donnees claire: Excel/JSON metier;
2. produire un graphe de connaissance versionne;
3. enrichir ce graphe par scripts reproductibles;
4. lancer une simulation via une API stable;
5. produire des artefacts compacts et manifests;
6. afficher les resultats sans embarquer toute la complexite metier dans la carte HTML.

## Etat chiffre actuel

Etat courant de `etudecas` apres nettoyage:

| Zone | Fichiers | Taille |
| --- | ---: | ---: |
| `etudecas` complet | 731 | 512.76 MB |
| `simulation` | 577 | 494.09 MB |
| `simulation/result` | 269 | 477.73 MB |
| `simulation/sensibility` | 231 | 3.86 MB |
| `archive/worstcase` | 43 | 6.73 MB |
| `risk/supplier_criticality` | 8 | 5.30 MB |
| `supplier_risk_kpi` wrapper | 2 | ~0 MB |
| `simulation_prep` | 27 | 2.60 MB |
| `prototypes/prediction` | 16 | 1.80 MB |
| `visualization` | 13 | 1.47 MB |
| `data` | 17 | ~0.39 MB |

Les plus gros artefacts restants sont les traces de simulation 5 ans:

- `mrp_trace_daily.csv`: environ 28.6 a 28.9 MB par run complet;
- `production_lot_events.csv`: environ 13.2 a 13.4 MB;
- `production_lot_genealogy.csv`: environ 8.0 MB;
- carte interactive courante: environ 9.8 MB;
- payload compact de comparaison risques: environ 6.7 MB.

Les runs lourds restants dans `simulation/result` sont encore redondants:

| Run | Taille |
| --- | ---: |
| `_codex_lot_trace_5y_risk_portfolio` | 86.62 MB |
| `_codex_lot_trace_5y_state_risks` | 75.61 MB |
| `_codex_lot_trace_5y_safe` | 75.31 MB |
| `mrp_bom_test_weekly...state_dependent_risk_test` | 58.63 MB |
| `mrp_bom_test_weekly...non_state_risks_test` | 58.25 MB |
| `mrp_bom_test_weekly...multisource_portfolio_test` | 58.22 MB |
| `mrp_bom_test_weekly...cost_risk_portfolio_test` | 58.21 MB |
| `risk_amplitude_duration_sweep_5y` | 6.88 MB |

Conclusion: le nettoyage a fonctionne, mais il faut encore decider combien de runs complets on garde localement. Pour un repo de developpement, un seul run canonique complet + un ou deux fixtures reduits suffisent. La brique fournisseur canonique est maintenant `risk/supplier_criticality`; `supplier_risk_kpi` ne reste qu'un wrapper de compatibilite.

## Bons points

### Donnees et graphe de connaissance

- Le fichier `config/cases/data_poc_enrichment_input.xlsx` est coherent avec le template `knowledge_graph/excel_template.py`.
- Le flux Excel -> JSON -> graphe enrichi est en place.
- `data_poc.json` porte deja des informations qui doivent rester metier: alias, labels, notes item, logistique, overrides, profils de cout.
- Les graphes de `simulation_prep/result` passent le validateur actuel.

### Simulation

- Une API existe: `simulation/engine/api.py` expose `simulate(...)`.
- Les contrats de base sont separes dans `simulation/engine/contracts.py`.
- Les tests de simulation passent via `unittest`.
- Les risques state-dependent, la sensibilite et la comparaison de scenarios ont une base fonctionnelle.

### Lotification

- Le ledger est devenu une source canonique: lots, evenements, liens parent/enfant.
- `simulation/lot_trace` est la zone la mieux decoupee: `io`, `schema`, `indexes`, `payload`, `view_model`, `campaigns`.
- Les lots de transport techniques ne sont plus proposes comme lots selectionnables metier.
- Les reports de production sont modelisables comme objets non physiques.
- Le diagramme peut maintenant representer les noeuds supply, transports, lots mixtes et flux amont/aval.

### Visualisation

- Les wrappers historiques pointent maintenant vers les implementations canoniques.
- Les outils de payload existent: externalisation, compression, chunking.
- La carte compacte actuelle est beaucoup plus legere que les anciennes cartes de 100+ MB.

## Problemes principaux

### P0 - Deux monolithes structurants

`visualization/maps/build_supplychain_worldmap.py` fait environ 30 155 lignes. Il melange:

- lecture de resultats;
- construction de payloads;
- KPI;
- risques;
- sensibilite;
- lot trace;
- template HTML/CSS/JS;
- rendu Plotly;
- post-traitement de payload.

`simulation/engine/run_first_simulation.py` fait environ 9 299 lignes. Il melange:

- boucle simulation;
- MRP;
- replanification;
- sizing lots;
- production;
- ledger de lots;
- risques fournisseurs;
- couts;
- exports CSV;
- rapports;
- generation carte.

Ces deux fichiers sont le principal frein a la suite. Tout peut marcher, mais chaque evolution coute trop cher et peut casser une autre zone.

### P0 - Contrats de donnees pas assez verrouilles

Le contrat `knowledge_graph` annonce `etudecas.supply_graph.v1`, mais plusieurs graphes produits portent encore `schema_version: "0.3"`. Le validateur est utile, mais permissif: il valide la forme generale, pas encore assez les unites, chemins, geocodage, provenance, case_config, scenarios et hypotheses de simulation.

Il reste aussi des artefacts avec chemins absolus historiques ou encodage imparfait. Ce n'est pas critique pour la simulation courante, mais c'est un risque de reproductibilite.

### P0 - Outputs encore trop proches du code

`simulation/result` pese encore environ 478 MB. Ce n'est plus absurde, mais c'est encore trop pour un repo source si on regenere souvent. Il faut distinguer:

- fixtures de test;
- run canonique courant pour l'interface;
- rapports compacts;
- artefacts regenerables a ne pas conserver;
- archives externes.

### P1 - Lot trace: logique dupliquee entre Python et JS

Le backend sait construire des view models, mais le JS reconstruit encore une partie des index et du rendu. Il faut choisir une regle:

- soit Python produit les view models metier complets et le JS affiche;
- soit le JS calcule vraiment les vues, mais alors il faut des tests de contrat.

La meilleure option pour ce projet: Python doit produire le payload metier canonique, le HTML doit rester un client interactif.

### P1 - Sensibilite: deux generations coexistent

On a a la fois:

- `simulation/sensibility/*`: scripts historiques riches;
- `simulation/experiments/sensitivity/*`: contrat plus propre et generique.

Il faut migrer progressivement les anciens runners vers le nouveau contrat, sans perdre les capacites utiles: overrides par fournisseur/noeud/item, risques state-dependent, campagnes multi-scenarios, scoring metier.

### P1 - Tests encore incomplets sur les regles critiques

Les tests existants sont utiles, mais les regles suivantes doivent etre verrouillees:

- MRP/replanification: review period, safety floor, cutover, target bucket;
- lot sizing et limite hebdomadaire de lots;
- reports de production et rattrapage;
- stock reconciliation;
- lots mixtes et contributions;
- transports avec perte/rendement;
- payload map minimal et securite d'injection JSON.

### P1 - CI et documentation de retention a stabiliser

Il n'y a pas encore de workflow CI racine ni de `pyproject.toml` racine. La commande fiable aujourd'hui est:

```powershell
python -B -m unittest discover -s etudecas -p "test*.py" -v
```

Les tests lents 5 ans doivent rester separes de la CI rapide. Ils doivent etre lances en nightly/manual avec `ETUDECAS_RUN_SLOW_TESTS=1`, un timeout adapte et des fixtures reduits si possible.

Deux documentations historiques doivent etre remises en ligne avec la politique actuelle:

- `simulation/sensibility/README.md`: decrit encore des dossiers `cases/*/simulation_output/*` alors que la retention par defaut est `summary`.
- `simulation/result/README_ORGANISATION.md`: reference des structures historiques qui ne representent plus l'etat courant.

Le pack multi-agent depend de `pytest`, mais l'environnement courant ne l'a pas. Pour `etudecas` principal, `unittest` suffit actuellement.

## Structure cible recommandee

Organisation cible sans tout casser d'un coup:

```text
etudecas/
  config/
    cases/
    sensitivity/
  data/
    source/              # fichiers metier source et graphe de base
    geocoded/            # graphe geocode et rapports
    reports/             # rapports d'enrichissement
  knowledge_graph/
    schema.py
    excel_io.py
    enrichers.py
    validators.py
  simulation/
    engine/
      api.py
      contracts.py
      state.py
      mrp.py
      production.py
      logistics.py
      risks.py
      outputs.py
    lot_trace/
      graph.py
      schema.py
      io.py
      indexes.py
      view_model.py
      payload.py
      audit.py
    experiments/
      sensitivity/
      scenarios/
    analysis/
    result/              # seulement run courant + payloads compacts
  visualization/
    maps/
      builders/
      panels/
      assets/
      payloads/
  reports/
  tests/
```

Remarque: les dossiers historiques `SC_analysis`, `SC_first_analysis`, `worstcase`, `Prediction` et `affichage_result` ont ete classes sous `analysis/`, `prototypes/` et `archive/`. Les anciens dossiers actifs `donnees`, `scripts_geocodage` et `result_geocodage` ont ete migres vers `data/source`, `data/geocoded`, `data/reports` et `geocoding`. Le dossier `donnees/` ne reste que parce que `Extract_En_cours.xlsx` est verrouille par un processus externe; la copie canonique est dans `data/source/`.

- source de donnees;
- analyse historique;
- prototype;
- outil encore actif;
- archive regenerable.

## Plan d'action

### Etape 1 - Stabiliser les contrats

1. Aligner `schema_version` des graphes.
2. Ajouter un manifest par run: input graph, config, hash, horizon, options, date, retention.
3. Renforcer le validateur: unites, case_config, geocodage, edges, scenarios, chemins relatifs.
4. Documenter le contrat "Excel enrichi -> JSON -> graphe simulation".
5. Corriger les chemins absolus historiques et les encodages imparfaits dans les artefacts conserves.

### Etape 2 - Nettoyer les artefacts sans perdre le point courant

1. Garder un run courant complet: `_codex_lot_trace_5y_risk_portfolio`.
2. Transformer les autres runs 5 ans en summaries ou les supprimer si regenerables.
3. Garder `risk_amplitude_duration_sweep_5y/scenario_comparison_payload_compact.json`.
4. Ajouter une politique stricte: les nouveaux runs vont dans un dossier ignore ou sont compacts.
5. Mettre a jour les README historiques pour ne plus encourager le stockage de runs complets.

### Etape 3 - Extraire le moteur simulation

Ordre de refactor conseille:

1. `outputs.py`: ecriture CSV, manifests, rapports.
2. `risks.py`: state-dependent events, application fournisseur.
3. `lot_policy.py`: tailles de lots, minimum commande, limites de campagnes.
4. `mrp.py`: calcul besoins, target, replanification.
5. `production.py`: consommation BOM, production, reports/rattrapage.

Chaque extraction doit etre accompagnee de tests unitaires sur un mini graphe.

### Etape 4 - Finaliser lot trace generique

1. Extraire un `LotTraceGraph` pur.
2. Unifier les alias de direction: `all/both`, `upstream/ancestors`, `downstream/descendants`.
3. Definir explicitement:
   - `parent_qty`: quantite consommee ou expediee;
   - `child_qty`: quantite creee ou recue;
   - `contribution_qty`: part tracable dans le lot enfant.
4. Transformer `audit_lot_paths.py` en bibliotheque reutilisable.
5. Faire produire au backend les view models metier; le JS affiche seulement.

### Etape 5 - Refaire la carte en client de payload

1. Securiser l'injection JSON dans le HTML (`</script>`).
2. Separer builders de payload et template UI.
3. Garder trois modes:
   - HTML autonome compact pour demo;
   - HTML + payload externe pour gros runs;
   - futur API locale pour what-if dynamique.
4. Rendre le chunking vraiment lazy: charger le detail lot, risques et sensibilite uniquement quand l'utilisateur ouvre le panneau.

### Etape 6 - Unifier la sensibilite

1. Faire de `simulation/experiments/sensitivity` le contrat unique.
2. Migrer les scripts `sensibility` historiques en wrappers ou recipes.
3. Stocker les resultats en format compact: `registry`, `metrics`, `summary`, courbes agregees.
4. Ne plus stocker tous les CSV de simulation par scenario, sauf cas de debug explicite.

### Etape 7 - Ajouter une validation de developpement

1. Ajouter une commande CI rapide officielle basee sur `unittest`.
2. Ajouter une commande CI lente optionnelle pour simulation 5 ans, lot audit et build map compact.
3. Documenter `pytest` comme dependance du pack multi-agent seulement, ou l'ajouter explicitement si on veut le lancer avec le repo principal.
4. Ajouter un smoke test de generation map minimale et de payload chunked.

## Recommandation metier pour la suite lotification

Le suivi de lots doit rester lisible et non exhaustif par defaut:

- liste selectionnable: lots physiques metier seulement, d'abord PF, puis PFI, puis MP;
- transports visibles dans le diagramme, mais non selectionnables;
- chaine complete: fournisseur -> transport fournisseur -> stock entree usine -> production -> stock PF usine -> transport usine/DC -> stock DC -> transport client -> client;
- lots mixtes: afficher la contribution du lot selectionne et l'autre source principale;
- reports: afficher l'ordre non produit, la cause, puis le lot de rattrapage associe;
- courbes temporelles: afficher uniquement les marqueurs du lot au bon endroit, pas des marqueurs globaux repetes partout.

## Recommandation developpement

Ne pas faire une grosse reorganisation en une seule fois. La bonne strategie est:

1. creer les modules cibles;
2. extraire une responsabilite a la fois;
3. garder les anciens scripts comme wrappers;
4. ajouter des tests de contrat;
5. regenerer la carte canonique;
6. supprimer l'ancien code seulement quand le wrapper et les tests prouvent l'equivalence.

La prochaine action concrete la plus rentable est:

1. extraire `LotTraceGraph` et les aliases de direction;
2. ajouter les tests de quantites mixtes/transport;
3. securiser l'injection JSON de la map;
4. ajouter un manifest de run canonique;
5. supprimer ou compacter les runs 5 ans redondants restants.

## Verification

Commandes de reference recentes:

- `python -m unittest discover -s etudecas -p "test*.py"`: 46 tests OK, 2 skipped.
- `python -m unittest discover -s etudecas\simulation -p "test_*.py"`: 34 tests OK, 2 skipped.
- tests lot trace cibles: 20 tests OK, 2 skipped.
- compilation du pack multi-agent: 29 fichiers compiles.

`pytest` n'est pas installe dans l'environnement courant.
