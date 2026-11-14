# Placement des fabrications et comparaison au réel

Le placement des nouvelles fabrications sur une capacité réservée est implémenté
et testé. **Il ne rapproche pas encore la production de 268967 du réel avec les
paramètres actuels. La référence par défaut reste conservée.**

La [comparaison HTML locale](../../resultats/placement_capacitaire_20261114.html)
permet de sélectionner une semaine et de consulter les lots, les décisions de
lancement, les réceptions et les stocks. Les courbes distinguent production
industrielle estimée par consommation d'étuis, témoin simulé et variante simulée.
Les semaines absentes restent inconnues. Le cumul comparable n'est pas annuel.

## Changement et périmètre

Le recalcul hebdomadaire du reliquat mensuel est identique dans les deux essais
(`calendar_month_weekly_review_v1`). La seule intervention industrielle est
`finite_lot_calendar_v1` : après calcul des besoins nets et des lots, réserver la
capacité puis déplacer les dates de lancement et les besoins de composants.
Le recalcul du matin conserve cette règle ; le soir commence au lendemain.
Les engagements déjà exécutés ne sont pas refabriqués. La marge de planification
est combinée à la durée physique et au contrôle sans être ajoutée deux fois.

1920 n'applique toujours aucun lot usine au besoin transmis. Les stocks initiaux,
les lots, la demande, la sécurité source et les capacités restent identiques
entre témoin et variante. Les réservations concernent un couple usine/article,
sans inventer la charge des autres références de la machine.

Deux simulations synthétiques de 42 jours précèdent les deux simulations
industrielles de 135 jours, du 1er janvier au 15 mai 2025. Cette fenêtre était
fixée avant calcul pour inclure les premières fabrications de 268967. Le témoin
industriel prend 358,6 secondes, la variante 389,7 secondes (+8,7 %). Les quatre
calculs se terminent avec leurs sources et entrées inchangées.

## Résultats

| Mesure sur les semaines industrielles renseignées | Réel estimé | Témoin | Placement |
|---|---:|---:|---:|
| 268967 : unités achevées, 11 semaines | 295 750 | 107 800 | 107 800 |
| 268967 : écart au réel | — | −63,55 % | −63,55 % |
| 268967 : semaines avec production | 6 | 1 | 1 |
| 268091 : achèvements, ordres initiaux inclus, 18 semaines | 2 140 500 | 2 351 135 | 2 351 135 |
| 268091 : écart des achèvements au réel | — | +9,84 % | +9,84 % |
| 268091 : écart hebdomadaire absolu moyen des achèvements | — | 87 130 | 88 730 |

Pour 268091, le travail des **nouveaux** lots sur ces mêmes semaines reste
547 200 unités dans les deux variantes. Les ordres initiaux achevés ne sont pas
une mesure du travail réalisé pendant l'horizon : leur fabrication antérieure
n'est pas répartie sur des dates inventées. Sur les 135 jours entiers, les
nouveaux lots achevés passent de 547 200 à 662 400 ; cette différence se situe
dans la dernière semaine incomplète et n'améliore pas les livraisons clients.
L'encours final passe de 126 452 unités équivalentes travaillées à zéro.

Le stock physique de 268967 à 1920 reste identique. Pour 268091, l'écart absolu
moyen aux photos de stock baisse légèrement (225 563 à 224 047 unités), mais
le calendrier des achèvements est moins proche du réel et le stock utilisable
final baisse de 14 400 unités. Il n'y a donc pas de gain industriel global.

Pour 268967, les 575 818 unités demandées sont toutes expédiées de Muret le jour
de la demande. Les 559 809 unités reçues par les clients correspondent exactement
à la demande décalée des deux jours de transport simulés ; 16 009 unités restent
en transit à la clôture. Le ratio reçu/demandé de 97,22 % sur cette fenêtre ne
prouve donc pas une rupture de préparation. Les livraisons industrielles brutes
ne sont toujours pas identifiées par ces données.

Le cas synthétique prouve un effet utile dans une situation réellement limitée
par la capacité : pour les mêmes 400 unités fabriquées et 375 livrées sur 385
demandées, l'attente cumulée baisse de 1 005 à 865 unités-jours (−13,9 %). Les
achèvements sont mieux répartis. Ce résultat ne constitue pas une calibration.

## Pourquoi 268967 reste éloigné

Les deux simulations terminent leur premier lot le **21 avril**. Le paramètre
actuel autorise **154 000 unités par jour** pour un lot de **107 800** : une journée
suffit, et la marge de planification actuelle couvre déjà ce travail. Réserver
une capacité aussi élevée ne suffit pas à étaler la fabrication sur des semaines.

