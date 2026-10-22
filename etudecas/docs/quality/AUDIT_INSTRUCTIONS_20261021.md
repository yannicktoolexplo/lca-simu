# Audit des instructions et du harnais — 21 octobre 2026

Périmètre : instructions, procédures, profils et routage. Moteur, données,
dépendances et références industrielles inchangés. Départ : `dev_yannick`, commit
`8a7cc3b27b1c95ee91b1e07b2b35d29d7e575adf`, arbre propre. Les consignes durables
sont dans [AGENTS.md](../../../AGENTS.md) et le
[guide scientifique](../DEVELOPPEMENT_SCIENTIFIQUE.md) ; ce bilan garde l'état daté.

## Acquis et limites de l'existant

| Statut | Constat et preuve |
|---|---|
| Vérifié en lecture seule | Les huit assets du [bundle MRP](../../config/mrp_reference_20261013.json) existent et leurs SHA correspondent. L'HTML courant a le SHA `a6cde094039b25c47e3516f5d3e217e833d3714d3693cee3dd88b839061a12a2`, conforme à la livraison documentée. Cela ne requalifie pas le moteur. |
| Existant, réutilisé | Parcours regenerate → [current_reference.py](../../simulation/current_reference.py) → moteur → CSV/manifestes → carte ; API typée, planification, lotification, transports et contrats de résultats séparés. Le cœur physique reste dans [run_first_simulation.py](../../simulation/engine/run_first_simulation.py). |
| Contrat d'entrée important | `resolve_inputs()` vérifie le bundle puis superpose `Flow_Data_Customer_Demand.xlsx` : le graphe seul ne décrit pas toutes les entrées. Observations 2025 et projections ultérieures ont des statuts distincts. |
| Déjà correctement documenté | [REGLES_MRP](../REGLES_MRP.md) couvre netting, réceptions tardives, surplus, connaissance datée et `tau_process`. [DONNEES_SOURCES](../DONNEES_SOURCES.md) et [RAPPORT_COMPLETUDE_SIMULATION](../RAPPORT_COMPLETUDE_SIMULATION.md) explicitent les données absentes. Les skills gardent hypothèses réfutées et propagation aval. |
| Historique, pas preuve actuelle | La [qualification du 14 octobre](../../artifacts/testing/final_mrp_cleanup_20261014/qualify-e228f53c8a9e4c8bb59b1edf3b4ea518/manifest.json) déclare `passed`, mais ses empreintes de `current_reference.py`, `run_first_simulation.py` et `current_reference_map.py` diffèrent du code audité. |
| Périmètres ambigus | `docs/reference/current.json` désigne septembre ; `mrp_current.json`, la référence demande/DC du 8 octobre ; le code utilise `coherent-MRP-20261014`. Identifier référence et périmètre, sans modifier ces comparateurs. |
| Inconnu/insuffisamment éprouvé | Capacités et calendriers industriels, ordres fermes, journaux OF/PO/prélèvements/qualité/livraisons et correspondances Scan3/BOM restent partiels. Une meilleure courbe ne résout pas ces inconnues. |

## Harnais réellement présent

| Niveau | Présence observée | Limite de la preuve |
|---|---|---|
| Codex natif | Outils de délégation/messages/suivi ; catalogue de quatre rôles et cinq skills ; trois enfants ont reçu et rendu des tâches utiles | `list_agents` a montré parent + trois enfants ; le plafond n'a pas été éprouvé. |
| Consignes déclaratives | AGENTS, rôles, propriété de fichiers, budgets | Explorer a retrouvé dans son contexte l'instruction du profil disque. Le rôle carte a refusé une écriture documentaire incompatible avec son instruction : restriction déclarative observée, pas preuve d'une sandbox. |
| Procédures spécialisées | Cinq skills, registre des tickets et guides | Parent a lu orchestrate ; agent métier a lu diagnose/calibrate/qualify. Catalogue disponible ne signifie pas procédure exécutée. Aucun automate de tickets/routage. |
| Contrôles déterministes | [cli.py](../../toolbox/cli.py), [contracts.py](../../toolbox/contracts.py), tests, CSV, navigateur, docs/gate | Huit aides exécutables vérifiées. Les contrôles réellement exécutés et manifestes sont dans le relevé final ; une aide seule ne valide pas le contrôle. |

