# Inventaire et politique de conservation depuis le dernier commit

Référence Git : `f95b1db6bb233cbf9750fc6ab2fda3943d6e82ab`, 15 septembre 2026.
La baseline a été prise avant les rapports de cette nouvelle revue. Elle couvre
le dépôt entier, pas seulement les fichiers de la dernière correction.

## Ce que Git permet de constater

| Ensemble | Nombre | Sens exact |
|---|---:|---|
| Fichiers non suivis | 265 | Absents de HEAD et non ignorés ; Git ne dit pas qui les a créés ni s'ils étaient déjà présents avant le commit. |
| Fichiers suivis signalés modifiés | 158 | État du répertoire de travail au début de revue. |
| Fichiers présentant un diff de contenu | 72 | Diff normalisé par Git par rapport à HEAD. |
| Autres fichiers suivis signalés modifiés | 86 | Comparaison directe avec les blobs HEAD : octets strictement identiques. Ne pas compter ces signalements comme 86 modifications de code. |
| Fichiers ignorés présents | 75 008 | Principalement environnements, caches, résultats et preuves locales ; inventaire de métadonnées, pas revue intégrale de leur contenu. |
| Ignorés datés après le commit | 2 629 | Indice création/modification du système de fichiers, pas preuve d'origine Git ; environ 30,19 Go décimaux. |

Les 265 fichiers non suivis occupent **2 617 424 octets**. Les **423 fichiers**
non ignorés signalés par Git ont une empreinte SHA-256 de baseline. Aucun
fichier n'était dans l'index de staging. La revue ne met rien en staging,
ne crée aucun commit et ne supprime aucun fichier.

| Famille | Non suivis | Suivis signalés modifiés |
|---|---:|---:|
| Racine, instructions et autres entrées | 27 | 7 |
| Graphe de connaissance | 1 | 2 |
| Prototypes et leurs tests | 11 | 106 |
| Simulation, API et préparation | 12 | 21 |
| Carte et visualisation | 14 | 10 |
| Pack multi-agent | 40 | 12 |
| Documentation du projet | 119 | 0 |
| Générateur de documentation | 6 | 0 |
| Vérificateurs et tests de livraison | 30 | 0 |
| Toolbox | 5 | 0 |

L'[inventaire complet CSV](../../artifacts/testing/audit_since_head_20260920/inventory.csv)
donne chemin, statut, famille, taille, dates et empreinte pour les fichiers
revus. La [version JSON](../../artifacts/testing/audit_since_head_20260920/inventory.json)
et le [diff conservé](../../artifacts/testing/audit_since_head_20260920/tracked.diff)
permettent de revenir à la portée exacte de cette passe.

## Contrôles transversaux

La [revue mécanique](../../artifacts/testing/audit_since_head_20260920/mechanical-summary.json)
lit 501 fichiers texte, dont les scripts ponctuels d'audit ignorés par Git :
312 Python analysés sans exécution, 70 JSON, 4 YAML et 11 TOML valides.
Aucun marqueur de conflit non résolu n'a été trouvé. Les 690 imports absolus
locaux inspectés pointent vers un module ou un paquet présent ; cela ne
prouve pas la validité de tous les symboles, imports relatifs ou imports
dynamiques à l'exécution.

Les 827 liens Markdown locaux inspectés ont une cible présente, après
interprétation des suffixes de ligne. Neuf liens utilisent `fichier.py:ligne`,
une notation dépendant du lecteur ; leur cible existe mais leur portabilité
sur GitHub/navigateur est à améliorer. Cent liens pointent vers des preuves
ou résultats ignorés par Git. Les URL distantes et ancres internes ne sont
pas vérifiées par ce contrôle.

Les 86 signalements sans diff ont été contrôlés avec `git cat-file` et
comparaison directe des octets, pas déduits d'un compteur de lignes.
La preuve figure dans [line-endings.json](../../artifacts/testing/audit_since_head_20260920/line-endings.json).

## Conservation et versionnement proposés

Le [plan fichier par fichier](../../artifacts/testing/audit_since_head_20260920/versioning-plan.csv)
couvre les 265 chemins non suivis. Il s'agit de propositions, sans modification
de l'index Git.

- **Conserver et versionner après correction des défauts** : sources, tests,
  petites fixtures, configuration, instructions natives et documentation.
  Les 22 pages/manifestes générés des onze registres voyagent avec leurs règles,
  car `check-all` vérifie leur présence et leur synchronisation.
- **Garder le staging natif** : les neuf copies du pack et leurs équivalents
  racine sont identiques. Cette duplication est voulue pour le déploiement,
  pas un résidu à supprimer sans examen.
- **Laisser locaux les exemples générés du pack** : sept dossiers UUID,
  28 fichiers. Les sept PNG et deux types de rapports sont identiques ; les
  rapports de validation graphique contiennent notamment leur propre chemin.
  Les tests actuels reconstruisent des sorties temporaires et ne dépendent
  plus de ces répertoires globaux. Les fichiers ont été conservés pendant la revue.
- **Archiver les gros résultats à part** : les nouveaux candidats ignorés
  représentent environ 30 Go, dont plusieurs `lot_causal_links.csv` dépassant
  2 Go. Les inclure dans un commit ordinaire n'est pas une stratégie de
  conservation adaptée. Prévoir un paquet de livraison identifié par SHA,
  avec manifeste, entrées exactes et instructions de récupération/recalcul.

## V-01 — P2 : les preuves reproductibles dépendent encore d'un dossier local ignoré

`.gitignore` exclut tout `etudecas/artifacts/` et les sorties de simulation.
L'inventaire trouve **49 scripts d'audit/livraison** `.py`/`.ps1` récents dans
ce dossier, plus 40 copies de sources dans un ancien essai isolé du pack.
Des commandes de `docs/audit_20260920/reproduction.md:37–65` désignent ces
scripts ; la même page avertit explicitement de leur caractère local à la
ligne 5. Il ne s'agit donc pas d'une promesse cachée de disponibilité dans Git.

Le manque opérationnel subsiste : un futur checkout contenant seulement les
fichiers versionnables n'aura pas ces scripts ni les cent preuves liées depuis
les documents. Des contrôles importants de la dernière livraison, notamment
les oracles Excel et la vérification complète des graphiques, sont concernés.
Les modules réutilisables de `etudecas/testing` restent, eux, versionnables.

**Proposition** : promouvoir les oracles réutilisables vers un emplacement
source, avec paramètres d'entrée et tests, puis garder uniquement journaux,
captures, résultats et manifestes dans `artifacts`. Conserver les scripts
ponctuels historiques avec leur paquet de preuves lorsqu'ils sont nécessaires
pour interpréter l'audit daté. Ne pas changer une empreinte historique pour
faire passer un nouveau code à sa place.

Ce constat porte sur la transmission et la répétabilité du travail, pas sur
une erreur arithmétique démontrée dans les résultats livrés.
