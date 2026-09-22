# Refaire les vérifications de cet audit

Exécuter les commandes depuis la racine `C:\dev\lca-simu`, avec l'environnement Python du projet. Le [rapport général](README.md) identifie exactement le HTML et les quatre calculs. Les scripts ponctuels de cet audit ciblent cette référence ; ils ne choisissent pas automatiquement le dernier résultat et ne constituent pas encore une toolbox générique.

Les résultats existants sont lus sans relancer cinq ans de simulation. Les commandes écrivent leurs preuves dans `etudecas/artifacts/testing/full_audit_20260920`. Conserver une copie de ce dossier avant un nouvel audit si ses résultats doivent rester comparables. Les gros artefacts et les scripts ponctuels placés dans `artifacts` sont locaux ; ils ne seront pas disponibles dans un simple checkout ne les contenant pas.

## Vérifications réutilisables déjà dans le projet

Suite de référence et documentation :

```powershell
python -m pytest -c pytest-reference.ini -q
python -m etudecas.documentation check-all
```

Inventaire de la suite étendue, en excluant les copies de test contenues dans les preuves :

```powershell
python -m pytest etudecas --collect-only --ignore=etudecas/artifacts --ignore=etudecas/archive -q
```

Dans cet audit, les 1 713 tests absents de la suite de référence ont été exécutés par [run_remaining.py](../../artifacts/testing/full_audit_20260920/run_remaining.py), depuis la liste figée `remaining-tests.json`. La liste appartient à l'état du code audité : la recollecter après une évolution du code. Le runner enregistre son XML et doit terminer avant la consolidation. Le premier essai avait un problème de chemin d'import du runner ; ses journaux sont conservés séparément.

Pour relire les invariants d'un calcul sans exécuter le moteur :

```powershell
python -m etudecas.testing.independent_review --run etudecas/simulation/result/_reruns/corrected_map_20260918 --output etudecas/artifacts/testing/full_audit_20260920/model/nominal-independent.json
```

Utiliser la racine de calcul qui contient `data` et `summaries`, et non son sous-dossier `run`. Les trois autres racines sont `scenario_runs/state_dependent_full`, `decision_support/actions/safety_150` et `decision_support/actions/expedite_50`, sous le même dossier principal. Conserver un nom de preuve différent pour chacune.

## Sondes propres à cet audit

Sources Excel, nomenclatures, coûts, tailles de lots et contre-exemples :

```powershell
python etudecas/artifacts/testing/full_audit_20260920/model/audit_sources.py
python etudecas/artifacts/testing/full_audit_20260920/model/audit_constraints.py
python etudecas/artifacts/testing/full_audit_20260920/model/audit_risk_semantics.py
```

**Un script qui termine n'indique pas que toutes les propriétés sont satisfaites.** Par exemple, `source-audit.json` contient `unit_invariance_probe.passed=false` : c'est le défaut démontré par la sonde. Le contre-exemple d'incident non appliqué enregistre aussi une conclusion erronée du produit. Lire ces sorties avec [model_data.md](model_data.md).

Rapprochement indépendant des valeurs embarquées dans le HTML :

```powershell
python etudecas/artifacts/testing/full_audit_20260920/numeric/audit_numeric.py
```

Ce script ne réimporte pas les constructeurs de courbes. Les chemins, contrôles, valeurs, tolérances et empreintes apparaissent dans ses JSON. `failed_checks=0` démontre le rapprochement numérique défini ; les problèmes métier N1 à N7 restent distincts.

Parcours de l'interface sous Chromium hors ligne, avec l'installation Playwright déjà disponible sur ce poste :

```powershell
python etudecas/artifacts/testing/full_audit_20260920/browser/audit_browser.py
python etudecas/artifacts/testing/full_audit_20260920/browser/exercise_ui.py
python etudecas/artifacts/testing/full_audit_20260920/browser/deep_ui.py
```

Ces sondes sont liées au DOM courant. Un bouton absent ou désactivé doit être classé comme indisponible, pas forcé ni assimilé à une courbe vérifiée. Les nœuds sont majoritairement parcourus en émettant l'événement de sélection ; un clic de souris réel est contrôlé séparément. Les limites sont dans [interface.md](interface.md).

## Consolidation et décision

```powershell
python etudecas/artifacts/testing/full_audit_20260920/finalize_audit.py
```

Le script vérifie de nouveau les empreintes du code et des sources suivies, lit les XML/Journaux, réunit les compteurs et signe les rapports par leurs empreintes dans `audit-summary.json`. Il refuse un état de collecte incomplet ou une source suivie modifiée. Un échec métier ou du pack reste inscrit dans la synthèse ; sa conclusion générale reste `revision_required_before_industrial_decision`, même lorsque tous les tests Etudecas sont verts.

Cette consolidation n'est pas une signature cryptographique d'auteur, ni une preuve de vérité industrielle. Après les corrections, il faudra mettre à jour les contrats, conserver les anciens résultats et produire de nouvelles preuves avec un nouveau manifeste. L'[architecture multi-agent](multiagent.md) prévoit d'intégrer ces oracles dans des commandes paramétrées et versionnées ; cette généralisation reste à réaliser.
