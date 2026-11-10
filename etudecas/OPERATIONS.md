# Etudecas — commandes et effets

[Comprendre le code et les dossiers](README.md) · [Documentation par sujet](docs/README.md)

Ce guide sert à choisir une commande et à savoir ce qu'elle lit ou produit.
Les commandes se lancent depuis la racine du dépôt, qui contient `etudecas/`.

## Choisir une commande

| Besoin | Commande ou entrée | Effet |
|---|---|---|
| Comprendre l'organisation | [README.md](README.md) | Lecture du guide ; aucune exécution nécessaire. |
| Voir les commandes disponibles | `python etudecas/run_etudecas_pipeline.py --help` | Affiche l'aide. |
| Vérifier les fichiers et dépendances du pipeline | `python etudecas/run_etudecas_pipeline.py doctor` | Diagnostic ; ne lance pas la simulation. |
| Contrôler la documentation liée au code | `python -m etudecas.documentation check-all` | Contrôle les registres sans régénération. |
| Consulter une carte existante | [Accueil des résultats](index.html) | Ouvre les fichiers déjà produits. |
| Construire le graphe depuis les données source | `python etudecas/run_etudecas_pipeline.py graph` | Écrit le graphe enrichi et géocodé. |
| Préparer les entrées du moteur | `python etudecas/run_etudecas_pipeline.py prepare` | Écrit un graphe préparé ; ne correspond pas à toute la chaîne de reconstruction. |
| Projeter le MRP conservé sur cinq ans | `python -B -m etudecas.regenerate --reference current --days 1825 --with-map` | Nominal W prolongé par des hypothèses explicites ; nouvelle carte et deux suivis de lots. |
| Reproduire le nominal historique de septembre | `python -m etudecas.regenerate --reference historical_20260920 --scenario nominal` | Ancienne configuration sur 1 825 jours ; ne reprend pas W. |
| Refaire la livraison historique avec lots et comparaisons | `python -m etudecas.regenerate --reference historical_20260920 --delivery lots` | Quatre calculs historiques, carte et diagnostic ; [périmètre exact](docs/REGENERER_RESULTATS.md). |
| Choisir une étude | `python -m etudecas.simulation.studies --help` | Sensibilité, rejeux, incertitude temporelle, cascades et études fournisseurs ; chaque mode garde ses règles et ses options. |
| Chercher les seuils d'effet par paramètre | `python -B -m etudecas.simulation.sensibility.run_adaptive_sensitivity --help` | Recherche bornée à la hausse et à la baisse ; vérifie d'abord que les trois indicateurs sont mesurables. |
| Recalculer et produire une carte | `python etudecas/run_etudecas_pipeline.py rebuild-map-5y` | Lance des calculs et crée un dossier de résultats ; détails ci-dessous. |

`rebuild-map-5y` utilise par défaut un graphe **déjà préparé** ; il ne rejoue
pas l'import des Excel. L'option `--refresh-input-graph` demande de reconstruire
son entrée. `graph`, `prepare`, `reference` et `all` couvrent les
étapes de construction correspondantes. Lire l'aide du sous-programme avant
de choisir une reconstruction. Le lanceur `launch_interactive_map.py` ouvre
un HTML existant avec l'API locale ; il n'est pas un constructeur de carte.

Les exemples de reconstruction qui suivent sont des opérations à lancer
volontairement, pas des étapes nécessaires pour lire le code.

Les modes d'étude sont `sensitivity`, `targeted`, `paired`, `temporal`,
`cascade`, `supplier-configurations`, `supplier-calibration` et
`supplier-campaign`. Commencer par l'aide du mode retenu, par exemple
`python -m etudecas.simulation.studies cascade --help` ; ses données et
prérequis restent explicites. La [procédure de vérification](docs/TEST_VALIDATION.md)
décrit la sélection des contrôles à effectuer après une modification.

## Recalculer la carte complète avec le MRP courant

