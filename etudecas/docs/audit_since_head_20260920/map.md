# Revue depuis HEAD — carte, décision et vérificateurs

Référence : `f95b1db6bb233cbf9750fc6ab2fda3943d6e82ab`. Revue du 20 septembre 2026, en lecture seule des sources. Aucune simulation recalculée, aucune correction appliquée. Les nouvelles écritures sont ce rapport et les preuves sous `artifacts/testing/audit_since_head_20260920/map/`.

**Quatre défauts sont confirmés**, dont un échec d’intégration sur la carte effectivement livrée. Les trois autres sont des contre-exemples construits de validation : ils ne démontrent pas une corruption des résultats actuels. Les **275 tests et 3 sous-tests** exécutés passent ; ils ne couvrent pas ces quatre situations.

## Résultats à corriger, par priorité

### MAP-01 — P1 : le parcours de livraison omet les sources exigées par son contrôle des lots

- Source : `etudecas/decision_support.py:322`, contrat dans `etudecas/testing/lot_browser_review.py:106-122`.
- `deliver(..., browser=True)` appelle `review_lots(map_path, output / 'browser-lots')` sans transmettre `run`. Depuis l’introduction de l’oracle CSV, le contrôle de `PBATCH-411EC755D7110AE0` nécessite ce troisième argument. À défaut, `oracle=None`, donc `matched=False`, indépendamment de la qualité réelle de la carte.
- **Reproduction réelle** : ouverture hors ligne de `supply_graph_audited_corrections_20260920.html` par ce même vérificateur, sans `--source-run`. Huit contrôles passent ; le seul échec est `known_lot_customer_conservation_against_csv`, avec `expected_contributions=null`. La carte affiche le lot `LOT-00003038`, deux contributions de **1 835 + 12 565 = 14 400 unités**. L’échec signifie « oracle absent », pas « conservation erronée ».
- Conséquence : la voie de livraison du module décision produit `lot_browser_ok=false`, ajoute une erreur de causalité/affichage et marque la livraison échouée. Le parcours distinct `testing/qualification.py:44` transmet correctement le run ; tous les points d’entrée ne sont donc pas affectés.
- Correction proposée : transmettre explicitement `run`, rendre l’absence de source explicite dans l’API, tester le raccordement du caller avec un oracle différent des valeurs historiques. Le test doit vérifier le troisième argument et une comparaison réelle des contributions, pas seulement le retour simulé d’un mock.
- Preuve : [lot-browser.json](../../artifacts/testing/audit_since_head_20260920/map/missing-source-browser/lot-browser.json), captures conservées dans le même dossier. Le test de livraison complet n’a pas été lancé : il réécrirait des artefacts et pourrait recalculer des actions ; la sous-opération réellement appelée et son branchement ont été vérifiés.

### MAP-02 — P2 : le rafraîchissement matière peut mélanger des unités et scénarios sous une garde de provenance positive

- Source : `etudecas/testing/material_delivery.py:43-55`.
- L’équivalence HTML/CSV des événements signe notamment identifiants, quantité et jour, mais **omet `uom` et `scenario_id`**. Le contexte matière est ensuite reconstruit à partir du CSV et du graphe fourni, sans imposer leur concordance avec le run de la carte.
- **Contre-exemple synthétique exécuté** : la carte contient `E1/L1`, article `RM`, quantité 100, unité `UN`, scénario `BASE`. Le CSV fourni garde les champs signés mais remplace l’unité par `KG` et le scénario par `OTHER`. Le graphe indique également `KG`. `refresh()` accepte, écrit un nouveau contexte matière de **100 KG**, et laisse les événements initiaux de la carte en **100 UN / BASE**. Les signatures déclarées concordantes ne détectent pas ce mélange.
- Conséquence : une actualisation de l’affichage peut présenter une origine et une quantité de nature différente du registre qu’elle accompagne. Ce risque concerne l’utilitaire de rafraîchissement ; aucun mélange de cette nature n’a été constaté dans la carte livrée.
- Correction proposée : contrôler les champs d’identité et d’unité réellement utilisés, ainsi que le scénario et la provenance du graphe/manifeste. Refuser une variation sémantique, même si les identifiants numériques et quantités sont identiques. Ajouter des cas négatifs « même quantité, autre unité » et « autre scénario ».
- Preuves : clé `refresh_mismatched_unit_scenario` dans [contract-probes.json](../../artifacts/testing/audit_since_head_20260920/map/contract-probes.json), [script reproductible](../../artifacts/testing/audit_since_head_20260920/map/probe_contracts.py), HTML/CSV/graphe minimaux dans `map/fixture-refresh/`.