Le stock initial de 1920 est de 1 101 534 unités. Aucun ordre initial 268967 n'a
été retrouvé dans l'extraction des en-cours ni dans les engagements chargés ou
écartés. Le stock et l'encours nuls à l'usine restent des hypothèses. Le premier
MRP industriel du 5 janvier annonce une entrée prévisionnelle au dépôt en mai ;
ce n'est pas un ordre ferme de fabrication. Inventer un tel ordre pour obtenir
une production en mars ne serait pas justifié.

Une répartition d'un lot sur trois à quatre semaines demanderait, à titre de
simple calcul, 3 850 à 5 133 unités par jour avec sept jours de travail par
semaine : 30 à 40 fois moins que le paramètre actuel. **Ce n'est pas une cadence
industrielle mesurée ni un paramètre retenu.** Les créneaux réellement affectés
au produit, les autres fabrications de la machine et le programme figé peuvent
expliquer cette différence ; les données présentes ne les départagent pas.

La disponibilité initiale mérite un contrôle distinct : le MRP du 5 janvier
mentionne 108 017 unités présentes mais disponibles la semaine suivante, alors
que tout le stock initial du scénario est utilisable. Cette ligne ne prouve
aucune nouvelle fabrication et ne doit pas être transformée en ordre initial.

## Vérification et limites

- 52 tests de calcul et d'intégration en mémoire réussis ; 4 contrôles des
  commandes réussis. Les tests interdits de manipulation d'intégrité ne sont
  pas exécutés.
- Contrôles indépendants : 44 vérifications mémoire, 45 sur la paire synthétique
  et 191 sur la paire industrielle. La qualification native synthétique
  passe. Les erreurs initiales des lecteurs sont conservées avec leur correction.
- **La qualification industrielle globale n'est pas obtenue dans les deux
  variantes.** Elle signale cinq familles : rapprochement des transferts,
  budgets de fin de période et trois conventions de provenance/base des
  mouvements complémentaires. Les contrôles ciblés n'effacent pas ces refus.
- La documentation générée signale encore les cinq familles déjà désynchronisées
  (`lot_risk`, `scenario_comparison`, `execution_verification`,
  `material_traceability`, `audited_semantics`). Le présent guide est manuel.
- HTML et données contrôlés statiquement, syntaxe JavaScript compilée sans
  exécuter les interactions ; navigateur non exécuté conformément aux restrictions
  de la session.

Le placement est limité aux nouvelles propositions, à 365 jours et au mode de
continuation des lots d'une campagne engagée. Les promesses des engagements
existants peuvent rester trop précoces lorsque le conditionnement initial
partage la machine. Les quotas hebdomadaires et les matières sont encore
vérifiés à l'exécution ; ni capacité partagée complète ni gel industriel de
quatre/huit semaines ne sont déduits.

## Reproduire et poursuivre

```powershell
# Utiliser à chaque essai un dossier neuf.
python -B -m etudecas.simulation.current_reference --days 135 --forecast-consumption-policy calendar_month_weekly_review_v1 --output-dir etudecas/artifacts/testing/NOUVEL_ESSAI/control
python -B -m etudecas.simulation.current_reference --days 135 --forecast-consumption-policy calendar_month_weekly_review_v1 --production-capacity-planning-policy finite_lot_calendar_v1 --output-dir etudecas/artifacts/testing/NOUVEL_ESSAI/finite
```

Preuves et commandes exactes :
[protocole](../../artifacts/testing/placement_capacitaire_20261114/protocol.json),
[contre-recalcul industriel](../../artifacts/testing/placement_capacitaire_20261114/validator/industrial_review_v2.json),
[comparaison](../../artifacts/testing/placement_capacitaire_20261114/comparison/run_v3/manifest.json),
[rendu HTML final](../../artifacts/testing/placement_capacitaire_20261114/comparison/final_render_v2/manifest.json),
[manifeste final](../../artifacts/testing/placement_capacitaire_20261114/final_manifest.json).

La prochaine expérience utile doit partir de la durée d'un lot et des créneaux
machine réellement réservés à 268967, ou d'un programme de fabrication figé
daté. Sans cela, modifier une cadence jusqu'à rejoindre les points observés
serait un ajustement sans preuve. Les anomalies de qualification et la
disponibilité initiale restent des chantiers séparés. Aucun lancement annuel,
nouvelle série de multiplicateurs ni promotion du nominal n'est engagé ici.
