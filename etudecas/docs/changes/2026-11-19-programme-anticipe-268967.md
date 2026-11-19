# Essai de programme usine anticipé pour 268967

**Le calendrier d'achat réagit dès janvier. Le lot est ensuite annulé au
recalcul hebdomadaire.** La règle expérimentale de réduction des ordres
figés considère que le besoin de Muret reste couvert sans ce lot.
L'exécution confirme donc un achat avancé et un stock de composant
immobilisé plus tôt, sans récupération de la production de mars.

La version MRP du 12 janvier contient deux besoins concordants de 1430
pour la semaine du 16 mars. Elle prévoit 110 495 étuis et 23 424,94 m du
composant 730384, au rapport de nomenclature de 0,212 mètre par unité.
Ces sorties planifiées justifient de tester un calendrier d'usine distinct
du calcul du besoin net de Muret. L'identité et le statut ferme de l'ordre
industriel restent inconnus. [Rapprochement des sources](2026-11-19-regles-et-programme-268967.md)

L'essai reprend le dernier calcul qualifié de 152 jours, avec les mêmes
stocks, horizons figés, sécurités, prévisions, demande hebdomadaire publiée,
calendriers et règles d'annulation. Le profil des autres usages physiques
est le même scénario reconstitué. La seule intervention avance un lot
simulé existant de **107 800 unités** au lundi 17 mars en s'appuyant
sur la version connue le 12 janvier. Le 17 mars est le premier jour ouvert
de la semaine source, choisi pour tester l'hypothèse. La série des
prélèvements réels d'étuis intervient dans la comparaison finale.

## Ce que l'essai change

L'adaptateur date le même lot du 12 au 20 janvier si le recalcul natif
conserve une proposition unique et équivalente. Les autres ordres gardent
leurs identités, quantités et dates au moment de la révision. Le 21 janvier,
le carnet fige l'ordre et émet ses besoins de composants. Le crédit de
réception planifiée garde la même identité. Le moteur exécute ensuite ses
contrôles habituels de stock, de réception, de matière disponible et de lots.
La quantité prévue est distincte de la matière effectivement consommée.

Sur les 25 premiers jours, le témoin et l'essai reproduisent les sorties
physiques et de planification avant le 12 janvier. La commande native
de 344135 part le 21 janvier, pour **120 000 unités**, avec réception prévue
le 25 février et disponibilité prévue le 3 mars. Les quatre tests mémoire
ciblés, la qualification courte et les 9 362 vérifications indépendantes
du démarrage passent.
[Preuve du démarrage](../../artifacts/testing/programme_anticipation_268967_20261119/validator/probe_review.json)

## Résultat sur 152 jours

La première commande de 344135 garde son identité et ses 120 000 unités.
Elle passe du 17 mars au **21 janvier**. Sa réception physique passe du
21 avril au **25 février** et sa disponibilité du 25 avril au **3 mars**.
Le 27 janvier, le lot avancé est annulé après vérification des besoins
datés et de la protection. Un lot de remplacement reste conditionnel dans
le plan. La première fabrication physique s'exécute le 9 mai avec une
autre identité, comme pour le calendrier physique du témoin.

Pour les deux produits, la production, le stock à Muret et le service
quotidien sont identiques au témoin. Sur les semaines documentées, 268967
cumulait et cumule **107 800 unités simulées face à 402 500 estimées**.
L'erreur hebdomadaire reste de 26 600 unités et l'erreur moyenne de stock
de 59 636 unités. Les quantités d'achat sur la fenêtre restent identiques
par article. Le 344135 immobilise 120 000 unités supplémentaires sur
55 jours en stock physique, soit 6 600 000 unités-jours. Cette mesure
porte sur une quantité et une durée. La valorisation économique du
réseau reste partielle.

La simulation complète et les 30 829 contrôles indépendants passent.
Ce résultat montre que la date avancée seule est annulée par la règle
de réduction. Le sens métier du signal est décisif : proposition usine
révocable, ou engagement d'usine à conserver.
[Comparatif HTML](../../resultats/programme_anticipation_268967_20261119.html) ·
[Preuves](../../artifacts/testing/programme_anticipation_268967_20261119/final_manifest.json)

## Contrôle sur 1810

Le même rapprochement au 12 janvier donne 144 631 unités pour chacun
des deux composants 338928 et 338929, aux jalons du 9 mars et du 6 avril.
Au 30 mars, leurs signaux divergent, à 228 276 et 99 654. Le carnet de
268091 conserve **20 ordres initiaux**, totalisant **1 945 715 unités**,
dont cinq de 141 795 unités. Le nombre de correspondances possibles
empêche d'affecter univoquement un signal concordant à du travail
supplémentaire. Le calcul traite 268091 comme contrôle des effets indirects
et conserve tous ses ordres initiaux.
[Rapprochement de 1810](../../artifacts/testing/programme_anticipation_268967_20261119/holdout_1810.json)

## Reproduction

L'expérience s'exécute dans un processus dédié. Le moteur nominal
dispose de ses points d'entrée habituels. La configuration explicite
du scénario et les cas préparés sont liés au manifeste local. Pour
refaire le calcul, utiliser une nouvelle destination dans le cas et
les arguments natifs associés.

```powershell
python -X utf8 -B -m etudecas.simulation.analysis.run_programme_advance_trial --case <cas.json> --scenario <scenario.json>
```
