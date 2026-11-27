# Premier inventaire au 27 novembre 2026

L’instantané porte sur les cinq branches distantes présentes avant la création de la branche du harnais. Le scan couvre 8 877 entrées de branche, soit 2 811 chemins distincts et 3 177 couples chemin/version. Le registre initial qualifie 16 capacités. Sept disposent d’une sortie archivée, huit ont été vérifiées dans le code et une est documentée. Les simulations industrielles restent à rejouer.

| Branche | Révision | Entrées |
|---|---|---:|
| `codex/article-cascade-pilot-20261104` | `REV-0332` | 1658 |
| `dev_P0002` | `REV-0251` | 1207 |
| `dev_P0001` | `REV-0414` | 1824 |
| `main` | `REV-0299` | 1982 |
| `partage/cahiers-ic-anonymes` | `REV-0425` | 2206 |

## Méthodes

Le moteur a recherché 43 familles et trouvé des indices pour 41. Les fiches peuvent traiter une famille ou expliquer la limite d’une méthode citée. Le tableau donne les identifiants des fiches que l’on peut passer à l’option `--focus`.

| Famille recherchée | Indice automatique | Fiches relues |
|---|---|---|
| Calcul des besoins nets (MRP) | Oui | mrp-date |
| Explosion et bilan de nomenclature | Oui | mrp-date |
| Lotissement et contraintes de lot | Oui | mrp-date |
| Dimensionnement des stocks et de la sécurité | Oui | politiques-stock-service, stock-retard-52s |
| Capacité, charge et goulets | Oui | allocation-sites |
| Traçabilité et généalogie des lots | Oui | trace-lots |
| Taux de service et retards clients | Oui | politiques-stock-service, stock-retard-52s, trace-lots, cascade-pilote, pareto-cout-service-carbone |
| Délais, calendriers et disponibilité | Oui | mrp-date |
| Cartographie des flux et fournisseurs multi-rangs | Oui | flux-transport |
| Modes de transport, substitution et expédition | Oui | stock-retard-52s, flux-transport |
| Prévision et signaux fournisseurs | Oui | risque-fournisseur-calibre |
| Calibration et validation sur observations | Oui | risque-fournisseur-calibre |
| Prédiction conforme et couverture | Oui | À instruire |
| Simulation Monte-Carlo | Oui | incertitude-appariee, regulation-pid, risque-action-robuste |
| Sensibilité et facteurs d’influence | Oui | incertitude-appariee |
| Stress tests, chocs et scénarios de rupture | Oui | stock-retard-52s, cascade-pilote |
| Cascades et propagation des perturbations | Oui | cascade-pilote |
| Mesures et trajectoires de résilience | Oui | stock-retard-52s, risque-action-robuste |
| Simulation à événements discrets | Oui | dynamique-frequence |
| Dynamique des systèmes et stocks-flux | Oui | dynamique-frequence |
| Simulation hybride | Oui | À instruire |
| Régulation en boucle fermée | Oui | regulation-pid, risque-action-robuste |
| Régulation PID | Oui | regulation-pid |
| Commande quadratique linéaire | Oui | À instruire |
| Commande robuste H∞ | Oui | À instruire |
| Commande prédictive (MPC) | Oui | À instruire |
| Identification et analyse fréquentielle | Oui | dynamique-frequence |
| Programmation mathématique des décisions | Oui | allocation-sites |
| Arbitrage multicritère et front de Pareto | Oui | pareto-cout-service-carbone |
| Analyse du cycle de vie et inventaires | Oui | sddlca-52s, brightway-echanges |
| ACV dynamique et caractérisation temporelle | Oui | sddlca-52s, adaptation-20ans |
| ACV dynamique dépendante de l’état | Oui | sddlca-52s, adaptation-20ans, brightway-echanges |
| Adaptation et scénarios climatiques | Oui | adaptation-20ans |
| Allègement et impacts en phase d’usage | Oui | À instruire |
| Alternatives fournisseurs et localisation | Oui | À instruire |
| Coûts des décisions et de mitigation | Oui | allocation-sites, pareto-cout-service-carbone |
| Attribution causale et comparaison contrefactuelle | Oui | trace-lots |
| Programmation par contraintes et ordonnancement | Oui | À instruire |
| Analyse entrées-sorties multirégionale | Aucun repéré | À instruire |
| Simulation à base d’agents | Aucun repéré | À instruire |
| Criticité et évaluation fournisseurs | Oui | risque-fournisseur-calibre |
| Classement et sélection d’actions de mitigation | Oui | risque-action-robuste, pareto-cout-service-carbone |
| Plan d’expériences et comparaison de politiques | Oui | politiques-stock-service, pareto-cout-service-carbone |

