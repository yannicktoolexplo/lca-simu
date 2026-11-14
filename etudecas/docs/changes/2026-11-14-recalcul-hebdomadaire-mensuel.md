# Recalcul hebdomadaire du reliquat mensuel — 14 novembre 2026

La règle demandée est implémentée dans `calendar_month_weekly_review_v1` et
raccordée au MRP daté. À chaque fin de semaine, la demande réelle connue consomme
le budget du mois et le reliquat est réparti sur les jours restants. Le taux
reste fixe entre les revues ; les demandes physiques continuent d'arriver chaque
jour. Nouvelle prévision au premier du mois, sans effacer stocks ou obligations.

**Exemple vérifié :** 1 000 − 300 = 700 sur trois semaines ; puis
700 − 250 = 450 sur deux semaines, soit 225 chacune. Les mois réels ne sont pas
artificiellement réduits à quatre semaines. La revue du dimanche soir pour le
lundi est une convention de calendrier déclarée.

[Comparaison lisible](../../resultats/recalcul_hebdomadaire_mensuel_20261114.html) ·
[Manifeste final](../../artifacts/testing/recalcul_hebdomadaire_mensuel_20261114/final_manifest.json)

## Mise en œuvre

Les budgets restent reconstruits depuis les prévisions sources connues à
l'ouverture du mois. Une version reçue plus tard ne modifie pas ce budget.
La consommation utilise la **demande réelle arrivée**, y compris non livrée,
conformément à la clarification utilisateur. L'audit distingue la demande
connue aujourd'hui de celle connue à la dernière revue et distingue le reste
comptable du programme figé entre revues.

Le mécanisme est commun, sans exception par référence. Les lots entiers,
capacités, délais, sécurités et ordres déjà engagés continuent à s'appliquer.
Ce n'est pas une contrainte imposant de fabriquer une quantité égale chaque semaine.

Commande disponible depuis la racine, avec un dossier de sortie neuf :

```powershell
python -B -m etudecas.regenerate --reference current --days 42 --forecast-consumption-policy calendar_month_weekly_review_v1 --output-dir etudecas/artifacts/testing/essai_mensuel_hebdo_42j
```

Cette commande est fournie pour le calcul industriel court suivant ; elle n'a
pas été exécutée ici. Son acheminement a été vérifié avec `--dry-run`.
Le mode reste explicite et limité à 365 jours ; aucun changement de référence
nominale ni relancement de carte industrielle n'a été effectué.

## Résultat des trois simulations synthétiques de 42 jours

Même graphe, mêmes demandes, stocks, ordres et capacités ; seule la règle de
consommation de prévision change. Lot fini de 100, capacité de 25 par jour,
demande totale 385. Le scénario couvre le passage janvier–février.

| Règle | Produits finis achevés | Livrés / demandés | Attente cumulée en unités-jours |
|---|---:|---:|---:|
| Référence à budget hebdomadaire | 400 | 375 / 385 | 815 |
| Budget mensuel recalculé chaque jour | 400 | 375 / 385 | 995 |
| Budget mensuel recalculé chaque semaine | 400 | 375 / 385 | 1 005 |

Une unité-jour est une unité encore en attente en fin de journée, additionnée
sur la période. Ce n'est ni une vente perdue ni un nombre de clients.
Le mode demandé ajoute ici 190 unités-jours d'attente par rapport au témoin,
soit 23,31 %, et 10 par rapport au recalcul quotidien. Le reliquat final de dix
unités est en transit dans les trois cas.

Par blocs successifs de sept jours depuis le 1er janvier, les achèvements
passent de **100 / 100 / 100 / 0 / 100 / 0** à
**100 / 0 / 200 / 0 / 100 / 0**. Le nouveau mode ne rend donc pas, à lui seul,
la production plus progressive. Ces blocs ne sont pas des semaines civiles.
Le volume total est conservé, mais le calendrier change.

## Vérification et portée

Les cas sélectionnés portent sur le calcul pur et son intégration dans les
fenêtres MRP : exemple demandé, taux constant entre revues, demande du jour,
causalité, changement de mois, versions connues et anciennes politiques.
Les trois exécutions normales ont duré environ 8 secondes chacune, avec sources
et entrée inchangées. Les 204 contrôles numériques de l'auteur rapprochent
les audits de prévision, événements de lots, stocks, matière, encours et service.
La revue indépendante et les résultats exacts sont consignés dans le manifeste.

L'essai est synthétique : il ne démontre pas un rapprochement de 268967 aux
observations industrielles. Aucun navigateur, Node, Word ou test d'altération
de fichiers n'est exécuté. Les contrôles documentaires exclus ou refusés sont
signalés séparément dans le manifeste, sans les compter comme réussis.

**Prochain test discriminant :** comparer le mode à revue hebdomadaire au
témoin sur un trimestre 2025 de 268967, mêmes données initiales et capacité,
avec travail, lots achevés, stocks et attente client. Si les concentrations
persistent, isoler la règle de placement des lots et le programme de production
avant toute augmentation de capacité ou ajout d'aléa.
