# Régénérer la référence et les cartes

Toutes les commandes partent de la racine du dépôt. Elles créent un nouveau
dossier et ne réutilisent pas silencieusement un ancien résultat.

## Référence MRP courante

```powershell
# Voir les entrées, le mode et la destination
python -B -m etudecas.regenerate --dry-run

# Simulation normale sur cinq ans
python -B -m etudecas.regenerate --days 1825

# Simulation et carte HTML complète
python -B -m etudecas.regenerate --days 1825 --with-map
```

Les valeurs par défaut sont :

```text
reference     = current
forecast-mode = coherent_scenario
days          = 1825
```

La référence charge exclusivement les fichiers versionnés suivants :

- `etudecas/config/mrp_reference_20261013.json` ;
- `etudecas/config/mrp_reference_20261013/graph.json.gz` ;
- `etudecas/config/mrp_reference_20261013/external_component_demand_daily.csv.gz` ;
- `etudecas/config/mrp_reference_20261013/supplier_neutral_floors.csv` ;
- `etudecas/config/mrp_reference_20261013/protocol.json` ;
- `etudecas/config/mrp_reference_20261013/engine_arguments.json` ;
- `etudecas/simulation/reference_mrp/`.

Les empreintes inscrites dans le manifeste empêchent d'utiliser un bundle
partiel ou modifié par erreur.

## Comparaisons explicites

```powershell
# Ancienne convention de prévision, même référence physique
python -B -m etudecas.regenerate --forecast-mode source_priority --days 1825

# Ancienne livraison de septembre
python -B -m etudecas.regenerate --reference historical_20260920 --scenario nominal

# Carte avec un calcul antérieur affiché comme comparaison
python -B -m etudecas.regenerate --days 1825 --with-map --comparison-run CHEMIN_RUN
```

`source_priority` n'est jamais sélectionné implicitement. Une exécution
historique ne devient pas la référence courante par la proximité de son dossier.

## Contenu de la carte courante

`--with-map` construit d'abord la carte réseau hors ligne, puis ajoute :

- les courbes de simulation ;
- les comparaisons avec les stocks, flux MRP, mouvements et demande disponibles
  pour 2025 ;
- le bilan annuel de demande, service, départs et stock à Muret ;
- le suivi détaillé d'un lot ;
- le parcours interactif amont–aval et aval–amont.

Les comparaisons industrielles restent limitées aux périodes réellement
documentées. Une valeur source absente n'est pas remplacée par zéro.

## Projection 2026–2029

Le mode `coherent_scenario` conserve 2025 puis prolonge le profil sur des cycles
de 52 semaines avec la croissance configurée de 5 %. La prévision utilisée par
le MRP et la demande physique simulée suivent le même scénario. Cette convention
sert à tester la cohérence prospective ; elle ne prétend pas connaître la
demande industrielle future.

Les règles et formules sont décrites dans
[`REGLES_MRP.md`](REGLES_MRP.md). Les essais qui ont conduit à cette convention
sont consolidés dans
[`archive/MRP_EXPERIENCES_2025.md`](archive/MRP_EXPERIENCES_2025.md).

## Études séparées du nominal

```powershell
python -B -m etudecas.simulation.studies --help
```

Les modes couvrent notamment sensibilité, scénarios ciblés, incertitude
temporelle, cascades, configurations fournisseurs, calibration fournisseur et
campagnes fournisseurs. Chaque étude écrit dans son propre dossier et ne
modifie pas le bundle nominal.

## Vérification après modification

1. Relire les tests ciblés et leurs fixtures.
2. Exécuter uniquement les cas concernés avec `python -m etudecas.toolbox tests`.
3. Lancer une simulation normale dans un nouveau dossier.
4. Qualifier ses CSV avec `python -m etudecas.toolbox qualify --run CHEMIN_RUN`.
5. Construire la carte depuis ce même run.
6. Vérifier statiquement les payloads et, lorsque l'environnement l'autorise,
   les interactions hors ligne.

Après l'incident Sophos, les tests qui altèrent volontairement des fichiers,
leurs dates ou leur présence restent interdits. Une vérification non exécutée
est signalée comme telle ; elle n'est jamais comptée comme réussie.

Les anciens CSV et HTML peuvent être supprimés une fois la reproduction
garantie. Le code, le bundle, les règles, les données sources et les preuves
compactes sont les éléments durables.
