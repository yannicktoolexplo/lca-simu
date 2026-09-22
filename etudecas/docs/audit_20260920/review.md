**Contre-revue indépendante des constats métier — 20 septembre 2026**

**Verdict pour le planificateur supply chain et le responsable industriel**

Trois constats majeurs sont confirmés par vérification indépendante : la valorisation de secours dépend arbitrairement des unités d'autres articles ; un événement sans application constatée peut être présenté comme ayant atteint le client ; le classement « coût total » change de sens selon l'inclusion des approvisionnements exceptionnels. Ces points justifient de limiter les décisions prises à partir des recommandations et comparaisons économiques actuelles.

Cela ne démontre ni que tous les flux physiques sont faux, ni que toute différence de scénario est dépourvue de sens. La carte peut servir à explorer le scénario et ses données. Pour prioriser une action fournisseur ou arbitrer un stock contre un coût, il faut d'abord rendre explicites la preuve, le périmètre économique et le caractère prévu ou exécuté des mouvements.

**Méthode et indépendance**

Cette contre-revue a commencé avant la publication des rapports `model_data.md` et `numeric_map.md`, sur leurs scripts et preuves déjà disponibles et les constats transmis par leurs auteurs. Les deux rapports ont ensuite été relus intégralement. Leurs qualifications concernant les délais annoncés, coûts conditionnels, mouvements futurs, consommation théorique, radars estimés et limites de couverture sont appropriées. La contre-revue ne modifie pas leurs analyses. Les trois contrôles principaux ci-dessous ont été refaits par des appels Python distincts et une lecture directe des CSV, sans exécuter les scripts des auteurs et sans réutiliser uniquement leurs agrégats JSON ; la transformation de demande a ensuite fait l'objet d'un quatrième contrôle ciblé.

Références examinées : `model/source-audit.json`, `model/audit_sources.py`, `model/risk-semantics.json`, `model/audit_risk_semantics.py`, `model/causality-counterexample-payload.json`, `numeric/numeric_summary.json`, sous `etudecas/artifacts/testing/full_audit_20260920/`. Les sources applicatives pertinentes ont été relues. Les comptes de tests ne sont utilisés comme preuve ni de calibration industrielle ni de validité scientifique.

Les vérifications sont en lecture seule pour le code et les données existantes. Aucun nouveau run du moteur, recalibrage, nettoyage ou changement de paramètre n'a été effectué.

**R1 — Valorisation de secours non invariante aux unités : confirmé**

Code vérifié : `etudecas/simulation_prep/prepare_simulation_graph.py:128`, fonction `derive_item_unit_value_map`, puis `holding_cost_per_unit_day_from_value` à la ligne 171. La première convertit chaque prix vers l'unité propre de son article, puis prend une médiane commune de ces valeurs numériques. La seconde attribue cette médiane à un article sans prix connu.

Contre-expérience indépendante : un article connu vaut 10 par kg ; un autre article, inconnu, est exprimé en UN. Sans modifier aucune propriété de l'article inconnu, la simple représentation du premier article en kg ou en g produit :

| Unité de l'article connu | Taux de possession attribué à l'article inconnu, par UN et par jour |
|---|---:|
| KG | 0,005479452054794521 |
| G | 0,000005479452054794521 |

Le ratio est exactement 1 000. Le prix physique de l'article connu n'a pourtant pas changé : la conversion conserve 10/kg = 0,01/g. Cette dépendance du prix d'un article UN à l'unité de représentation d'un autre article constitue un défaut de règle de valorisation, pas un simple désaccord sur le niveau du taux annuel.

Portée à conserver : le problème vise les valeurs de secours, et donc les coûts et classements qui en dépendent. Il ne démontre pas une erreur de conversion des quantités physiques. Les sommes importantes de holding attribuées au fallback dans `source-audit.json` établissent la matérialité dans le cas étudié, mais cette contre-revue n'a pas rejoué indépendamment chaque ligne du ledger de valorisation. La preuve minimale incontestable est la non-invariance ×1 000.

Décision recommandée : ne pas qualifier une stratégie d'économiquement optimale avant de remplacer ce fallback par une valeur article justifiée ou de marquer la valorisation comme inconnue. Une famille homogène peut aider à proposer une estimation, mais kg, mètre et unité ne doivent pas être mélangés numériquement dans une médiane sans base commune.

**R2 — Attribution au risque d'un backlog simplement concomitant : confirmé, sans généralisation abusive**

Code vérifié : `etudecas/visualization/maps/supplier_risk_panels.py:3194` sélectionne les lignes de backlog par fenêtre temporelle et article aval ; les lignes suivantes attribuent `service_client` dès que ces lignes existent. Cette branche précède celle qui distingue un événement seulement configuré.