## Outils et dépendances

Le scan repère 160 noms candidats. Une déclaration peut provenir d’un environnement figé et un import peut appartenir à un exemple. Pour qualifier un usage, retrouver le chemin, la fonction appelée et le scénario dans les résultats de la commande de scan.

### Déclarés et importés (20)

`geopy` · `ipython` · `matplotlib` · `networkx` · `numpy` · `openpyxl` · `pandas` · `plotly` · `psutil` · `pulp` · `pytest` · `pyyaml` · `requests` · `scikit-learn` · `scipy` · `seaborn` · `simpy` · `sqlalchemy` · `streamlit` · `sympy`

### Imports uniquement (12)

`brightway2` · `brightway25` · `bw2analyzer` · `bw2calc` · `bw2data` · `bw2io` · `ecoinvent-interface` · `lca-algebraic` · `playwright` · `python-docx` · `python-dotenv` · `supply`

### Déclarations uniquement (128)

`altair` · `anyio` · `argon2-cffi` · `argon2-cffi-bindings` · `arrow` · `asttokens` · `async-lru` · `attrs` · `babel` · `backcall` · `beautifulsoup4` · `bleach` · `blinker` · `cachetools` · `certifi` · `cffi` · `charset-normalizer` · `click` · `colorama` · `comm` · `contourpy` · `cycler` · `debugpy` · `decorator` · `defusedxml` · `docopt` · `et-xmlfile` · `executing` · `fastjsonschema` · `filelock` · `fonttools` · `fqdn` · `fsspec` · `geographiclib` · `gitdb` · `gitpython` · `greenlet` · `h11` · `httpcore` · `httpx` · `idna` · `ipykernel` · `ipython-pygments-lexers` · `isoduration` · `jedi` · `jinja2` · `joblib` · `json5` · `jsonpointer` · `jsonschema` · `jsonschema-specifications` · `jupyter-client` · `jupyter-core` · `jupyter-events` · `jupyter-lsp` · `jupyter-server` · `jupyter-server-mathjax` · `jupyter-server-terminals` · `jupyterlab` · `jupyterlab-git` · `jupyterlab-pygments` · `jupyterlab-server` · `kiwisolver` · `lark` · `markupsafe` · `matplotlib-inline` · `mistune` · `mpmath` · `narwhals` · `nbclient` · `nbconvert` · `nbdime` · `nbformat` · `nest-asyncio` · `notebook-shim` · `packaging` · `pandocfilters` · `parso` · `pexpect` · `pickleshare` · `pillow` · `pipreqs` · `platformdirs` · `prometheus-client` · `prompt-toolkit` · `protobuf` · `ptyprocess` · `pure-eval` · `pyarrow` · `pycparser` · `pydeck` · `pygments` · `pyparsing` · `python-dateutil` · `python-json-logger` · `pytz` · `pyzmq` · `referencing` · `rfc3339-validator` · `rfc3986-validator` · `rfc3987-syntax` · `rpds-py` · `ruff` · `send2trash` · `setuptools` · `six` · `smmap` · `sniffio` · `soupsieve` · `stack-data` · `tenacity` · `terminado` · `threadpoolctl` · `tinycss2` · `toml` · `torch` · `tornado` · `traitlets` · `typing-extensions` · `tzdata` · `uri-template` · `urllib3` · `watchdog` · `wcwidth` · `webcolors` · `webencodings` · `websocket-client` · `yarg`

## Manques prioritaires et prochains essais

- **Reproduire les écarts carbone au même horizon** (haute). Recalculer la trajectoire de référence et retrouver les trois totaux archivés avec les mêmes paramètres.
- **Tester la propagation jusqu’au service client** (haute). Comparer les calendriers sur plusieurs graines, identifier les réceptions retardées puis tester l’effet sur le service à échéance.
- **Qualifier les méthodes de commande citées** (moyenne). Examiner les équations de synthèse, le modèle et les contraintes des autres modules avant de qualifier le portefeuille LQR ou H∞.
- **Relier la règle de lot au niveau de service** (haute). Faire varier le tampon à besoins datés fixes. Mesurer séparément couverture hebdomadaire, ponctualité par commande et capital immobilisé.
- **Tester conjointement la fiabilité de l’alerte et la valeur de l’action** (haute). Sur une période tenue à part, comparer les actions avec et sans signal à stock initial identique. Mesurer calibration, coûts et service.

Les [fiches complètes](catalog.json) contiennent les preuves au commit, les limites, les séries chiffrées et les projections externes. Pour actualiser le panorama et identifier les chemins divergents, suivre le [guide d’exécution](README.md).
