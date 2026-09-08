# Pilote causal : cascade 338929 → M-1810 → 268091

## Question à laquelle répond le calcul

Lorsqu'un retard touche la liaison du composant 338929, l'état du réseau fait-il
apparaître d'autres signaux de tension, puis des effets mesurables sur le stock,
les lots de production, les commandes en retard et la disponibilité client de
268091 ?

## Comparaison

Le calcul croise deux choix dans un plan 2 × 2 : règles dépendantes de l'état
désactivées ou activées, et retard absent ou présent. Quatre trajectoires sont
donc exécutées :

1. règles dépendantes de l'état désactivées, sans retard imposé ;
2. règles dépendantes de l'état désactivées, avec le retard imposé ;
3. règles dépendantes de l'état activées, sans retard imposé ;
4. règles dépendantes de l'état activées, avec le retard imposé.

Dans chaque paire, la seule différence est le retard de +120 jours sur la
liaison SDC-VD0914360C → M-1810 pour 338929, de J228 à J407. Les trajectoires
réutilisent le même état initial et la même série de tirages aléatoires. Cela
permet de distinguer l'effet direct du retard de son amplification éventuelle
par les règles dépendantes de l'état.

Les familles de signaux actives portent sur le stock, la capacité, le délai, la
disponibilité, l'amont fournisseur, la fiabilité et le coût. La famille retirée
du périmètre de la réunion n'est pas activée.

## Horizon

- 240 jours de mise en régime, communs aux quatre simulations ;
- 720 jours mesurés, comme la campagne principale ;
- le calcul couvre toute la fenêtre de l'incident, les arrivées décalées et une
  période de retour vers le fonctionnement courant.

Le premier essai sur 600 jours a montré que certaines expéditions touchées
étaient encore programmées après J600. Il a donc été conservé comme résultat
intermédiaire et remplacé, pour la démonstration, par le calcul à 720 jours.

## Résultats calculés

- disponibilité de 268091 à la date demandée, sans compter les rattrapages
  tardifs comme des livraisons à l'heure ;
- retard client cumulé et retard restant à la fin ;
- stock de 338929 chez le fournisseur et à M-1810 ;
- quantité de 268091 libérée par la production et jours sans libération ;
- signaux secondaires apparus, disparus ou déplacés dans le temps à cause de
  l'incident ;
- lots finis 268091 dont la généalogie simulée contient l'incident initial ou
  un signal secondaire propre au scénario perturbé.

## Lecture correcte

La différence avec/sans retard est mesurée séparément lorsque les règles
dépendantes de l'état sont désactivées puis activées. La différence entre ces
deux effets mesure l'amplification produite par la couche dynamique. Ce pilote
démontre un mécanisme de cascade ; il ne donne ni la probabilité historique de
l'incident, ni une performance moyenne industrielle. Les règles qui créent les
signaux secondaires devront être validées avec les achats, la logistique et la
production.

Commande prévue :

```powershell
python etudecas/prototypes/scan_2027_risk_control/supplier_state_dependent_cascade_pilot.py `
  --output-dir C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_state_cascade_338929_meeting_20260904_v2_720d `
  --days 720 `
  --seed 340281 `
  --workers 2 `
  --execute
```