Contre-expérience indépendante : relecture de la petite fixture déjà enregistrée, puis nouvel appel à `build_simulated_risk_global_diagnostic_payload`. L'événement `CONFIGURED_BUT_NEVER_APPLIED` retourne simultanément :

- `local_application.applied = false` et zéro ligne d'application ;
- zéro retard de production associé ;
- `stage = service_client` et `absorption_label = Client atteint` ;
- action de priorité `high`, avec proposition d'accélération, achat spot ou seconde source.

La construction de cette recommandation ne requiert donc ni application constatée de l'événement, ni chemin causal quantifié jusqu'au client, ni comparaison contrefactuelle. Le constat « cette logique peut produire une attribution non démontrée » est solide.

Limite essentielle : la fixture n'est pas une campagne industrielle réelle et ne prouve pas que toutes les alertes du livrable sont fausses. L'absence de fichier d'application ne prouve pas, à elle seule, l'absence physique d'un incident. Elle doit néanmoins empêcher d'annoncer une preuve positive de propagation. Il faut distinguer événement configuré, application tracée, exposition généalogique et effet causal estimé.

Décision recommandée : présenter cette sortie comme une association à investiguer tant que la preuve manque. Une action fournisseur coûteuse ne doit pas être priorisée automatiquement à partir de cette seule fenêtre. Pour attribuer un écart au scénario, comparer des trajectoires appariées ; pour attribuer cet écart à un événement individuel, préciser encore le dispositif d'identification et les interactions entre événements.

**R3 — Classement économique : chiffres réconciliés, libellé insuffisant**

Contre-calcul indépendant depuis `data/first_simulation_daily.csv` des deux runs `corrected_map_20260918` et `scenario_runs/state_dependent_full` :

| Périmètre simulé | Nominal | Risques | Risques moins nominal |
|---|---:|---:|---:|
| Coût opérationnel `total_supply_cost_day` | 289 514 141,0706 | 262 259 663,9399 | −27 254 477,1307 |
| Approvisionnement exceptionnel | 85 778 749,9432 | 129 784 089,1809 | +44 005 339,2377 |
| Exposition économique agrégée | 375 292 891,0138 | 392 043 753,1208 | +16 750 862,1070 |

Les très petits écarts avec les valeurs de synthèse proviennent de l'utilisation des séries CSV arrondies ; ils ne changent ni le signe ni le classement. Les valeurs sont dans l'unité monétaire du modèle : elles ne sont pas ici certifiées comme coûts réels comptables.

Code vérifié : `etudecas/simulation/engine/run_first_simulation.py:14733` construit explicitement le coût opérationnel ; les lignes 14737–14743 ajoutent l'exceptionnel pour produire `total_economic_exposure_day`. `etudecas/visualization/maps/scenario_comparison_payload.py:575` présente pourtant le gagnant sous « Cout total le plus bas » à partir de `total_cost`.

Le défaut n'est pas une erreur d'addition du moteur : c'est une ambiguïté de périmètre pour la décision. Le risque apparaît moins cher sur les opérations, mais plus cher avec l'exceptionnel. Une baisse des dépenses opérationnelles peut aussi accompagner moins de production ou moins de stock ; elle ne constitue pas automatiquement un gain d'efficacité.

Décision recommandée : montrer au moins coût opérationnel, exceptionnel et exposition agrégée, avec unités, horizon, niveau de service et hypothèses. Ne pas appeler ces écarts « économies réalisées » ou « pertes causées » sans qualification supplémentaire. La fragilité de valorisation de R1 interdit également de traiter l'exposition agrégée comme une vérité économique calibrée simplement parce qu'elle est plus complète.

**R4 — Déplacement de la demande par le lissage MRP : confirmation complémentaire**

Après publication de MD-01, le classeur `etudecas/data/source/demand_PF.xlsx`, feuille `Demande`, a été rouvert indépendamment : l'article 268091 porte bien 13 300 UN en semaine 1, puis 35 719 en semaine 2. Le recalcul direct des lignes J0 à J6 de `production_demand_service_daily.csv` donne 22 908,142858 UN pour la première semaine. La lecture du moteur confirme que `demand_target_today` est construit avec la fenêtre de lissage MRP (`run_first_simulation.py:10079`), puis utilisé pour satisfaire le client (`:11688`). Le constat d'une demande réalisée transformée par un paramètre annoncé comme signal de planification est donc confirmé, sans dépendre des semaines négatives de l'autre article.

Cela ne démontre pas une perte de conservation du volume annuel ; cela démontre un déplacement de son échéancier. Pour le planificateur, cette distinction est déterminante : un bilan annuel juste peut masquer une simulation des ruptures, lancements et actions sur d'autres dates que celles de la demande source. Conserver séparément source, prévision MRP et demande réalisée ; si la transformation est intentionnelle, la nommer comme scénario distinct.

**Qualifications utiles pour éviter d'autres faux positifs**