```powershell
python -B -m etudecas.simulation.complete_campaign --plan-only
python -B -m etudecas.simulation.complete_campaign --progress-maps
# Reprendre les étapes terminées et les checkpoints analytiques compatibles
python -B -m etudecas.simulation.complete_campaign --resume --progress-maps
```

Ce parcours utilise `coherent-MRP-20261014` et son runtime de réconciliation
et projection pour tous les calculs. Il produit un nouveau nominal avec lots
et audit, cinq compagnons de risques avec réactions dépendant de l'état,
leurs registres incident–expédition–lots–clients, les sensibilités, la criticité
fournisseur et Monte Carlo, puis assemble leurs résultats dans la même carte.
Il ne réutilise pas les campagnes historiques comme résultats de substitution.
Les commandes d'achat initiales datées gardent leurs quantités et dates source
dans ces comparaisons ; l'application des risques à ces commandes initiales
reste un mécanisme distinct, non activé par ce parcours.
Les variantes de stock modifient uniquement le stock libre utilisable initial
du fournisseur ou du site de fabrication visé. Les quantités bloquées et leurs
dates source sont conservées ; les articles en unités restent entiers après
application du facteur. Ces quantités de variante sont signalées comme hypothèses.
Les délais internes liés au contrat de disponibilité source restent fixes.
Les délais fournisseurs paramétrables exprimés en jours entiers sont arrondis
au jour supérieur ; le facteur demandé, l'effet appliqué et les exclusions sont tracés.

Le plan par défaut comporte 388 calculs de 1 825 jours : un nominal, cinq
risques, 181 cas de sensibilité pour huit fournisseurs éligibles et 200 tirages
Monte Carlo plus leur baseline. Le profil `workshop`, la graine 42 et un seul
worker sont explicites ; la propagation appariée supplémentaire est désactivée.
Le nombre de sensibilités est adapté si moins de huit fournisseurs sont éligibles.
Les seuils de risque et distributions d'incertitude restent des hypothèses de
scénario ; ils ne sont pas des probabilités industrielles démontrées.

`--output-dir`, `--map-output`, `--stop-after`, `--max-wall-minutes` et les limites
de stockage sont vérifiés entre les étapes, sans interrompre un calcul natif
déjà engagé. Les checkpoints distinguent les
étapes déclarées, en cours, terminées et échouées. Une erreur ou un refus
d'écriture ne déclenche pas de relance aveugle. Ne pas modifier les sources
pendant une campagne : la reprise vérifie leur identité.

`--progress-maps` publie des cartes intermédiaires explicitement marquées en
cours ; les analyses non encore calculées y restent absentes. La carte finale
attend tous les tirages et cas demandés réussis. Une exécution terminée n'est
pas une qualification scientifique. Les références HTML précédentes restent
conservées. L'ancien `rebuild-map-5y` utilise son parcours historique distinct.

## Sensibilité par recherche de seuils

```powershell
python -B -m etudecas.simulation.sensibility.run_adaptive_sensitivity --baseline-manifest CHEMIN_NOMINAL/run_manifest.json --plan-only
python -B -m etudecas.simulation.sensibility.run_adaptive_sensitivity --baseline-manifest CHEMIN_NOMINAL/run_manifest.json --output-dir etudecas/artifacts/testing/NOUVELLE_ETUDE_SEUILS
```

Cette étude parcourt les **19 facteurs globaux** exposés par le moteur, un seul
à la fois, séparément à la hausse et à la baisse. Elle ne couvre pas toutes les
déclinaisons par article, site ou fournisseur. `--parameters` permet de déclarer
un sous-ensemble explicite. Le témoin est recalculé sur le même horizon que les
variantes ; les indicateurs d'un nominal sur cinq ans ne servent pas de témoin
à une variante annuelle.

