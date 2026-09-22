# Maintenir la documentation du code et du métier

Ce guide rassemble les commandes du générateur et la procédure de maintenance
des règles. Pour choisir un guide métier, revenir au [sommaire](README.md).

Le générateur utilise la bibliothèque standard de Python (3.10+). Il analyse
les sources avec `ast`, sans importer le moteur, lancer une simulation ou
exécuter les tests référencés. Aucun service externe n'est nécessaire.

## Registres et fichiers générés

Le [catalogue](catalog.json) associe chaque registre de `docs/rules/` à son
dossier sous `docs/generated/`. Chaque registre décrit des règles, leurs sources
métier et des références vers l'implémentation et les tests. Le générateur produit
un `index.md` et un `manifest.json`, compacts et versionnés avec le code.

Exemple : [registre des lots et risques](rules/lot_risk.json),
[page générée](generated/index.md), [manifeste](generated/manifest.json) et
[source métier](../simulation/lot_trace/RISK_IMPACT_REGISTRY.md).

| Élément | Gestion |
|---|---|
| Signatures, annotations, constantes, docstrings et lignes des symboles référencés | Extraction automatique |
| Liens règle → implémentation → tests | Résolution et contrôle automatiques |
| Règles affectées par une modification | Détection automatique |
| Définition métier, unités, périmètre et limites | Texte explicite à relire et maintenir |
| Justification des hypothèses et validation industrielle | Jamais déduites du code ou d'une empreinte |
| Résultats des tests | Non exécutés et non certifiés par le générateur |

## Traiter tout le catalogue

Depuis la racine du dépôt :

```powershell
# Générer les pages et manifestes.
python -m etudecas.documentation build-all

# Contrôler sans écrire.
python -m etudecas.documentation check-all

# Régénérer après une modification ; Ctrl+C pour arrêter.
python -m etudecas.documentation watch-all
```

Un registre présent dans `docs/rules/` mais absent du catalogue est refusé,
comme une sortie dupliquée ou un chemin hors du dépôt. Si un registre est
invalide, les autres sont tout de même examinés ; un catalogue invalide empêche
le démarrage du lot.

`watch-all` surveille les sources, les règles et les pages métier. Ne pas le
lancer pendant une vérification exigeant des fichiers immuables. Pour un
contrôle bloquant, utiliser `check-all`.

## Examiner un seul domaine

Sans option, les commandes suivantes ciblent le registre des lots et risques :

```powershell
python -m etudecas.documentation build
python -m etudecas.documentation check
python -m etudecas.documentation inspect
python -m etudecas.documentation watch
```

`inspect` affiche les empreintes actuelles et les règles impactées sans écrire.
Pour un autre domaine, donner son registre et son dossier de sortie :

```powershell
python -m etudecas.documentation inspect --registry etudecas/docs/rules/run_package.json --output-dir etudecas/docs/generated/run_package
python -m etudecas.documentation build --registry etudecas/docs/rules/run_package.json --output-dir etudecas/docs/generated/run_package
python -m etudecas.documentation check --registry etudecas/docs/rules/run_package.json --output-dir etudecas/docs/generated/run_package
```

`watch` accepte les mêmes options. Il vérifie les fichiers toutes les deux
secondes (`--interval 2`) et reste actif jusqu'à Ctrl+C. Une erreur pendant une
édition est signalée ; la sauvegarde suivante permet de réessayer. Les commandes
`*-all` utilisent le catalogue et n'acceptent pas un autre registre ou dossier
de sortie.

## Lire les codes de retour

| Code | Signification pour `build` et `check`, seuls ou sur le catalogue |
|---|---|
| `0` | Documentation à jour, aucune divergence avec les références |
| `1` | Documentation périmée ou références nécessitant une relecture |
| `2` | Registre invalide, source absente ou symbole introuvable |

`build` écrit les pages même si une référence a changé : les règles concernées
sont marquées « relecture requise » et le retour reste 1. Régénérer ne suffit
donc pas à accepter un changement. `inspect` est informatif et retourne 0 si le
registre est exploitable. L'arrêt normal de `watch` retourne 0 ; exécuter
`check` ou `check-all` avant de livrer.

## Mettre à jour une règle après modification du code

1. Modifier le code et ses tests ; lancer `build` sur le domaine concerné.
2. Utiliser `inspect` pour lire `changed_references` et `changed_business_sources` pour chaque règle.
3. Relire les définitions, unités et limites concernées. Corriger leurs textes, liens et statuts si nécessaire. Exécuter les tests métier séparément.
4. Après cette revue, reporter uniquement les empreintes examinées : `references[].fingerprint` du manifeste vers le `reference_fingerprint` de la même référence dans le registre ; pour les textes métier, reporter la valeur de `business_source_fingerprints` du chemin concerné.
5. Relancer `build`, puis `check-all`. Relire ensemble les différences du code, des règles et des pages générées.

