# Comparer les scénarios de la carte

La référence est le premier scénario classé nominal, ou portant un identifiant nominal historique ; à défaut, c'est le premier disponible. `reference_id` et `is_reference` rendent ce choix visible. Une référence de repli n'est pas pour autant une référence métier validée. Les résultats archivés sans sources permettant de reconstruire le comparatif ne sont plus republiés comme un classement validé.

## Score descriptif

Le contrat `customer_cost_v3_valuation_guard` applique :

`5 × perte de service en points + 3 × pic de reliquat en % de demande + 0,25 × surcoût opérationnel en %`.

La composante de coût intervient **uniquement si les deux scénarios déclarent une valorisation complète**. Sinon, `cost_delta_pct` vaut `null` et `score_excluded_dimensions` contient `cost`. L'exclusion ne signifie pas un effet économique nul. Les pertes de matières et les quantités de production reportées sont également exclues : leurs unités ne sont pas comparables à celles de la demande finale. `loss_qty_pct` et `replan_volume_pct` valent `null`.

La perte de service et le surcoût sont bornés à zéro ; le pic de reliquat est celui du scénario, sans soustraction du nominal. Les dénominateurs de demande et de coût de référence sont au moins 1 : cette convention doit être interprétée avec prudence lorsqu'ils sont nuls. Les poids 5, 3 et 0,25 ne sont pas calibrés industriellement. Le score n'est ni une probabilité, ni une preuve de causalité, ni une recommandation automatique.

Les vues « Top perturbateurs » utilisent `observed_impact_score`. Un score observé nul reste nul même si le champ historique `impact_score` est non nul. Comparer des scores dont les dimensions économiques incluses diffèrent n'est pas un classement économique valide.

## Trois périmètres monétaires

| Champ | Périmètre |
| --- | --- |
| `operating_cost`, alias historique `total_cost` | Coûts opérationnels simulés : possession, production, achats et transport opérationnels. |
| `external_procurement_cost`, alias `total_external_procurement_cost` | Approvisionnement externe, présenté séparément. |
| `economic_exposure` | Somme des deux périmètres précédents ; exposition économique du modèle. |

`economic_valuation` décrit la couverture de valorisation. Le statut `complete` exige aussi `complete=true`. Un statut incomplet, ou absent sur un résultat historique, interdit le classement économique. Les champs `known_cost_subtotal` et `known_economic_exposure_subtotal`, lorsqu'ils existent, sont privilégiés ; les valeurs affichées restent des **sous-totaux connus** lorsque la valorisation est incomplète. Des prix absents ne sont pas remplacés par un prix commun à des unités incompatibles.

Le choix du coût le plus bas porte sur l'**exposition économique**, seulement lorsque tous les scénarios comparés sont éligibles. La composante monétaire du **score descriptif**, elle, porte encore sur le **coût opérationnel** : ces deux périmètres sont explicitement distincts. Un coût opérationnel plus faible peut accompagner une baisse de production et de service ; il ne démontre pas une économie réelle.

## Écarts, service et reliquats

Les écarts signés sont calculés scénario moins référence. `fill_rate_delta_pp` est en points de pourcentage ; `cost_delta` et `operating_cost_delta` portent sur l'opérationnel, `external_cost_delta` sur l'approvisionnement externe et `economic_exposure_delta` sur leur somme. Des différences entre sous-totaux incomplets ne deviennent pas des économies comparables : `monetary_comparison_eligible=false` l'indique. `cost_delta_pct`, lorsqu'il est disponible, mesure uniquement le surcoût positif entrant dans le score.

Le service cumulé comprend les rattrapages ; il n'est pas un OTIF. Dans le comparatif, l'amorçage s'arrête au premier service client et reste documenté par `startup_backlog_days`. Les autres jours de reliquat sont comptés au seuil numérique de `1e-9`, fractions prévisionnelles comprises. Ils ne sont pas un nombre de commandes en retard.

Le **diagnostic de la fiche client** utilise un autre indicateur, nommé explicitement : pour un article en `UN`, un retard physique exige au moins 1 unité par article (`1 - 1e-9` de tolérance numérique). Les fractions inférieures sont conservées dans `forecast_residual_days`, les jours de retard physique dans `actionable_backlog_days`, et le comptage historique dans `backlog_days`. Pour les autres unités, le seuil positif reste `1e-9`. Il ne faut pas sommer les fractions de plusieurs articles pour fabriquer une unité en retard.

## Association et interactivité

La mention « service cumulé préservé dans ce scénario » décrit le résultat. Elle ne prouve pas que les stocks ou le MRP ont absorbé un incident précis. Les diagrammes de risques distinguent événement configuré, application locale observée et signaux aval associés. La proximité dans le temps et l'existence d'un chemin réseau ne suffisent pas à attribuer une perte client ou un coût : `causality_status=association_only`, `attributed_customer_loss_qty=null`, `attributed_cost=null`.

Les fenêtres de plusieurs événements peuvent se chevaucher : leurs volumes associés ne doivent pas être additionnés comme des pertes distinctes. Le score d'exposition des diagrammes n'est pas le score comparatif des scénarios.

L'enveloppe P10–P90 décrit les scénarios sélectionnés ; ce n'est pas un intervalle de confiance Monte Carlo. Une sélection de deux scénarios ne constitue pas une distribution probabiliste.

## Vérification et limites

Les tests comprennent des calculs vérifiables à la main, une valorisation inconnue ou incomplète, un service nul, des écarts signés et deux runs temporaires. Un cas négatif vérifie qu'un backlog préexistant ne devient pas une perte attribuée à un événement jamais appliqué. Les contrôles historiques rapprochent les chiffres des CSV et du graphe indiqué par le manifeste ; ils ne qualifient pas scientifiquement les hypothèses du modèle.

La revue navigateur vérifie séparément les valeurs affichées et les interactions sélectionnées. `map_delivery --browser-review <rapport.json>` relit les sources indépendamment des producteurs de la carte : les trois périmètres monétaires, leur couverture, le pic de reliquat hors amorçage et le score v3 sont contrôlés. Lorsque les colonnes monétaires journalières sont disponibles, leurs sommes sont rapprochées du résumé. Les tests refusent notamment un score calculé avec l'exposition à la place de l'opérationnel, une valorisation inconnue déclarée complète, et un résumé falsifié avec son HTML alors que les CSV sont restés inchangés. Une revue antérieure à une modification de l'HTML ou des sources n'est pas réutilisable. Ces parcours ne couvrent pas exhaustivement toutes les interactions.

Les [règles générées](generated/scenario_comparison/index.md) relient ces conventions au code et aux tests. `build-all`, `check-all` et `watch-all` ne lancent pas de simulation. Une empreinte mise à jour atteste une revue du changement référencé, pas la validité métier de l'ensemble du simulateur.