L'horizon par défaut est de **362 jours**, convention historique 2025 du modèle.
Une fenêtre de 21 jours peut masquer les effets des délais et des stocks.
Les paliers par défaut sont ×0,5, ×0,1, ×0,01 puis, dans l'autre sens, ×2, ×5,
×20. Les bornes, saturations, paramètres effectivement inchangés et budgets
arrêtent la recherche. Une absence d'effet dans ce périmètre ne prouve pas une
insensibilité générale ; aucune monotonie globale n'est supposée.

Les trois indicateurs sont suivis séparément :

- réponse client `quantity_service_rate` : quantité servie divisée par la demande
  cumulée et l'arriéré initial, compté une seule fois. La version 2 de l'étude
  utilise explicitement ce critère, distinct du stock disponible et de la
  ponctualité ;
- taux de révision du programme prévisionnel de fabrication simulé : changements
  de quantité ou de calendrier rapportés aux publications actives comparables ;
  il ne mesure pas les révisions industrielles d'ordres de fabrication ;
- coût du stock valorisé : `total_holding_cost`, capital immobilisé sur les
  couples valorisés, distinct du coût total et de l'exploitation des entrepôts.

Les seuils d'effet par défaut valent **0,1 point de pourcentage** pour chaque
taux et **1 %** du coût témoin, avec un plancher d'une unité monétaire. Une hausse
ou une baisse compte comme effet et conserve son signe. Un effet sur le coût
seul ne vaut pas réussite sur les trois indicateurs.

Le critère historique `product_availability`, part des journées client/article
entièrement servies, retards inclus, reste affiché en diagnostic secondaire.
Un taux de journées entièrement servies nul peut coexister avec des livraisons
importantes : tant qu'un arriéré demeure, la journée échoue à ce critère binaire.
Présenter séparément la part de demande servie en quantité et le retard final.
Cette part divise la quantité servie par la demande cumulée plus l'arriéré
initial de la fenêtre ; elle inclut les rattrapages et ne mesure pas la
ponctualité. La disponibilité physique se lit dans les stocks utilisables du
site concerné, pas dans ce compteur de service client. Un critère déjà à zéro
ne peut plus baisser : il ne suffit pas pour étudier toute dégradation.

Si l'ancien nominal ne contient pas ce journal de programme, le runner recalcule
une seule fois un témoin avec le code courant et l'horizon demandé. Il refuse
ensuite les variantes si un indicateur requis reste inconnu.
`--allow-partial-indicators` autorise une exploration explicitement
partielle ; elle ne valide jamais l'objectif des trois indicateurs. Les budgets
par défaut sont 115 calculs, 48 heures et 20 GiB, vérifiés entre les cas, avec un
seul calcul à la fois. Choisir un nouveau dossier de résultats ; le nominal et
les anciens rapports restent conservés.

La progression et les trois mesures sont enregistrées après chaque cas terminé.
Les exports moteur restent compacts, avec conservation des stocks, campagnes,
journaux, événements et généalogies de lots produits par ce profil. Cela suffit
au contrôle ciblé des trois mesures ; le registre détaillé de consommation
matière n'est pas exporté et la qualification complète des bilans matière ne
peut pas être déclarée sur ces seuls fichiers. `--resume --output-dir
DOSSIER` ne reprend qu'un arrêt de budget entre deux cas terminés : même version
2, paramètres, horizon, critères, sources, entrées et empreintes CSV. Les budgets
peuvent être augmentés explicitement ; le temps cumulé est conservé. Un cas
partiel, un échec natif ou un refus de sécurité interdit cette reprise.

Une recherche achevée ne garantit pas un effet sur les trois indicateurs pour
chaque paramètre : un coût de stockage seul doit changer le coût, sans changer
les flux. D'autres coûts ne ciblent pas directement l'immobilisation. Une cible
PF nominale à zéro reste zéro après multiplication ; une période de revue d'un
jour et une fiabilité déjà à 100 % peuvent atteindre leurs bornes. Ces cas sont
distincts d'une mesure manquante ou d'un arrêt de budget. `all_three_satisfied`
décrit uniquement les effets détectés, pas une validation globale du modèle.