Ni `build` ni `watch` n'acceptent automatiquement de nouvelles empreintes. Les
empreintes constituent un état documentaire de référence, **pas une attestation
de validation métier**. Il n'existe pas de commande acceptant toutes les
nouvelles empreintes sans relecture.

Les statuts `documented`, `known_gap`, `hypothesis` et `experimental` décrivent
l'état déclaré d'une règle. Aucun ne signifie « validé par le métier ». Par
exemple, le [changement de statut de la jointure expéditions/lots](changes/2026-09-16-shipment-identity.md)
accompagne une correction documentée. Une page à jour peut aussi décrire un
défaut connu.

## Ajouter un domaine ou une règle

Une référence comporte `id`, `kind` (`implementation`, `test` ou `contract`),
`path` relatif à la racine du dépôt, `symbol` et `reference_fingerprint`. Le
symbole peut être une fonction, une classe, une méthode (`Classe.methode`) ou
une constante de premier niveau.

Une règle exige un identifiant stable tel que `MRP-ORDER-001`, un titre, un
énoncé, des unités, un périmètre, des limites, un statut, des sources métier
existantes et au moins une référence d'implémentation et une de test. Les
documents métier doivent figurer dans `business_source_fingerprints`.

Pour préparer une référence, une chaîne de 64 zéros permet d'obtenir son
empreinte avec `inspect`, avant de la reporter après revue. Cette étape n'est
pas une validation.

Pour un nouveau domaine :

1. Créer son registre sous `etudecas/docs/rules/` et lui attribuer un dossier de sortie distinct.
2. Ajouter la paire registre/sortie au [catalogue](catalog.json).
3. Examiner les références avec `inspect`, puis reporter les empreintes relues.
4. Générer et contrôler le catalogue avec `build-all` puis `check-all`.
5. Ajouter les tests métier nécessaires et vérifier les liens de la page générée.

Le contrôle sur un seul registre ne couvre que ce registre ; `check-all` exige
que le catalogue couvre tous les registres du dossier.

## Contrôles locaux et GitHub

Les tests de `etudecas/documentation/` vérifient notamment les références
absentes, les changements de sources, les fichiers générés modifiés et le
traitement du catalogue :

```powershell
python -m pytest etudecas/documentation -q
```

Le [workflow GitHub](../../.github/workflows/etudecas-documentation.yml) définit
les déclencheurs, dépendances et tests réellement exécutés. Il prévoit le
contrôle documentaire et des tests applicatifs ciblés, dont certains importent
le moteur, ainsi que des contrôles d'écritures atomiques sur Windows et Linux.
Ces tests sont distincts du générateur statique décrit ici. Les détails de
publication et reprise sont dans [CALIBRATION_EXECUTION.md](CALIBRATION_EXECUTION.md).

Le workflow ne crée aucun commit et ne publie aucun document. Il faut pousser
les fichiers pour l'exécuter sur GitHub ; sa présence locale ne prouve pas une
exécution distante réussie. Les prérequis des tests, notamment ceux du navigateur,
doivent être installés dans le job qui les lance.

## Portée des empreintes et limites

Les empreintes de code utilisent une représentation AST canonique, indépendante
des positions, de l'indentation et des fins de ligne LF/CRLF. Les docstrings,
signatures et corps des symboles sont inclus. Les textes métier utilisent leur
contenu UTF-8 avec fins de ligne normalisées. Les chemins et numéros de ligne du
rendu sont actualisés même si seul l'emplacement d'un symbole change.

Cette politique **ne remplace pas** le SHA-256 exact des artefacts de simulation.
Elle détecte des changements ; elle ne prouve pas une équivalence de comportement.

Seuls les symboles et documents déclarés sont suivis. Les dépendances
transitives, commentaires Python hors docstrings, paramètres d'exécution et
fichiers externes ne le sont pas implicitement. Une référence au `main()` du
moteur couvre un bloc large : toute modification de ce bloc demande une revue
des règles liées.

Les constantes sont affichées comme expressions Python, sans exécuter leurs
imports ni développer les `*AUTRES_CHAMPS`. Le registre lui-même reste un texte
éditorial dont les modifications doivent être relues. Le générateur ne déduit
ni l'intention métier, ni la validité scientifique, ni la réussite d'un test à
partir de sa présence dans une page.
