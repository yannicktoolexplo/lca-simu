# Retour industriel : règles MRP à rapprocher du simulateur

Informations transmises dans la conversation le **13 novembre 2026**, puis
précisées par l'utilisateur. Elles constituent un témoignage sur les pratiques,
pas un export d'événements ERP. La sous-capacité de 268967 est explicitement
rapportée pour 2025 ; la date d'effet historique des autres règles reste à préciser.

L'audit porte sur `dev_yannick`, commit `394af4669`, sans changement du moteur,
des données source, du nominal ni des cartes. Les preuves sont sous
`etudecas/artifacts/testing/retour_industriel_20261113/`.

## Ce que les précisions confirment

| Sujet | Information reçue | Contrat à conserver ou préciser |
|---|---|---|
| Prévision | Révision mensuelle ; consommation par la demande réelle ; reliquat réétalé chaque semaine ; nouveau compteur au premier du mois. | L'utilisateur confirme que « vendu » désigne ici la **demande réelle**, indépendamment des quantités livrées. |
| Gaillac | Production conservée et libérée sur place ; livraison à la demande, possible sous le standard. | Séparer taille de fabrication, quantité demandée et quantité expédiée. Le témoignage ne confirme pas les durées de contrôle. |
| D1920 | Besoin transmis sans taille de lot propre, décalé par la sécurité ; l'usine applique sa lotification et peut pousser plus tôt. | Ne pas transformer cette absence de lotification du besoin en absence de contraintes physiques de transport ou de contrôle. |
| Plan de production | 1810 achète les matières selon son propre programme de production. | Le programme de fabrication doit porter les besoins composants ; une réservation n'est pas une consommation. |
| Horizon figé | Quatre semaines à 1810, huit à 1430. | La restriction exacte des modifications et la date de référence de l'ordre restent à confirmer. |
| Capacité 268967 | Sous-capacité machine pendant toute l'année 2025. | Cause industrielle rapportée ; capacité disponible, charge partagée et calendrier non quantifiés. |
| 268091 | Aucun problème de « provision » rapporté. | Périmètre du terme à préciser ; ce n'est pas une mesure de capacité ou de service parfait. |
| Packaging 338929 | Les deux semaines évoquées concernent ce packaging, pas le produit fini 268091. | Quantité, détenteur du stock, durée jusqu'à réception ou jusqu'à disponibilité encore inconnus. |
| Début de mois | Les premières semaines de prévision de janvier/février paraissent erronées. | Suspicion à expliquer à la source ; aucune valeur remplacée. |

## Écart démontré : consommation hebdomadaire au lieu du budget mensuel

La source commerciale comporte 13 versions de prévision, selon une cadence
mensuelle. L'import et le moteur imposent cependant
`weekly_actual_orders_v1` : la demande reçue consomme la prévision de la semaine,
dont le reliquat expire le dimanche. Le changement de mois n'est pas son reset.

Preuves : `simulation_prep/inject_mrp_seed_data_v2.py:511` ;
`simulation/engine/run_first_simulation.py:4781`, `:5171`, `:5336` ;
`docs/REGLES_MRP.md:677`. Le résumé natif déclare cette convention et conserve
`industrial_rule_confirmed: false`.

Dans le calcul courant de 56 jours, au **1er février 2025**, le compteur de
268091 porte encore sur la semaine du **27 janvier au 2 février** : prévision
de 174 010 UN, demande cumulée de 62 012 UN, reliquat de 111 998 UN.
Le 2 février, 101 662 UN non consommées expirent ; le nouveau compteur commence
le 3 février. Source :
`artifacts/testing/demonstration_01_etat_20261113/compatibility/v3/run/data/mrp_forecast_consumption_daily.csv`,
lignes 64–69. Le moteur n'a pas changé depuis ce calcul.

La règle industrielle peut être spécifiée simplement :

> **Reste du mois = maximum(prévision du mois − demande réelle cumulée du mois, 0).**
> La prévision est le budget connu pour le mois courant ; la demande cumulée
> comprend uniquement la demande réelle déjà connue à la date de décision ;
> le reste est la prévision encore à répartir dans ce mois.

Le réétalement doit respecter les poids de périodes convenus, sans traiter tous
les mois comme quatre semaines. Dans l'exemple **synthétique** à quatre périodes :