### Mesure des révisions de production

Le moteur publie en fin de journée le programme de lancement par site, article
et semaine absolue du lundi au dimanche. Chaque publication conserve ses dates,
sa version et sa couverture. Pour un même programme et une même couverture :

`taux = nombre de comparaisons avec quantité OU calendrier modifié / nombre de comparaisons actives identifiées`.

Une comparaison rapproche deux publications quotidiennes consécutives. Elle
est active si au moins l'une des deux contient une quantité positive. La
première publication positive crée le programme et ne compte pas comme une
révision. Une annulation ultérieure compte ; une simple exécution ne compte
pas : la quantité complète de chaque campagne est conservée une fois après
son engagement. Dans le nominal actuel, cet engagement correspond à la création
de campagne et peut précéder le premier travail physique ; il ne prouve aucune
consommation. Sa base est `simulated_weekly_launch_programme_authorization_v1`.
Le mode optionnel d'engagement au premier travail physique utilise la base
distincte `simulated_weekly_launch_programme_v1`. Ne pas classer ensemble des
taux de bases différentes. Les ordres fermes initiaux restent séparés.
Les recommandations en retard gardent leur date absolue d'origine ; le suivi
ne les déplace pas artificiellement au lendemain.

La mesure compte des comparaisons de programmes, sans additionner KG et UN.
Le taux est compris entre 0 et 100 %. Un dénominateur nul, un journal incomplet
ou une couverture non établie donnent une valeur inconnue, jamais zéro par
défaut. Les passages physiques et les attentes de matière ne servent pas de
dénominateur ou de substitut.

Preuves natives : `data/production_programme_snapshots.csv`, contrat
`production_programme_revisions` et champs `production_replanning_*` du résumé.
Le journal est activé par défaut pour l'exécution datée compatible, sans
préchauffage ; `--no-production-programme-revision-journal` permet un
témoin sans suivi. Les sensibilités conservent ce CSV même en mode résumé.
Pour auditer les tirages Monte Carlo, conserver les sorties avec l'option
`--keep-run-artifacts` ; les seuls KPI numériques ne remplacent pas le journal.
Ces observations simulées ne démontrent pas la fidélité au planning industriel.

## Installation Minimale

Depuis la racine du repo :

```powershell
python -m pip install -r requirements-etudecas.txt
```

`requirements.txt` reste disponible pour les notebooks et prototypes, mais il est beaucoup plus large.

## Diagnostic

```powershell
python etudecas/run_etudecas_pipeline.py doctor
```

Le diagnostic verifie :

- les fichiers metier dans `etudecas/data/source/` ;
- les scripts principaux ;
- le graphe actif lotifie retenu ;
- les modules Python necessaires au pipeline.

## Reconstruction Complete Active

Commande canonique :

```powershell
python etudecas/run_etudecas_pipeline.py rebuild-map-5y --open-map
```

`rebuild-active` reste un alias compatible.

La commande canonique exige Monte Carlo par défaut : 200 exécutions pour la
phase finale du profil retenu, précédées d'exécutions de sélection et, par
défaut, d'une campagne de sensibilité fournisseur. Ce nombre n'est donc pas
le total des calculs de la commande.
Pour produire explicitement une carte sans analyse d'incertitude, utiliser
`--no-require-montecarlo`. La livraison du 18 septembre 2026, conservée dans les
[archives](archive/README.md), documente ce périmètre et ses contrôles historiques.

Equivalent Windows court :

```powershell
.\run_etudecas_active.cmd
```

Par defaut, cette commande :

- lance la simulation active lotifiee sur 5 ans ;
- construit également les scénarios de risque compagnons sélectionnés
  (`--state-dependent-scenarios all` par défaut) ;