### MAP-03 — P2 : des quantités physiques vides peuvent devenir un bilan « rapproché »

- Source : `etudecas/visualization/maps/physical_material_balance.py:16-17`, `:28`, `:52-56`, `:91-103`.
- Le parseur `float(value or 0)` assimile une valeur absente ou vide à zéro. La présence d’un événement et d’une ligne de clôture suffit ensuite à déclarer la source disponible ; aucune garde ne distingue la mesure manquante du zéro mesuré.
- **Contre-exemple synthétique exécuté** : ligne matière `UN`, horizon d’un jour, événement de stock initial `qty=''`, clôture `stock_end_of_day=''`. Résultat : initial 0, clôture 0, écart 0, `physical_source_available=true`, `balance_status='reconciled'`, diagnostic **« Bilan physique rapproché »**.
- Conséquence : un CSV partiel, fourni directement au constructeur de carte, peut donner une assurance de rapprochement sans mesure. Le helper est effectivement utilisé par le builder. Toutefois, le chemin de qualification indépendant des CSV rejette déjà les nombres vides : un run passé par cette garde est protégé. Il ne s’agit pas d’une erreur constatée dans les stocks du run actuel.
- Correction proposée : parser strictement les champs physiques requis comme nombres finis ; faire porter l’état `unavailable` et des valeurs `null` aux mesures absentes. Ajouter un test avec événement présent mais quantité vide, et un autre avec clôture présente mais vide. Conserver le zéro explicite comme valeur valide.
- Preuve : clé `blank_physical_quantities` dans [contract-probes.json](../../artifacts/testing/audit_since_head_20260920/map/contract-probes.json).

### MAP-04 — P2 : le vérificateur indépendant conserve une borne d’arrondi trop étroite pour les coûts

- Source : `etudecas/testing/independent_review.py:133-138` et `Evidence.close` à `:29-34`.
- Pour rapprocher la somme journalière du coût opérationnel et le résumé, il autorise `N × 0,00005 + 0,0001`. L’export peut cumuler les arrondis de **cinq postes**, puis celui du total journalier incluant le sixième poste non encore arrondi. La borne du coût opérationnel est donc `(6N + 1) × 0,00005`, déjà prise en compte par `testing/map_delivery.py`.
- **Contre-exemple analytique exécuté sur le vérificateur** : 1 825 journées, six postes bruts de 1,000049 par jour. Le total CSV vaut 10 950,0000 ; le résumé brut arrondi vaut 10 950,5366. L’écart légitime **0,5366** respecte la borne **0,54755**, mais dépasse **0,09135** et provoque un échec dans `Evidence.close` avec les arguments exacts de `audit_run`.
- Conséquence : une qualification peut refuser un calcul correct uniquement à cause des arrondis documentés. Les jeux actuels ont un écart plus faible et passent ; cette preuve ne remet pas en cause leurs valeurs. Le contre-exemple a été construit sans lancer le moteur et sans modifier un run existant.
- Correction proposée : établir les bornes par chaîne d’export et périmètre, indépendamment du producteur ; partager le contrat mathématique entre les deux vérificateurs, avec cas aux limites et refus d’un vrai dépassement. Ne pas remplacer cette analyse par une tolérance monétaire arbitraire. Pour l’exposition économique, inclure aussi les postes externes effectivement sommés.
- Preuves : [independent-cost-rounding.json](../../artifacts/testing/audit_since_head_20260920/map/independent-cost-rounding.json), [script](../../artifacts/testing/audit_since_head_20260920/map/record_coverage.py), contre-calcul antérieur [rounding-counterexample.json](../../artifacts/testing/audit_corrections_20260920/model/final-dashboard/rounding-counterexample.json).