**Expéditions au-delà de l'horizon.** La preuve modèle relève 167 lignes dont le départ est postérieur au dernier jour simulé. Cela peut représenter un engagement ou une réservation planifiée, et n'est pas intrinsèquement une incohérence physique. En revanche, le statut doit permettre de distinguer réservé, départ prévu, expédié et reçu. La lecture indépendante du moteur à `run_first_simulation.py:13374` confirme que les dépenses et quantités journalières sont mises en attente dans `scheduled_lane_release_metrics` lorsque le départ est futur. La seule présence de ces lignes ne prouve donc pas une surfacturation des totaux journaliers. Le risque confirmé concerne le sens des tables/statuts et leurs consommateurs qui additionneraient toutes les lignes sans filtre de date.

**Délai futur utilisé comme observation.** `run_first_simulation.py:13122` ajoute un délai simulé à une structure nommée observations ; à la ligne 13780, cette valeur alimente des déclencheurs `observed_lead_ratio`. Une ETA prévisionnelle est une information légitime pour un planificateur. Il faut donc éviter de conclure « anticipation impossible » uniquement parce que la réception est future. Le problème est de traiter une prévision ou un tirage latent du simulateur comme une mesure déjà réalisée, sans contrat d'information explicite. Pour une évaluation de politique réactive, définir ce que l'acteur connaît à la décision et séparer ETA annoncée, délai prévu et délai constaté après réception.

**Consommation théorique BOM et mouvements exécutés.** Les constats transmis par l'audit numérique sur une consommation calculée comme ratio BOM × production doivent être qualifiés comme un écart de représentation si le ledger débite autrement, notamment avec arrondis physiques. La première version de `material_table_reconciliation.json` indiquait une consommation physique nulle : ce point a été rejeté par la contre-revue et signalé à son auteur. Une lecture directe de `production_lot_events.csv` pour `M-1430` et `item:042342` donne **429 321 288 UN** pour `event_type=production_consume`, face à **429 321 261,6 UN** théoriques, soit −26,4 UN entre affichage théorique et débit réel simulé. Les réceptions de ce même article totalisent bien 420 000 000 UN. Le zéro initial était donc une erreur de rapprochement dans la preuve, pas une absence de consommation du moteur. Une quantité théorique fractionnaire n'est pas à elle seule la preuve d'une sortie de stock fractionnaire. Pour le planificateur, publier séparément besoin théorique, quantité réservée et quantité réellement consommée dans la simulation. Les autres articles n'ont pas été recalculés intégralement par cette contre-revue.

**Sommes d'unités différentes.** Additionner G, KG, M et UN n'a pas de sens physique sans conversion vers une grandeur commune. Une courbe de score normalisé peut agréger des composantes de différentes unités si son contrat le dit ; une courbe intitulée simplement « Quantité » ne le peut pas. Limiter le constat aux panneaux effectivement identifiés par l'audit numérique, sans l'étendre aux graphes qui séparent déjà les unités.

**Ce qui est utilisable et ce qui reste à qualifier**

Pour préparer une réunion industrielle, la carte reste un support d'exploration : repérer un fournisseur, lire un scénario, comparer les dates et ouvrir ses preuves. Pour ordonner un achat de secours, augmenter un stock ou justifier une économie, les trois distinctions suivantes doivent être visibles : simulé versus observé dans l'entreprise, prévu versus exécuté dans la simulation, association versus effet causal démontré.

Les preuves examinées ne certifient pas les hypothèses de demande, prix, capacités ou lois de risque. Une suite de tests verte établit des propriétés couvertes par ses assertions ; elle n'établit ni la pertinence des hypothèses industrielles, ni la validité de toutes les recommandations affichées. Les audits de conservation, tests navigateur et comparaisons appariées sont complémentaires.

La preuve finale de consommation a été relue après correction : elle porte bien 429 321 288 UN pour l'exemple contre-vérifié. `numeric_map.md` ne conserve pas le faux zéro provisoire et signale les corrections de son oracle. Il distingue également l'année 6 présente dans le payload de son absence dans les contrôles de sélection courants. Ces deux nuances évitent d'attribuer au produit des défauts que l'audit n'a pas démontrés. Les grands compteurs de rapprochement restent ceux du `numeric_summary.json` final : cette contre-revue n'a pas rejoué leur inventaire exhaustif.

Changements réalisés : ce rapport seulement. Contrôles exécutés : sonde d'invariance des unités, reconstruction du diagnostic de la fixture sans application, sommes directes de trois colonnes économiques des deux CSV, lecture des branches de report de coûts et de déclenchement des alertes. Aucun code applicatif corrigé.

Prochaine étape recommandée : traiter en priorité la valorisation de secours, la qualification des attributions au risque et les libellés de périmètre économique ; garder des tests négatifs montrant qu'une preuve absente ou une quantité seulement prévue ne devient pas une recommandation certaine.