| Prévision initiale | Demande réelle première période | Reste industriel | Trois semaines futures conservées par le code actuel |
|---:|---:|---:|---:|
| 1 000 UN | 300 UN | 700 UN | 750 UN |
| 1 000 UN | 200 UN | 800 UN | 750 UN |

Le deuxième résultat a été obtenu en appelant réellement `RollingMrpForecast`
en mémoire, sans simulation physique : `current_weekly_probe.json`. Trois tests
ciblés passent également ; ils vérifient **la convention hebdomadaire actuelle**,
pas l'implémentation d'une nouvelle règle mensuelle.

Pour 700 UN, une répartition entière illustrative est 233, 233 et 234 UN.
La remise à zéro du premier février concerne le compteur de consommation de
prévision : elle ne supprime ni retard de demande réelle, ni stock, ni encours,
ni ordre ferme. Les 34 oracles indépendants vérifient notamment cette séparation.

## Premières semaines : anomalie source et ouverture à vérifier

Dans la première version de projection, les valeurs suivantes sont présentes :

| Article | Semaine | Prévision source, UN | Demande historique, UN | Cellule prévision |
|---|---|---:|---:|---|
| 268091 | 06/01/2025 | 329 532 | 35 719 | `Projection!D2` |
| 268091 | 03/02/2025 | 273 757 | 66 112 | `Projection!D54` |
| 268967 | 06/01/2025 | 5 037 | 43 797 | `Projection!D678` |
| 268967 | 03/02/2025 | 9 377 | 26 844 | `Projection!D730` |

Fichier : `data/source/Flow_Data_Customer_Demand.xlsx`.
Ce rapprochement signale des écarts ; il ne démontre pas à lui seul une erreur.
Il faut expliquer leur périmètre et leur construction avec l'industriel.

La première version ne couvre pas la semaine du 30 décembre. Les premiers jours
de janvier prennent alors le taux prévisionnel de la période connue la plus
proche, celle du 6 janvier. Le journal le déclare comme repli, pas comme demande
réelle. Janvier commence un mercredi, février un samedi : leurs fragments de
première semaine sont respectivement de cinq et deux jours calendaires.
La date de connaissance des versions est reconstruite au lundi indiqué ; leur
date réelle de publication industrielle n'est pas démontrée.

## Horizon figé : proposition de contrat, pas arrêt d'usine

L'interprétation évoquée par l'utilisateur est cohérente avec une barrière de
planification : ne pas ajouter automatiquement un nouvel ordre de fabrication
à réaliser dans la fenêtre, ni y avancer un ordre. Les ordres déjà engagés
continuent à s'exécuter et leurs composants restent nécessaires.