- prépare les sensibilités puis la sélection et la phase finale Monte-Carlo,
  lorsque leurs artefacts locaux compatibles doivent être produits ;
- utilise le profil `compact` ;
- reconstruit la criticite fournisseur depuis ce run ;
- genere une carte HTML autonome compressee ;
- exporte un package de run generique dans `run/` ;
- verifie les fichiers principaux, la lotification et la taille de carte ;
- ecrit un rapport de pipeline.

Les resultats sont ecrits dans :

```text
etudecas/simulation/result/_reruns/active_mrp_physical_<timestamp>/
```

Les fichiers importants sont :

- `maps/*.html` : carte autonome ;
- `run/run_manifest.json` : point d'entree generique du run ;
- `run/artifact_index.json` : index logique des CSV/JSON lourds ;
- `run/nodes.json`, `run/flows.json`, `run/kpis.json` : contrat metier compact ;
- `summaries/first_simulation_summary.json` : KPI du run ;
- `reports/first_simulation_report.md` : rapport simulation ;
- `reports/pipeline_report.json` : statut de reconstruction ;
- `data/production_lot_events.csv` et `data/production_lot_genealogy.csv` : suivi de lots ;
- `reports/lot_path_audit.md` : audit des chemins de lots.

## Format De Run Generique

Chaque reconstruction operationnelle produit un dossier `run/` qui sert de
contrat stable pour la suite du projet. La carte peut encore utiliser les CSV
historiques, mais les nouveaux developpements doivent partir de ce package.

Exporter un ancien resultat sans relancer la simulation :

```powershell
python etudecas/run_etudecas_pipeline.py export-run --output-dir "CHEMIN_RESULTAT_EXISTANT" --input-graph "GRAPHE_EXACT_DU_RESULTAT.json"
```

Remplacer ces deux chemins par ceux du résultat concerné et de son manifeste
source. Sans `--input-graph`, la commande prend le graphe actif actuel, qui
peut être différent de celui d'un ancien calcul. Cet export écrit un package.

Valider un package de run :

```powershell
python etudecas/run_etudecas_pipeline.py validate-run --package-dir etudecas/simulation/result/_reruns/<run>/run
```

Le package ne duplique pas les gros CSV par defaut. Il stocke les petits objets
stables (`nodes`, `flows`, `kpis`) et des index vers les series, evenements,
lots, genealogie et diagnostics.

## Dry Run

Pour voir exactement ce qui serait lance sans creer de resultat :

```powershell
python etudecas/run_etudecas_pipeline.py rebuild-map-5y --dry-run
```

## Options Utiles

```powershell
python etudecas/run_etudecas_pipeline.py rebuild-map-5y --days 365
python etudecas/run_etudecas_pipeline.py rebuild-map-5y --output-dir etudecas/simulation/result/_reruns/mon_run --overwrite
python etudecas/run_etudecas_pipeline.py rebuild-map-5y --full-output
python etudecas/run_etudecas_pipeline.py rebuild-map-5y --max-map-mb 50
python etudecas/run_etudecas_pipeline.py rebuild-map-5y --with-montecarlo --montecarlo-runs 60
```

`--full-output` garde les CSV de debug lourds. Le mode standard doit rester `compact`.
`--with-montecarlo` lance une suite adaptative multi-profils et stocke les
resultats dans `<run>/montecarlo/selected/` pour l'onglet Incertitude de la carte.

## Rebuild Depuis Donnees Source

Pour reconstruire les graphes historiques depuis les XLSX :

```powershell
python etudecas/run_etudecas_pipeline.py all --with-5y
```

La commande opérationnelle `rebuild-map-5y` utilise le graphe actif lotifié
retenu et produit une nouvelle carte du calcul lancé. Pour reproduire une
livraison précise, reprendre son graphe et ses paramètres enregistrés ; le
nom de la commande ne garantit pas à lui seul une reproduction identique.