## Limites secondaires confirmées, sans erreur démontrée dans le jeu livré

Ces observations ne sont pas classées comme de nouvelles corruptions du run actuel. Elles précisent les préconditions à consolider avant de réutiliser les API avec d’autres producteurs ou scénarios.

- **Dates d’expédition contradictoires** — `unit_scoped_mrp.py:35-49` utilise `day`/`arrival_day`, alors que le helper d’exécution commun privilégie `realized_departure_day`/`realized_arrival_day`. Sur une ligne synthétique dont les dates historiques valent 0/1 et les dates réalisées 8/9, les graphiques MRP placent 7 unités dans la semaine commençant à J0 ; le helper commun les date à J8/J9, donc dans la semaine commençant à J7. Le moteur actuel exporte des dates cohérentes entre ces champs ; le défaut requiert un autre producteur ou une incohérence d’entrée. Réutiliser le helper d’exécution évitera deux définitions divergentes. Preuve : `conflicting_physical_dates` dans `contract-probes.json`.
- **Déclaration de valorisation incohérente** — `economic_valuation.py:9-24` croit le couple `complete=true/status=complete`, même avec `unknown_inventory_pairs` non vide et des périmètres monétaires manquants. Le contre-exemple renvoie `economic_ranking_eligible=true`, avec exposition/externe `null`. Le moteur actuel produit une déclaration cohérente et le rapprochement de livraison contrôle les contradictions ; les runs actuels sont correctement étiquetés incomplets. Une garde au niveau du producteur empêcherait un builder appelé directement de faire confiance à un résumé externe incohérent. Preuve : `contradictory_valuation` dans `contract-probes.json`.
- **Vérifications navigateur historiques** — `journey_explorer_review.py`, `journey_case_review.py`, `material_browser_review.py`, `journey_operations_browser.py` et `lot_usability_audit.py` comportent des identifiants/quantités de jeux historiques. C’est utile comme régression d’un jeu figé, mais ils acceptent des chemins quelconques sans imposer l’empreinte du jeu attendu. L’ancien lot racine `LOT-00002658` ne désigne plus le PBATCH cible dans le nouveau run ; celui-ci utilise `LOT-00003038`. Le contrôle générique `lot_browser_review` a été adapté, contrairement à ces utilitaires. Ne pas présenter leurs anciens résultats comme validation du nouveau scénario. Preuve d’identité, sans rejouer chacun de ces navigateurs : [historical-browser-ids.json](../../artifacts/testing/audit_since_head_20260920/map/historical-browser-ids.json).
- **Précondition du contrôle de scénario risque** — `journey_scenario_review.py:17` cherche par `next()` une réception portant `risk_event_ids` avant son bloc d’erreur. Sur un scénario sans réception à risque, l’utilitaire n’émet pas le rapport de contrôle prévu. Il devrait annoncer explicitement sa précondition ou l’état « non applicable ». Cette voie spécialisée n’est pas le contrôle général de la carte nominale.

## Ce qui résiste à cette revue

L’explorateur reste distinct du suivi historique des lots. Les modules relus séparent généalogie, mouvements physiques et consolidation camion ; partager un transport n’est pas utilisé comme preuve de consommation d’un lot. Les regroupements conservent l’article et l’unité. Les bornes de présence dans un stock mélangé sont présentées comme des bornes, sans inventer une filiation proportionnelle certaine. Les imports de dossiers d’enquête vérifient l’empreinte et préparent l’état avant remplacement ; les actions d’exploration ne modifient pas le registre physique.

Les changements de carte introduisent également des distinctions nécessaires : consommation physique/BOM, départ prévu/exécuté, unité par graphique MRP, coûts connus/couverture inconnue, association temporelle/attribution causale. Les tests négatifs existants couvrent notamment manque de source, bilans corrompus, mouvements futurs, unités incompatibles, imports invalides et absence de comparaison économique lorsque la valorisation est incomplète. Ils doivent être complétés par les contre-exemples de cette revue.

## Vérification réellement exécutée et réutilisation des preuves