Les ERP distinguent cette règle des autorisations de report ou d'annulation
([exemple documenté Oracle](https://docs.oracle.com/cd/E18727-01/doc.121/b31558/T478564T478850.htm)).
Elle ne confirme donc pas à elle seule une interdiction de toute modification
de date et de quantité dans les deux usines. La borne de référence — début,
fin ou disponibilité de la fabrication — et les exceptions restent à préciser.

Aucun horizon figé de production de quatre/huit semaines n'a été trouvé dans
le parcours courant : revue quotidienne, horizon glissant de 364 jours et
engagement à la première exécution physique sont d'autres conventions.

## Gaillac : le besoin et l'expédition restent parfois liés au lot fabriqué

- **693055** : l'expédition est fractionnable (`transfer_multiple_qty=0`), mais
  la commande interne est encore arrondie à 600 kg (`order_multiple_qty=600000 G`).
- **773474** : minimum et multiple de 3 200 kg, consolidation de sept jours,
  hérités du lot de fabrication par une règle dérivée, pas une preuve ERP.
- La libération à Gaillac existe déjà : 28 jours ouvrés pour 693055 et 33 pour
  773474 ; la seconde durée est une hypothèse. La nouvelle information confirme
  le lieu de libération, pas ces durées.

Sources : `config/mrp_reference_20261013/graph.json.gz`,
`meta.internal_component_policy.rows` ; `simulation/lot_policy/engine_adapter.py:46`
et `:95` ; consommateurs `run_first_simulation.py:8138` et `:20968`.

Essai discriminant à préparer : besoin de 300 kg et stock déjà libéré de
5 000 kg ; expédier 300 kg sans imposer un nouveau lot fabriqué de 3 200 kg
ni une attente de sept jours. Tester séparément l'arrondi de commande et le
fractionnement physique ; conserver les engagements existants.

Le transfert usine de produits finis vers D1920 pousse déjà le stock libéré
et non réservé (`push_released_available_v1`). Les contrôles des PF à D1920
de 10/15 jours ouvrés concernent d'autres flux que la libération de Gaillac :
ce témoignage ne justifie pas de déplacer tous les contrôles.

## Capacité machine et packaging : ne pas transformer un témoignage en quantité

La capacité courante de M1430 est de 154 000 UN/jour, construite comme un
équivalent lot/semaine, avec vingt démarrages/semaine ; celle de M1810 est de
203 550 UN/jour. Ces conventions ne décrivent pas la capacité machine réellement
disponible en 2025. La sous-capacité rapportée de 268967 est une cause étayée
par témoignage, mais son calendrier et son amplitude ne sont pas encore identifiés.

Pour **338929**, l'offre est `VD0914360C → M1810` :
`268091.xlsx!FIA!F20=42 jours`, `G20:H20=5000 UN` comme standard documentaire.
Le contrôle à réception est distinct : six jours ouvrés
(`Flow_Data_MRP_results.xlsx!Feuille1!E705`). Le témoin natif commande à J4,
reçoit physiquement à J46 et rend disponible à J54 : 42 jours avant réception,
50 avant disponibilité selon le calendrier du modèle.

42 jours représentent six semaines. Un plafond technique de 84 jours existe
dans `delay_step_limit` ; il ne prouve pas que les « douze semaines » citées par
l'industriel désignent ce champ ou un délai réellement appliqué.

Les deux semaines doivent être une information sourcée séparée, avec périmètre
et conditions. Si elles désignent la réception physique, un simple oracle de
dates à commande J4 donne J18 physique puis J26 utilisable, contrôle conservé.
Ce n'est pas une preuve de disponibilité de toute quantité demandée en deux semaines.
Le stock fournisseur exporté de 180 UN est explicitement inactif dans le netting
des promesses agrégées ; il ne mesure pas le stock industriel mobilisable.

## Ce que montrent les résultats de l'autre équipe

Les images portent sur **leur version v2c**, pas sur ce commit ni sur nos calculs.
La courbe noire est une production **estimée à partir des étuis**, la grise des
entrées à D1920, l'orange une production simulée. Les dates et périmètres diffèrent.
La grille compare un stock incluant la marchandise en contrôle. Sans séries,
paramètres et formule des métriques, ses résultats restent rapportés, non recalculés.
La note de leur grille précise également que la version « précédente » utilisait
encore une compensation. Sans protocole détaillé, la comparaison ne permet pas
d'attribuer une amélioration à une règle isolée.

| Indicateur rapporté | 268091 précédente → v2c | 268967 précédente → v2c |
|---|---|---|
| Critères satisfaits | 3/7 → 3/7 | 4/7 → 6/7 |
| Écart production annuelle, seuil ±10 % | −4 % → −4 % | +12 % → −9 % |
| Biais moyen de stock, seuil ±10 % | +39 % → +43 % | −1 % → −6 % |
| Pire trimestre, seuil ≤30 % | 64 % → 96 % | 37 % → 33 % |
| Corrélation, seuil ≥0,7 | 0,56 → 0,32 | 0,71 → 0,85 |

Le score inchangé de 268091 masque donc trois dégradations ; 268967 s'améliore,
mais son pire trimestre reste hors seuil. Le critère de comparaison à une droite
de stock moyen demande sa formule et son dénominateur : le résultat rapporté
de 268967 passe de +16 % non accepté à +39 % accepté, sans reconstitution ici.
Aucune promotion globale ni importation de paramètres v2c n'en découle.

## Suite priorisée

1. Spécifier puis comparer la consommation **mensuelle** sur la demande réelle,
   les fragments de semaines et le reset de février, sans corriger les cellules
   source suspectes ni inventer leurs dates de publication.
2. Introduire les horizons figés comme règle explicite de plan de production,
   avec maintien des ordres engagés et critères de dates/quantités déclarés.
3. Séparer les quantités demandées et livrées de Gaillac des lots fabriqués ;
   comparer un petit transfert réellement couvert par le stock libéré.
4. Obtenir une capacité machine disponible et une charge partagée pour 268967 ;
   identifier le stock et le périmètre des deux semaines de 338929.

Les cartes précédentes sont préservées et ne sont pas présentées comme recalculées
avec ces nouvelles règles. Le manifeste de ce travail est
`artifacts/testing/retour_industriel_20261113/final_manifest.json`.
