# Etudecas

Etudecas simule une chaîne pharmaceutique complète : demande client, centre de
distribution, usines de produits finis, semi-finis, matières et emballages,
fournisseurs, transports, stocks, MRP et traçabilité par lots.

Le moteur reste un modèle de dynamique des systèmes dépendant de l'état. Les
études de sensibilité, cascades de risques, criticité fournisseur, contexte
fournisseur, audits et Monte-Carlo réutilisent le même parcours nominal sans
modifier ses données de sécurité.

## Parcours courant

La référence active est `coherent-MRP-20261014`. Elle est autonome : le code,
le graphe et le profil de besoins complémentaires nécessaires sont versionnés.
Elle ne dépend d'aucun ancien dossier sous `artifacts/testing`.

```powershell
# Examiner la commande sans calculer
python -B -m etudecas.regenerate --dry-run

# Recalculer cinq ans et construire la carte complète
python -B -m etudecas.regenerate --days 1825 --with-map

# Comparer explicitement avec une exécution antérieure
python -B -m etudecas.regenerate --days 1825 --with-map --comparison-run CHEMIN_RUN
```

Les valeurs par défaut sont `--reference current` et
`--forecast-mode coherent_scenario`. Le mode antérieur reste disponible avec
`--forecast-mode source_priority`. La livraison historique de septembre reste
reproductible avec `--reference historical_20260920`.

La carte courante est
[`resultats/corrections_5ans_20261014/carte_simulation_5ans_corrigee.html`](resultats/corrections_5ans_20261014/carte_simulation_5ans_corrigee.html).
Elle contient le réseau, les courbes, les comparaisons industrielles 2025, un
bilan annuel et les deux suivis de lots. Les années 2026 à 2029 sont un scénario
prospectif déclaré, pas des observations industrielles.

## Structure utile

| Dossier ou fichier | Rôle |
|---|---|
| `simulation/engine/` | Moteur physique et planification MRP |
| `simulation/current_reference.py` | Entrée de la référence MRP courante |
| `simulation/reference_mrp/` | Adaptateurs nécessaires à cette référence |
| `config/mrp_reference_20261013/` | Bundle autonome compact de la référence |
| `visualization/maps/` | Carte, comparaisons et interactions |
| `simulation/studies.py` | Sensibilités, risques, fournisseurs et incertitude |
| `data/source/` | Données industrielles, jamais remplacées par les résultats simulés |
| `tests/` | Contrôles ciblés du moteur, des lots et de la carte |
| `docs/REGLES_MRP.md` | Règles actives et formules |
| `docs/archive/MRP_EXPERIENCES_2025.md` | Chronologie consolidée des essais MRP |

## Conventions métier

- Les quantités physiques en `UN` sont entières.
- Les jours de sécurité suivent le calendrier lundi–vendredi.
- Muret utilise 100 % des jours de sécurité source.
- Prévu, réservé et exécuté restent distincts.
- Simulation et observation industrielle restent identifiées séparément.
- La théorie BOM ne remplace pas le registre de consommation matière.
- `tau_process` reste une marge de planification à confirmer.
- Le nominal et les sensibilités utilisent des paramètres séparés.
- Les deux suivis de lots sont conservés.

## Autres études

```powershell
python -B -m etudecas.simulation.studies --help
python -B -m etudecas.simulation.studies cascade --help
python -B -m etudecas.simulation.studies sensitivity --help
python -B -m etudecas.simulation.studies supplier-configurations --help
python -B -m etudecas.simulation.studies temporal --help
```

Les résultats générés sont remplaçables : la source, la configuration et les
commandes de reproduction sont conservées, pas toutes les campagnes
intermédiaires.

## Documentation

- [Commandes opérationnelles](OPERATIONS.md)
- [Régénération des résultats](docs/REGENERER_RESULTATS.md)
- [Règles MRP actives](docs/REGLES_MRP.md)
- [Référence MRP qualifiée du 14 octobre 2026](docs/MRP_REFERENCE_20261014.md)
- [Données sources et limites](docs/DONNEES_SOURCES.md)
- [Validation ciblée](docs/TEST_VALIDATION.md)
- [Accueil des cartes conservées](index.html)

Les contrôles techniques vérifient les calculs et les contrats de données. Ils
ne certifient pas à eux seuls la calibration industrielle ni la causalité d'un
scénario de risque.
