---
name: code-modernization
description: Cartographier et moderniser un module existant, extraire ses règles métier et comparer avant/après sur les mêmes entrées. Utiliser pour une montée de version, une extraction progressive ou une migration du moteur de simulation.
---

# Moderniser un module avec des preuves de comportement

Partir du périmètre demandé. Pour une étude, rendre la carte, les règles et les options. Pour une migration demandée, poursuivre jusqu'au pilote exécuté par son point d'entrée habituel et aux comparaisons. Conserver les modifications locales de l'utilisateur.

## Choisir et conduire le pilote

1. Identifier la révision de départ, la version du langage ou de la dépendance, les appelants et la commande utilisée en exploitation. Recenser les données d'entrée, leurs unités, l'ordre des événements et les sorties consommées par les outils en aval. Identifier où les données anciennes entrent encore dans le système.
2. Suivre un cas de l'entrée à la sortie. Associer chaque règle à un emplacement dans le code, une condition d'activation et un résultat calculable. Distinguer les comportements constatés dans le moteur des pratiques confirmées par une source industrielle. Pour Etudecas, partir des contrats cités par `AGENTS.md`.
3. Choisir selon l'objectif. Pour une montée de version, relever les appels effectivement touchés par les changements de l'API. Pour une extraction progressive, choisir une responsabilité et ses consommateurs. Pour un changement d'architecture, spécifier d'abord les interfaces, les scénarios d'acceptation et le point de retour. Fixer les comportements à conserver et les changements expressément demandés.
4. Sur la version de départ, conserver une sortie de référence indépendante du code cible. Exécuter le pilote sur les mêmes entrées, calendrier, horizon, état initial et réalisations des aléas. Si la migration change l'ordre de consommation des nombres aléatoires, enregistrer les événements exogènes ou stabiliser les flux par source. Une graine identique ne suffit alors plus à établir que les perturbations sont identiques.
5. Comparer les sorties puis un cas limite réservé à la vérification. Pour Etudecas, compléter les preuves avec les invariants et les tests ciblés de [qualification](../etudecas-qualify/SKILL.md). Lors d'une reprise, indiquer le dernier module qualifié, les cas restants et la première divergence encore ouverte.

## Comparer les résultats

Retenir des sorties **produites par les deux exécutions**. Pour un stock, exporter par article et site les événements datés, leurs quantités signées, le statut du lot et les stocks physique et utilisable. Conserver l'ordre des événements dans la journée lorsqu'il intervient dans la décision. Une égalité des stocks finaux peut cacher une rupture intermédiaire. Un changement approuvé de règle métier dispose de son propre résultat attendu.

Réunir les sorties de chaque version dans deux sous-dossiers d'un même dossier de preuves neuf. Y écrire un fichier `cases.json` tel que celui-ci, en adaptant les chemins aux fichiers réellement produits.

```json
{
  "system": "rejeu-pilote",
  "legacy": {"label": "Version de départ"},
  "new": {"label": "Version modernisée"},
  "cases": [
    {"id": "flux", "legacy": "avant/mouvements.csv", "new": "apres/mouvements.csv"},
    {"id": "stock", "legacy": "avant/stocks.csv", "new": "apres/stocks.csv"}
  ]
}
```

Depuis la racine du dépôt, remplacer le dossier d'exemple par le dossier de preuves réel.

```shell
python .agents/skills/code-modernization/scripts/compare.py preuves/rejeu-pilote/cases.json --out preuves/rejeu-pilote/equivalence.json
```

Le comparateur utilise la bibliothèque standard Python et examine les octets. Pour des formats dont seule la sérialisation varie, exporter des tableaux avec le même schéma, encodage et format de date. Conserver aussi les originaux et décrire toute normalisation. Les quantités entières, dates, statuts et identifiants se comparent exactement. Réserver les tolérances justifiées aux sorties numériques qui le nécessitent.

Lire les verdicts par cas, les fichiers absents et les écarts acceptés. Un code de retour nul peut inclure un écart que le demandeur a explicitement accepté. Rendre les différences encore inexpliquées avec le premier événement concerné et le périmètre effectivement comparé. L'équivalence sur les cas vérifiés établit ce que le changement préserve dans le logiciel. La validation industrielle reste une question distincte.

## Provenance

Ce parcours Codex adapte au dépôt les étapes d'analyse, d'extraction des règles, de migration et de vérification du plugin **Code Modernization** d'Anthropic, version 1.1.0. Le fichier `scripts/compare.py` provient de cette révision, à l'identique. Les commandes et le panneau interactif propres à Claude Code sont documentés dans la distribution d'origine. [Source épinglée](https://github.com/anthropics/claude-plugins-official/tree/0fbfda5a91f4adc311daca25acc99132f40f0b6e/plugins/code-modernization) · [Licence Apache 2.0](LICENSE).