Les profils/configurations n'imposent ni modèle ni effort ; les délégations ont
demandé l'héritage. Modèle effectivement servi, jetons et coût facturé ne sont pas
exposés par ces preuves. Les anciennes clés `sandbox_mode` des rôles sont retirées :
elles ne remplacent pas les permissions du parent, selon la documentation officielle.
[Sous-agents Codex](https://learn.chatgpt.com/docs/agent-configuration/subagents).

Les changements disque ne rechargent pas rétroactivement les enfants déjà créés.
Le contexte initial a été observé ; le chargement des fichiers finaux dans une
nouvelle session n'est pas revendiqué. Découverte revérifiée le 21 octobre :
[AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md) et
[skills](https://learn.chatgpt.com/docs/build-skills).

Lacunes : doctor contrôle trois skills historiques seulement, ni les deux skills
supply chain ni leurs liens ; il ne vérifie pas l'absence de modèle imposé ou la
valeur exacte de trois enfants. `changed_files` est déclaratif ; handoff ne détecte
pas une omission. `--timeout` borne chaque sous-processus, pas la mission entière.
Budgets et tickets restent des procédures parent. Aucun juge IA ne remplace ces
contrôles ni les oracles scientifiques.

## Problème → instruction/procédure → vérification

| Problème observé | Changement | Vérification adaptée |
|---|---|---|
| Navigation faible, méthode répétée en racine | AGENTS transversal, guide scientifique et skills ciblés | Liens, revue et section Sophos identique |
| Recommandation confondue avec capacité implémentée | Quatre statuts de preuve ; six responsabilités comme critères d'audit | Revue indépendante ; aucune capacité moteur nouvelle revendiquée |
| Modules entiers/injections encore prescrits | Cas exacts, fixtures/hooks relus ; guides calibration/exécution corrigés | Recherche ciblée ; aucun test interdit exécuté |
| Fausse isolation attribuée aux profils | Retrait sandbox_mode, permissions effectives explicites | TOML, documentation officielle et observation explorer |
| Pack ancien à trois skills | Synchronisation depuis racine, cinq skills et référence tickets | Comparaison racine/staging et métadonnées des cinq skills |
| Budget absent de la délégation | Calcul/temps/mémoire/stockage et arrêt dans objectif ou suivi | Champs TaskSpec inchangés ; aucune promesse de quota automatique |
| Dates/unités/états dispersés | Contrat synthétique et distinction planification/exécution | Oracles manuels et revue indépendante |
| Calibration confondue avec robustesse des fichiers | Protocole avant runner, critères préfixés, validation chronologique, identifiabilité | Tâches E3/E4 ; aucune campagne documentaire massive |
| Performance/risques sans procédure commune | Profilage, mémoire, intensité par pas et flux stables | E5 et hypothèses explicites, sans migration automatique |
| Chargé/disponible/exécuté confondus | Tableau du harnais et limites doctor/gate | Retours réels, aides et preuves de livraison |
| Routeur envisagé sans gain établi | Comparaison bornée ci-dessous ; maintien du natif | Comptages indépendants, abstentions et coûts inconnus déclarés |

## Jev et comparaison de routage

Clarification utilisateur : pas d'accès Jev, inspiration seulement si utile.
Aucun SDK, service, API ou dépendance ajouté. Recherche locale sans intégration
Jev dans le code/configuration non sensibles inspectés ; pas de conclusion sur
les installations globales.

TypeSafe propose des décisions bornées `Choice` avec distribution. La confiance
résume cette distribution, sans être directement la probabilité d'une réponse
correcte ; les seuils demandent une évaluation du domaine. Sources consultées le
21 octobre : [introduction](https://docs.typesafe.ai/introduction),
[confiance](https://docs.typesafe.ai/confidence). La page
[modèles](https://docs.typesafe.ai/models) annonce `jev-1.14.0`, avec `jev-latest`
encore sur `1.13.0` et `jev-preview` sur 1.14 ; aucune version appelée. Les
performances commerciales ne sont pas des mesures Etudecas.

Le [jeu de douze tickets](../../artifacts/testing/instructions_20261021/routing_cases.json)
couvre MRP, données, calibration, causes racines, performance, carte, revue,
parallélisme, ambiguïté et instruction citée sans autorité. Le parent a fixé
l'[oracle](../../artifacts/testing/instructions_20261021/routing_reference.json)
avant de recevoir les réponses. L'explorateur n'a reçu ni oracle ni règles.
Le petit routeur expérimental est conservé dans les artefacts, hors harnais actif ;
ses règles n'ont pas été ajustées après notation.

| Mesure, mêmes 12 textes | Natif | Règles avec abstention | Jev |
|---|---:|---:|---|
| Routes attendues, clarification incluse | 12/12 | 11/12 | Non mesuré |
| Routes spécialisées acceptées | 11/12 | 10/12 | Non mesuré |
| Mauvaises routes parmi les acceptées | 0/11 | 0/10 | Non mesuré |
| Abstentions pertinentes / inutiles | 1 / 0 | 1 / 1 | Non mesuré |
| Temps | ≤ 78,884 s, aller-retour incluant travail concurrent parent | 1,6944 ms, lot mémoire hors Python/IO | Non mesuré |
| Coût | Jetons/facturation indisponibles | 0 appel API ; CPU non valorisé | Non mesuré |

R01 demande correction puis contre-validation : deux correspondances de mots-clés
font s'abstenir inutilement les règles. Le natif identifie la première étape.
Les deux méthodes s'abstiennent sur R10, trop vague.
[Résultats et limites](../../artifacts/testing/instructions_20261021/routing_comparison.json).
Les temps portent sur des frontières différentes : aucun facteur d'accélération
n'en est déduit. Textes synthétiques et règles ont le même auteur ; les quatre
cas supplémentaires ne forment pas une validation indépendante hors conception.
Seul le routage est évalué, pas la réussite des missions.

**Décision : conserver le natif.** Aucun gain démontré ne justifie Jev ou un
classificateur supplémentaire. Clarifier route, incertitude et compatibilité
du rôle avec les fichiers apporte une amélioration procédurale sans dépendance.
Permissions, gate et oracles indépendants restent distincts. Rouvrir seulement
avec des erreurs sur un volume réel de tickets et un bénéfice mesurable.

## Outillage : conserver avant d'ajouter

Métadonnées observées sans installation : Python 3.11.9 ; NumPy 2.4.6, pandas 3.0.3,
openpyxl 3.1.5, pytest 9.1.1, PyYAML 6.0.3, matplotlib 3.11.0, Pillow 12.3.0,
Playwright 1.61.0, Ruff 0.15.20. Ruff présent n'est pas une configuration qualité.
SciPy, PuLP, SimPy et PyArrow sont épinglés dans le requirements global mais absents
de ce Python. Requirements Etudecas à bornes ouvertes, sans verrou dédié identifié.

Docs officielles ci-dessous ouvertes le 21 octobre 2026. Aucun candidat non installé
n'a de version qualifiée sur ce projet. Avant adoption, figer compatibilité
Windows/Python/NumPy/pandas, mesurer et maintenir un retour possible ; un lien
stable/latest ne constitue pas un verrou. Ce tableau ne prescrit aucune installation.

| Candidat / besoin | Alternative existante / décision | Compatibilité, maintenance et preuve attendue |
|---|---|---|
| [uv](https://docs.astral.sh/uv/concepts/projects/) : reproductibilité | pip + requirements ; verrou dédié d'abord | Interpréteur/verrou à maintenir ; installation reproductible et résultats identiques sur deux environnements |
| [Ruff](https://docs.astral.sh/ruff/) : erreurs statiques | Présent ; pas de reformatage global | Règles limitées aux modules concernés ; vrais défauts détectés et bruit acceptable |
| [mypy](https://mypy.readthedocs.io/en/stable/) : types | Dataclasses/types actuels ; un seul vérificateur envisagé | Pilote API/contrats, stubs pandas et dette d'annotations ; erreurs utiles, pas deux vérificateurs simultanés |
| [Hypothesis](https://hypothesis.readthedocs.io/en/latest/stateful.html) : séquences métier | Oracles pytest exacts et mémoire d'abord | Générateurs bornés, contre-exemple minimal ; aucune altération de fichiers interdite |
| [Pydantic](https://pydantic.dev/docs/validation/latest/concepts/models/) / [Pandera](https://pandera.readthedocs.io/en/stable/dataframe_schemas.html) : frontières objet/tableau | Dataclasses/validations existantes | Choisir selon frontière ; coercition/nulls/unités explicites, coût et erreurs détectées mesurés |
| [Pint](https://pint.readthedocs.io/en/stable/) : conversions | Conventions et calculs manuels | Pilote kg/g/UN ; registre/sérialisation à maintenir, défaut dimensionnel concret avant ajout |
| pandas/openpyxl ; [Arrow/Parquet](https://arrow.apache.org/docs/python/), [Polars](https://docs.pola.rs/), [DuckDB](https://duckdb.org/docs/2.0/clients/python/overview) | Garder lectures actuelles, sélectionner/agréger d'abord | Point chaud IO/RAM mesuré ; mêmes types/dates/nulls/ordres/sommes ; coût migration et double lecteur |
| NumPy/[SciPy](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.linprog.html), [Numba](https://numba.readthedocs.io/en/stable/user/5minguide.html) | NumPy disponible ; compilation non justifiée | Profilage avant JIT, compatibilité NumPy/LLVM et démarrage ; même sens/tolérances, gain répété |
| [SimPy](https://simpy.readthedocs.io/en/latest/), [PySD](https://pysd.readthedocs.io/en/master/) | Conserver noyau quotidien | Ressources/événements ou modèle SD explicite seulement ; migration coûteuse, équivalence calendriers/états et bénéfice démontré |
| PuLP, [CP-SAT](https://developers.google.com/optimization/cp/cp_solver), [HiGHS/SciPy](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.linprog.html) | Réutiliser formulations/solveurs déclarés | Entiers/ordonnancement vs LP selon problème ; versions/binaires, faisabilité, gap et temps sur petit oracle |
| [SALib](https://salib.readthedocs.io/en/latest/), [flux NumPy](https://numpy.org/doc/stable/reference/random/parallel.html) | Sensibilités/Monte-Carlo existants | Hypothèses corrélation/indépendance, convergence et coût moteur ; flux stables et gain méthodologique avant remplacement |

## Cinq tâches d'évaluation des consignes

Tâches proposées, **non exécutées contre le moteur dans cette passe**. Pour chacune :
sources stabilisées, scénario exact, nouveau dossier de preuves, budget mesuré sur
cas court, arrêt si alerte/donnée indispensable absente/limite atteinte. Commencer
en mémoire sans campagne ni installation. Le routage de ces demandes seul a été évalué.

| ID / demande | Livrable et oracle | Réussite et erreur à détecter |
|---|---|---|
| E1 — Achat MRP doublonné | Besoin 10 à J2, libre 3, réception ferme 7 à J4, sécurité nulle, aucun autre besoin ni accélération ; correction et revue distincte | 3 à l'échéance, 7 tardifs, zéro nouvel achat ; aucune disponibilité fictive à J2, engagement unique |
| E2 — Données incohérentes | En mémoire : 1 kg, 1000 g, absent, −2 kg de signe inconnu et dates de connaissance manquantes | Deux premières masses égales ; absence distincte de zéro ; aucun écrêtage/date inventée, transformations proposées séparées |
| E3 — Calibration commune | Paramètre borné, témoin, critères volumes/dates, période chronologique hors ajustement et autre article si disponible | Pas de fuite future/fenêtre favorable ; gains/dégradations chaîne et identifiabilité ; préserver référence si preuve insuffisante |
| E4 — Cause racine | Retard amont simulé 2 jours, aval initial 10 UN, demande 3/jour, aucun autre besoin | 6 absorbées et stock 4 à deux jours ; pas de non-livraison déduite du seul retard ; cause industrielle distincte/inconnue |
| E5 — Performance | Cas figé, profil temps/RAM/IO/artefacts, extraction minimale du point chaud | Mêmes entrées/états/indicateurs/tolérances ; gain supérieur au bruit ; refuser comparaison avec demande/calendrier différents |

## Backlog distinct : aucun changement moteur dans cette passe

| Priorité | Problème concret / source | Suite et preuve attendue |
|---|---|---|
| P0 — CI | [Workflow](../../../.github/workflows/etudecas-documentation.yml), l.32/40/73 : modules avec altérations/suppressions et référence absente à `test_correction_contracts.py` | Relire puis sélectionner des cas exacts autorisés ; ne pas lancer le workflow actuel pour le vérifier |
| P0 — Références | Registres current antérieurs au bundle 14/10 | Clarifier consommateurs/pointeur actif, préserver comparateurs ; aucune acceptation globale d'empreintes |
| P1 — Qualification | Preuves historiques incompatibles ; navigateur non rejoué depuis refus | Nouvelle preuve adaptée lors d'une livraison de calcul ; cette passe ne qualifie pas le nominal |
| P1 — Registres documentaires | Le contrôle global refuse cinq domaines pour six références préexistantes : `engine-day-loop`, `payload`, `browser`, `csv-oracle`, `lot_journey.js`, `engine-run` ; leurs sources ne sont pas changées ici | Revue dédiée ; seuls les deux textes métier relus sont acceptés dans cette passe, aucun hash de code réaccepté par opportunité |
| P1 — Environnement | Pas de verrou Etudecas ; Playwright absent des requirements tests mais exigé par doctor | Séparer runtime/tests/navigateur ; versions contrôlées et installation reproductible, aucune installation implicite |
| P1 — Doctor | Trois skills contrôlés sur cinq ; pas liens/plafond exact/surcharges | Étendre le contrôle déterministe après spécification ; cas mémoire, pas tests d'altération |
| P1 — Données | [Questions ouvertes MRP](../REGLES_MRP.md) : capacité 693055 absente, FIA 70 j non réconciliés, calendriers et ordres fermes incomplets | Obtenir portée/dates/définition source ; expérience discriminante, pas coefficient pour rapprocher une courbe |
| P2 — Modularité | Moteur 26 915 lignes, planification 2 836 ; current_reference modifie temporairement des objets globaux | Extraction justifiée par défaut/oracle/profil, mesurer isolation/équivalence ; pas réécriture au nombre de lignes |
| P2 — Incertitude | Mécanismes existants sans distributions/causalité industrielles établies | Campagne bornée après diagnostic, appariement vérifié et données discriminantes |

## Preuves et reprise

Le [relevé local](../../artifacts/testing/instructions_20261021/verification.json)
énumère contrôles, codes de retour, manifestes, fichiers et empreintes finales.
Le [doctor racine](../../artifacts/testing/instructions_20261021/doctor-e1a10f59b071415cbe1adac7bef1fe1a/manifest.json)
réussit ; le [contrôle documentaire global](../../artifacts/testing/instructions_20261021/docs-3e303332ed894d95bf634af5ec0922f5/manifest.json)
est refusé pour les divergences préexistantes listées au backlog. Aucun gate global
n'est annoncé réussi. Les deux empreintes de textes relus sont mises à jour selon
AUTOMATION.md et leurs pages régénérées ; les empreintes de code restent intactes.
Un contrôle exclu/échoué/non exécuté reste distinct d'une réussite. Le contrôle du
catalogue ne remplace pas les liens des instructions ni les cinq skills. Aucune
suite pytest globale, simulation, navigateur ou ancien contrôle d'altération
n'est lancé pour cet audit. Les oracles manuels ont reçu une revue indépendante,
sans être exécutés contre le moteur.

`codex --version` a indiqué `0.162.0-alpha.17.2` avec refus d'accès à ses fichiers
temporaires : arrêt des appels à cet exécutable, aucune sonde ni contournement.
Le refus n'est pas attribué à Sophos sans preuve. Section Sophos et preuves
historiques conservées. Prochaine action hors mission : sélections CI et gouvernance
des références avant une nouvelle campagne.