Commande exécutée une fois :

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
python -m pytest etudecas/visualization/maps etudecas/testing etudecas/test_decision_support.py etudecas/test_decision_actions.py -q -p no:cacheprovider --junitxml=etudecas/artifacts/testing/audit_since_head_20260920/map/tests.xml
```

Résultat : **275 tests réussis, 3 sous-tests réussis, 55,53 secondes**, aucun saut signalé. Preuve : [tests.xml](../../artifacts/testing/audit_since_head_20260920/map/tests.xml). La commande inclut aussi des dépendances/tests préexistants de ces répertoires : ce nombre n’est pas le nombre de nouveaux tests depuis HEAD.

Une ouverture réelle supplémentaire de la carte, hors ligne, reproduit MAP-01. Les autres probes sont de petits appels de fonctions sur jeux construits ; ils ne constituent pas une campagne navigateur exhaustive. Le cas d’arrondi est un contre-calcul analytique avec application de la comparaison actuelle, pas une simulation de 1 825 jours.

La carte livrée a encore l’empreinte `51a019257f42ae3909ee17d87a3943d3a0b87f6da0f65e41325cf9d5a210a10f`. [reused-proof-binding.json](../../artifacts/testing/audit_since_head_20260920/map/reused-proof-binding.json) vérifie son identité binaire avec la carte attachée à l’audit numérique antérieur. Ce précédent rapprochement reste réutilisable sur cet artefact ; **ses millions de valeurs ne sont pas présentées comme recalculées à nouveau dans cette revue**. Il ne couvre pas toutes les futures entrées de chaque helper.

## Couverture des fichiers et reproductibilité

**58 fichiers nouveaux/modifiés** du périmètre ont une ligne de couverture nominative : **27 lectures détaillées de contrats et contrôle de flux, 8 revues de régions modifiées, 15 échantillonnages, 8 contrôles mécaniques avec tests**. Le mode détaillé n’implique pas la preuve de toutes les branches. Les deux gros fichiers builder/template ont été échantillonnés, avec diff et dépendances ciblées ; ils n’ont pas été relus ligne par ligne.

- [coverage.csv](../../artifacts/testing/audit_since_head_20260920/map/coverage.csv) : chaque chemin, mode de revue, longueur, empreinte et note.
- [coverage.json](../../artifacts/testing/audit_since_head_20260920/map/coverage.json) : mêmes entrées, symboles AST, imports locaux, comptes d’assertions/tests et dépendances ignorées.
- [tracked.diff](../../artifacts/testing/audit_since_head_20260920/map/tracked.diff) : différences des fichiers suivis depuis HEAD. Les nouveaux fichiers sont couverts par leur contenu courant et leur empreinte, puisqu’ils n’ont pas de contenu de référence dans HEAD.

Les **58 empreintes correspondent à l’inventaire initial du parent** après les contrôles : aucune source de ce périmètre n’a été modifiée par cette revue. Tous les Python concernés ont été parsés par AST ; ce contrôle de syntaxe ne vaut pas revue métier. Les modules JavaScript ont été lus et exercés par les tests navigateur concernés ; le CSS a été relu, sans prétendre couvrir chaque largeur d’écran ou combinaison de filtres.

Les fichiers Plotly `vendor/plotly-2.32.0.min.js`, `vendor/world_110m.json` et leur `.gitignore` sont ignorés. Le builder prévoit leur téléchargement ; ils sont ensuite embarqués pour l’utilisation hors ligne de la carte. Leur présence locale n’est donc pas une preuve qu’un clone propre peut construire la carte sans réseau. Pas de défaut d’exécution actuel constaté sur ces ressources, et pas de relecture de leur code tiers minifié. Les `__pycache__` ignorés sont des caches, pas des sources nouvelles à auditer comme du code écrit par l’équipe.

Les générateurs historiques non modifiés de ce répertoire, les sources moteur et les données de référence relèvent des autres volets de la revue. Les tests présents ne démontrent pas la calibration métier d’un score, la réalité d’un lot fournisseur ni l’exhaustivité d’un rappel industriel. Cette passe contrôle la cohérence des ajouts logiciels et leurs raccordements ; elle ne remplace pas l’audit chiffré antérieur de la carte.
