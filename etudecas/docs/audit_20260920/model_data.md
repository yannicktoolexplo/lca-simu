# Audit indépendant du modèle, des données et de la portée scientifique — 20 septembre 2026

Le registre physique courant est beaucoup plus solide que ne le laisseraient supposer les défauts de présentation : les quatre calculs passent de nouveau les 62 familles d'invariants CSV, et les consommations de nomenclature du nominal se rapprochent des quantités produites. **Cela ne valide pas encore le scénario comme reproduction des données industrielles.** Cet audit trouve notamment une demande client déplacée par le lissage MRP, une valorisation de stock dépendant arbitrairement de l'unité choisie pour d'autres articles, et une attribution d'impact client possible à un événement jamais appliqué.

Décision : **réviser avant toute conclusion économique ou causale industrielle**. Les résultats restent utilisables pour explorer les mécanismes et vérifier les bilans dans les conventions documentées. Aucun moteur, graphe source, résultat de simulation ni HTML livré n'a été modifié par cet audit.

## Périmètre et méthode

Référence calculée : `simulation/result/_reruns/corrected_map_20260918`, son compagnon `scenario_runs/state_dependent_full`, puis les actions finales `decision_support/actions/safety_150` et `expedite_50`. Les dossiers `actions_initial_review` sont historiques et exclus.

Le graphe d'entrée indiqué par chaque résumé et manifeste fait autorité pour reproduire son calcul. Le graphe brut `data/source/supply_graph_poc.json` est une étape antérieure : comparer aveuglément ses extrémités de flux au calcul préparé créerait des faux positifs, notamment pour le dépôt DC-1920 dont certains identifiants de liens contiennent encore DC-1910.

Trois nouvelles sondes, avec leurs fichiers de preuve :

- [audit_sources.py](../../artifacts/testing/full_audit_20260920/model/audit_sources.py) / [source-audit.json](../../artifacts/testing/full_audit_20260920/model/source-audit.json) : lecture indépendante des classeurs, bilan des mouvements, coûts de possession, demande, nomenclature et unités.
- [audit_constraints.py](../../artifacts/testing/full_audit_20260920/model/audit_constraints.py) / [constraints.json](../../artifacts/testing/full_audit_20260920/model/constraints.json) : tailles de lots, plafonds nominaux, plafonds hebdomadaires, conventions de coût de transport et quatre scénarios.
- [audit_risk_semantics.py](../../artifacts/testing/full_audit_20260920/model/audit_risk_semantics.py) / [risk-semantics.json](../../artifacts/testing/full_audit_20260920/model/risk-semantics.json) : datation des signaux de délai et contre-exemple d'attribution client.

Les oracles de quantités et de coûts lisent directement les fichiers, sans appeler le moteur ni le constructeur des courbes. Deux sondes appellent intentionnellement les fonctions de production afin de les contredire avec une propriété attendue : invariance d'un coût au changement d'unité d'un autre article ; impossibilité de prouver un impact physique d'un incident jamais appliqué. Ces deux sondes échouent à la propriété attendue et constituent des **défauts démontrés**, pas des tests de réussite.

Les preuves conservent les empreintes des fichiers examinés. L'audit n'a pas rejoué cinq ans de moteur ; il distingue donc la cohérence des sorties existantes de l'exécution de chaque branche du code actuel. La suite logicielle globale est pilotée par l'auditeur principal, sans doublon ici.

Le [manifeste de preuves](../../artifacts/testing/full_audit_20260920/model/evidence-manifest.json) fige 127 fichiers de données/résumés des quatre calculs, les quatre rapports d'invariants et les trois scripts nouveaux. Une empreinte atteste l'identité d'un fichier, pas la validation exhaustive de chacune de ses colonnes. Une contre-relecture indépendante a reproduit les défauts MD-01/02/03 et confirmé les nuances sur MD-04/08/09 ; voir [review.md](review.md).

## Ce qui passe effectivement

| Calcul | Familles CSV | Vérifications ponctuelles | Événements | Occurrences | Liens de généalogie |
|---|---:|---:|---:|---:|---:|
| Nominal | 62/62 | 935 045 | 58 816 | 14 803 | 33 220 |
| Risques | 62/62 | 948 983 | 60 194 | 15 751 | 33 266 |
| Sécurité ×1,5 | 62/62 | 956 006 | 60 905 | 15 954 | 33 516 |
| Expédition accélérée | 62/62 | 948 968 | 60 210 | 15 752 | 33 222 |

Ces nombres de vérifications ne sont pas des pourcentages de couverture du code. Les familles incluent notamment conservation de demande, UN entières, bilans fournisseurs, bilans d'occurrences, rapprochement stocks/registre et additions de coûts. Les quatre rapports `*-independent*.json` sont dans le [dossier de preuves](../../artifacts/testing/full_audit_20260920/model/). Deux premiers appels aux actions ont visé leur package `run/` au lieu de leur racine de calcul : leurs erreurs de fichier absent sont conservées, les reprises `*-final.json` passent.

Contrôles supplémentaires réussis :

- 28 lignes de stock source présentes dans le périmètre rapprochées du graphe, conversions G/KG comprises ; aucun écart supérieur à 10⁻⁵. Quatre lignes source hors périmètre sont listées explicitement.
- Les 25 délais de sécurité du classeur sont copiés numériquement dans les politiques du graphe ; leur **unité temporelle** pose cependant le problème MD-06 ci-dessous.
- Les 24 composants des trois nomenclatures sources correspondent aux ratios du graphe. 15 672 rapprochements consommation/production par campagne du nominal ne présentent aucun écart supérieur à 0,0002, après conversion G/KG et arrondi supérieur des besoins physiques UN. Les ordres de production déjà ouverts ne sont pas inclus dans cet oracle de campagnes nouvelles.
- 10 294 contrôles de quantités libérées, plafonds journaliers nominaux et nombre de démarrages par semaine sur les quatre calculs passent. Ils ne prouvent pas l'adéquation de la capacité à une vraie usine ni les plafonds dynamiques de chaque incident.
- Au nominal, 268091 est effectivement produit en 908 lots de 14 400 UN et 100 lots de 28 800 UN ; 268967 en 66 lots de 107 800 UN ; 773474 en 24 lots de 3 200 000 G. Le maximum admissible configuré de 268091 est 142 485 UN, avec multiple de 14 400 : 129 600 UN est le plus grand multiple admissible, mais n'est pas atteint dans ces sorties.
- La reconstruction du coût brut de possession à partir des soldes du registre et des tarifs du graphe donne 188 730 239,09869, contre 188 730 239,0979 dans le résumé : l'addition est cohérente aux arrondis près. La **base économique** est néanmoins défectueuse (MD-02).
- Les empreintes des quatre graphes lus correspondent au champ `input_sha256` de leurs résumés. La sécurité ×1,5 reste un calcul distinct : les stocks et cibles sources du nominal n'ont pas été remplacés par ceux de cette sensibilité.

## Constats prioritaires

### MD-01 — P1 : le lissage MRP modifie la demande client réalisée

**Fait vérifié.** L'option `--mrp-demand-signal-smoothing-days 7` est annoncée comme une fenêtre du signal MRP (`run_first_simulation.py:2747`). Elle alimente pourtant `demand_target_today` (`:10079`), puis `dval` lors du service client (`:11688`). La demande exécutée devient la moyenne des sept jours **à venir**, et non la quantité source répartie uniformément dans sa semaine.

Exemple sans aucune correction négative : pour 268091, la semaine 1 du classeur `demand_PF.xlsx`, feuille `Demande`, contient **13 300 UN** ; les sept premières demandes du CSV totalisent **22 908,142858 UN**, soit +72,24 %. La semaine 2 contient 35 719 UN dans la source et 42 508,428573 UN dans l'exécution. J1 vaut 2 357,530612 au lieu de 1 900 UN/j dans le profil source de cette semaine.

Sur 3 650 lignes client, **3 010 diffèrent** du profil hebdomadaire préparé, une fois correctement traitées les corrections négatives décrites ci-dessous. **Toutes les lignes** se rapprochent en revanche de la moyenne future sur sept jours reconstruite indépendamment. Les totaux annuels restent exactement préservés à l'arrondi près, ce qui explique pourquoi un contrôle uniquement annuel est vert.

La source 268967 contient quatre semaines négatives, totalisant −130 764 UN. Leur compensation sur les semaines suivantes est explicitement documentée par `rebalance_weekly_demand_rows` (`prepare_simulation_graph.py:523`) et conserve le total annuel de 1 575 986 UN. Ce traitement ne doit pas être confondu avec le lissage supplémentaire : notre oracle refait cette compensation avant de compter les 3 010 écarts.

**Conséquence.** Courbes de service, dates de pénurie, besoins usine et évaluation des actions portent sur une demande déplacée dans le temps. Dire qu'elles reproduisent directement les semaines observées est incorrect. Le profil préparé porte pourtant `daily_distribution=uniform_over_7_days`.

**Action proposée.** Séparer demande réalisée et prévision utilisée par le MRP. Un test de deux semaines très différentes doit prouver que changer le lissage MRP ne modifie ni les retraits clients ni leurs dates. Recalculer ensuite une variante corrigée, sans écraser l'actuelle. Si ce déplacement est intentionnel, le traiter comme scénario de demande transformée et l'afficher clairement.

### MD-02 — P1 : le repli de valorisation mélange des unités incompatibles

**Fait vérifié.** `prepare_simulation_graph.py:131–189` construit une médiane globale de valeurs déjà exprimées dans l'unité de chaque article, puis réemploie ce nombre pour tout article sans prix. Une valeur en €/KG, une autre en €/UN et une autre en €/M ne forment pas une distribution de prix homogène. Le nominal applique ainsi **3,895 par gramme** aux semi-finis 773474 et 693055, faute de prix explicite.

La sonde change uniquement la représentation d'un article connu de KG vers G ; le coût de possession d'un **autre article inconnu en UN** passe de 0,005479452 à 0,000005479452 par UN/j, soit un facteur **1 000**, alors qu'aucune réalité économique n'a changé.

Effet mesuré dans le calcul livré : **151 203 031,30** de coût brut de possession viennent de ce repli, soit **80,12 %** des 188 730 239,10 de possession et **52,23 %** du coût total de 289 514 141,10. Le seul stock 773474 à M-1430 en représente 119 264 042,31. Ce sont des contributions calculées, pas une estimation du « vrai surcoût » industriel ; le prix correct n'est pas connu.

**Action proposée.** Refuser une valorisation financière complète quand un prix dimensionné manque ; publier séparément part valorisée, part inconnue et scénarios de prix. Pour les semi-finis internes, définir un coût de revient ou prix de transfert traçable, avec unité et devise. Ajouter ce test d'invariance à la préparation et au contrat des résultats économiques.

### MD-03 — P1 : une simple coïncidence de backlog devient une cause et une action prioritaire

**Fait démontré par contre-exemple.** `supplier_risk_panels.py:3194–3240` sélectionne le backlog d'un produit aval dans une fenêtre suivant l'événement ; il n'exige ni application physique de l'événement ni lien causal au service concerné. La fenêtre est de 45 à 56 jours selon la famille (`:3147–3149`).

La [fixture et son résultat](../../artifacts/testing/full_audit_20260920/model/causality-counterexample-payload.json) contiennent un incident `CONFIGURED_BUT_NEVER_APPLIED`, **zéro application locale**, **zéro retard de production**, puis un backlog de 10 UN à J10. Le constructeur réel retourne simultanément :

- `local_application.applied=false` ;
- `stage=service_client`, `absorption_label=Client atteint` ;
- `root_cause_label` désignant la capacité du fournisseur ;
- une action de priorité `high` pour protéger le service client.

La même logique agrège les observations dans des chemins causaux et des mises en évidence du réseau. Des fournisseurs différents peuvent donc se voir attribuer le même maximum de backlog. L'allocation des coûts d'événements partage également un coût journalier global entre lignes de signaux (`:3122`), et ne mesure pas le coût marginal propre à chaque cause.

**Action proposée.** Présenter ces liens comme associations temporelles potentielles tant qu'aucune preuve de propagation n'existe. Exiger au minimum un effet appliqué et une chaîne de quantités/dates pour « propagation observée » ; réserver « effet propre » à une comparaison contrefactuelle adaptée. Un incident non appliqué ne doit jamais recevoir une recommandation causale prioritaire sur la seule présence d'un backlog aval.

### MD-04 — P1 : des délais futurs servent de délais « observés » au déclenchement de risques

Le moteur tire le délai lors de la décision d'expédition, puis le place immédiatement dans `supplier_state_lead_observations_today_by_pair` (`run_first_simulation.py:13121`). Les règles de risque le lisent ensuite comme observation réalisée (`:13780`).

Dans le scénario livré, 291 des 680 événements endogènes sont de famille `lead`. Pour **287**, un rapprochement direct trouve des expéditions décidées le jour du déclenchement dont la première réception est encore future. Exemple : 338929, alerte à J43 sur **60/42 = 1,428571** ; SHIP-00000170 n'arrive qu'à **J103**. Les quatre autres ne sont pas validés par ce rapprochement direct ; ils ne sont pas considérés comme corrects par défaut.

Un délai annoncé par le fournisseur à la commande peut être un signal métier légitime. Le modèle ne distingue toutefois pas cette annonce de la réalisation future tirée aléatoirement, tout en parlant de délai « observé ». Il serait donc excessif d'en conclure que toute utilisation d'un délai futur est interdite ; **ce qui manque est le contrat d'information disponible au décideur**.

**Action proposée.** Conserver distinctement délai promis/ETA, délai réalisé, date d'observation et date de décision. Une règle fondée sur les réalisations ne doit apprendre un délai qu'à réception ; une règle fondée sur une annonce doit le dire et disposer d'un modèle d'erreur d'annonce. Tester explicitement l'absence d'accès aux réalisations futures dans le mode de contrôle causal.

### MD-05 — P1 : « par unité » devient « par lot d'achat » pour les coûts de transport

Le graphe indique `transport_cost.per=unit`. `lane_records` reprend le nombre en `unit_transport_cost` (`run_first_simulation.py:2969`), puis `lane_transport_cost_for_chunk` le multiplie par le nombre de lots d'achat dès qu'il s'agit d'un composant disposant d'une quantité standard (`:8981–8998`). La dimension tarifaire du graphe n'est pas utilisée pour choisir la formule.

Exemple SHIP-00000134 : 5 000 UN de 338929, tarif configuré 0,3614 par unité, multiplicateur économique 0,2. Coût exporté : **0,07228**, correspondant à un lot. Avec le libellé « par unité », le calcul arithmétique serait 361,40. **Ce dernier nombre n'est pas un tarif industriel validé** : il démontre la contradiction du contrat.

6 275 lignes nominales présentent ce changement de base ; leurs coûts exportés totalisent 502,47. Les frais PF utilisent une autre base. Le dimensionnement des camions et les groupes hebdomadaires affichés ne recalculent pas ces tarifs.

**Action proposée.** Formaliser des unités tarifaires distinctes — expédition, camion, palette, kg, pièce, kilomètre — et refuser les combinaisons ambiguës. Une commande, un lot de fabrication et une charge de camion ne définissent pas la même unité de facturation.

### MD-06 — P1 métier : les jours ouvrés sources deviennent des jours moteur

Les 25 politiques du classeur `Extract_Données_Complémentaires.xlsx` portent le titre **« Délai de sécurité (en jours ouvrés) »**. L'injecteur lit ce champ puis transmet directement le nombre dans `safety_time_days` (`inject_mrp_seed_data_v2.py:471–510`). Le moteur multiplie un besoin journalier simulé sur sept jours par ce nombre (`run_first_simulation.py:12164`), et ajoute des jours entiers aux dates (`:9509`). Aucun calendrier de jours ouvrés n'intervient dans ce chemin.

La copie numérique exacte des 25 valeurs ne prouve donc pas le respect de leur sens métier. À titre d'illustration seulement, 20 jours ouvrés peuvent représenter quatre semaines avec un calendrier lundi-vendredi ; aucun facteur universel ne remplace un calendrier réel et ses jours fériés.

Le coefficient supplémentaire **0,75** est toujours appliqué au dépôt : 20 jours pour 268091 deviennent 15 jours dans la cible souple ; 25 jours pour 268967 deviennent 18,75. Les 23 couples composants d'usine disposent bien d'une surcharge à 1. Ce coefficient n'est pas une modification récente de donnée source et sa décision métier reste ouverte.

**Action proposée.** Faire confirmer le calendrier et le sens exact du délai de sécurité avant de modifier le moteur ; conserver champ source, unité source, règle de conversion et cible effective. Résoudre séparément le coefficient dépôt.

### MD-07 — P2 : besoins composants statiques très supérieurs à la consommation observée

Les 23 couples composants des deux usines sont explicitement forcés en `mrp_static_requirement_pairs`, malgré l'activation générale MRP/BOM/MPS. Le besoin statique est calculé depuis **capacité nominale × nomenclature** (`run_first_simulation.py:8430–8452`) et prime sur le signal propagé (`:12123`).

Pour 042342, le MRP utilise **9 292 668 UN/j** ; la consommation physique moyenne nominale est **235 244,54137 UN/j**, ratio **39,50**. Le délai source de 5 jours produit ainsi une cible de **46 463 340 UN**. Les composants de M-1810 présentent typiquement un ratio **23,28** entre signal et consommation moyenne.

C'est une convention explicitement configurée, donc pas une faute d'addition ni la preuve qu'il faut remplacer toutes les cibles. Elle influence fortement stocks, coûts, alertes et dimensionnement fournisseurs. Une carte de « besoin MRP » doit dire si le besoin vient d'un programme, d'une prévision ou d'un débit maximal théorique.

**Action proposée.** Exposer cette base dans la fiche article et comparer, sur cas séparés, besoin issu du PDP versus besoin de capacité. Ne pas présenter le niveau calculé comme quantité directement observée dans l'ERP.

### MD-08 — P2 : départs futurs exportés comme expédiés/en transit

Les événements physiques du nominal s'arrêtent bien à **J1824**. Le fichier `production_supplier_shipments_daily.csv` contient toutefois **167 départs futurs**, jusqu'à **J1947** : **870 000 UN et 50 000 G**. Les ordres associés sont marqués `released_in_transit` car le statut dépend de l'arrivée, sans tester que le départ a eu lieu (`run_first_simulation.py:9522`).

Exemple SHIP-00010064 : réservation J1820, départ J1947, arrivée J2039. Le registre ne contient que la réservation ; il serait faux de dire qu'il est physiquement parti à J1824.

**Nuance importante.** Le moteur reporte les coûts et quantités journaliers au jour du départ grâce à `scheduled_lane_release_metrics` (`:13373–13394`, `:11744`). Cet audit **ne démontre pas une surfacturation du résumé** par les 167 lignes futures. Le défaut concerne les statuts, le contrat d'export et tout consommateur qui assimile l'ensemble du CSV à des mouvements exécutés ou en déduit un horizon étendu.

**Action proposée.** Séparer réservé, départ planifié, parti, reçu ; inclure date de décision et date d'observation. Les séries de réalisation doivent être bornées au manifeste, pas au maximum d'un carnet futur.

### MD-09 — P2 métier : stock disponible et stock physiquement réservé sont confondus dans la valorisation

Les réservations débitent le stock dès la décision, avant certains départs physiques. Le suivi récent sait isoler les réservations, mais le calcul de possession somme seulement `stock` (`run_first_simulation.py:14199–14212`). Le stock réservé dans l'attente du camion ne porte alors plus de coût de stockage dans cette convention.

Si ces quantités restent physiquement au site jusqu'au départ, leur valorisation au même tarif ajouterait **489 962,12** de coût brut sur le nominal. Ce nombre est un scénario comptable conditionnel, **pas une correction à appliquer sans confirmation** : propriété, transfert de responsabilité et base de stockage doivent être définis. À la clôture, le registre distingue bien les 870 000 UN et 50 000 G réservés du transit réel.

### MD-10 — P2 : périmètre initial et informations économiques partiellement hypothétiques

Le graphe exclut quatre lignes de stock du classeur hors nomenclature/périmètre : M-1430/001848, M-1430/007923, SDC-1450/001893 et SDC-1450/002612. Un ordre ouvert de 7 000 KG de 001848 à M-1430 est néanmoins injecté dans le registre, alors que ce couple est absent des états d'inventaire du graphe et n'a pas de coût de possession associé. Une règle unique de périmètre stock initial/ordres ouverts est nécessaire.

L'initialisation inclut également **107 800 UN de EX-344135**, ancienne référence de packaging issue d'une hypothèse de transition explicitement conservée dans `reference_transition_stocks`. Dire que tous les stocks de J0 sont exclusivement des observations du classeur est donc trop fort.

Les 33 capacités fournisseurs sont toutes multipliées par **320** dans le scénario courant ; leurs bases sont 19 besoins aval, 9 besoins aval avec indice FIA, 4 replis depuis stock initial et 1 capacité explicite avec indice FIA. Ce sont majoritairement des paramètres inférés/calibrés, pas 33 capacités industrielles mesurées.

Quatre liens 021081 conservent des prix en **USD** alors que le graphe annonce l'euro. Aucun passage de change n'est visible dans les formules de valorisation inspectées. Ces quatre liens n'ont pas de lignes d'expédition exécutées dans le nominal ; ne pas leur attribuer un coût d'achat erroné effectivement mesuré sans preuve. Leur usage comme références de prix/valorisation reste à dimensionner en devise.

### MD-11 — P2 métier : un délai procédé de trois jours n'impose pas une attente physique

Les trois procédés portent `tau_process=3`. Les **1 098 libérations** nouvelles du nominal ont lieu le jour du démarrage du lot. Les traces l'indiquent honnêtement : `execution_complete_tau_planning_only`, `tau_process_used_for_planning_cover_only`. Le paramètre sert à la couverture de planification ; il n'est pas une durée minimale de fabrication ni de libération qualité.

Ce n'est pas une nouvelle incohérence du registre. C'est une hypothèse de modèle majeure pour prévoir la propagation d'un incident au lot, la capacité, le WIP et la date de disponibilité. Une fiche intitulée « délai de production 3 jours » doit préciser cette convention, ou le moteur doit être étendu après décision métier.

## Portée des résultats de recherche

Les valeurs actuelles sont des trajectoires de simulation, pas une estimation statistique robuste de la performance industrielle :

| Aspect | État vérifié | Limite pour une conclusion |
|---|---|---|
| Demande | 104 semaines article-source, 2 produits ; volumes annuels conservés et répétés 5 fois | Ce ne sont pas cinq années indépendantes ; lissage temporel MD-01 ; aucune erreur prévisionnelle dans la source (`forecast_demand == real demand` sur 104 lignes) |
| Aléa | Graine 42, délais Erlang activés, `common_random_numbers=false` sur les quatre calculs | Même graine ne garantit pas mêmes réalisations si le nombre/ordre des tirages change ; une trajectoire par action ne donne ni intervalle d'incertitude ni stabilité de classement |
| Risque | 355 événements configurés et 680 déclenchements endogènes dans le compagnon | Portefeuille construit/scénarisé ; certains événements mentionnent explicitement l'absence de cas de sensibilité locale disponible ; fréquence/amplitude ne sont pas estimées ici depuis des incidents industriels |
| Coûts | Additions cohérentes ; tarification fixe par procédé, décomposition 35/45/20 de possession | Paramètres calibrés et conventions MD-02/05/09/10 ; ne pas interpréter l'écart comme économie en euros validée |
| Production | Tailles de lots et plafonds nominaux contrôlés | Durées qualité, calendriers, capacité partagée entre produits et calibration non qualifiés par ces tests |
| Service | Conservation demande/service/reliquat vérifiée | Service cumulé n'est pas OTIF ; un retard rattrapé peut laisser un service final proche de 100 % |
| Traçabilité | Identités et quantités exécutées bien conservées | Mélanges bornés et exposition potentielle ne prouvent pas l'effet marginal d'un incident sur un client |

À paramètres actuels, le résumé nominal donne 25 762 139 UN servies et 0,9999 UN de reliquat prévisionnel ; le compagnon risques donne 25 667 344 UN servies et 94 795,9999 de reliquat. Ces bilans sont arithmétiquement cohérents. Leur validité industrielle dépend des conventions précédentes.

Pour soutenir une étude : figer une version du modèle et ses données, tracer chaque transformation source, qualifier les unités et calendriers, définir les sorties de validation hors calibration, puis comparer plusieurs graines avec intervalles de différence et appariement adapté. Une étude d'effets propres devra isoler les facteurs et interactions ; le portefeuille complet peut servir de stress test, mais son backlog ne doit pas être attribué à chaque risque actif par fenêtre temporelle.

Les prototypes historiques, campagnes Monte Carlo et validations V2–V8 ne sont pas requalifiés par ce travail. Leur présence, leurs signatures historiques ou des tests verts ne transfèrent pas automatiquement une validation scientifique au moteur et à la carte courants.

## Vérification durable à ajouter après décision de correction

1. **Données vers simulation** : contrat de calendrier et unité, conservation des volumes par semaine, source/transformé séparés, cohérence de périmètre entre stock initial et ordres ouverts.
2. **Invariances économiques** : changement G/KG sans changement de valeur totale ; aucun tarif €/pièce traité €/lot ; devises explicites ; prix manquant visible.
3. **Causalité** : incident jamais appliqué ⇒ aucun impact affirmé ; changement d'un backlog sans lien ⇒ aucune nouvelle cause fournisseur ; séparation ETA/réalisé et absence d'accès au futur selon le mode choisi.
4. **États logistiques** : réservation future ≠ départ exécuté ; horizon des réalisations borné ; stock disponible, réservé, en transit et propriété comptable séparés.
5. **Qualification de chaque courbe** : reproduire les points depuis les CSV par un calcul indépendant, puis vérifier le libellé, l'unité, l'horizon et le domaine métier dans le navigateur. Un bon rapprochement du CSV vers la courbe ne corrige pas une mauvaise transformation Excel vers CSV.

## Limites explicites de cet audit

La lecture porte sur les mécanismes actifs et leurs sources pertinentes ; elle ne certifie pas chaque branche des prototypes ni toutes les feuilles sans rôle dans le calcul livré. Les règles physiques d'incidents ciblés, la quarantaine, la péremption, les retours et les unités logistiques réelles restent à définir/qualifier. Les 62 familles CSV ne constituent ni une preuve de calibration ni une preuve de causalité. Les contre-exemples démontrent les défauts signalés, sans prédire le résultat corrigé avant recalcul.

Changements réalisés : ce rapport et preuves/scripts confinés au dossier d'audit. Tests exécutés : quatre audits CSV, rapprochements sources/nomenclature, contraintes des quatre calculs, deux contre-exemples sémantiques. Risques/limites : conventions métier et recherche ci-dessus, données industrielles non inventées. Prochaine étape recommandée : corriger d'abord MD-01 à MD-05 dans des variantes vérifiables, clarifier MD-06/07/09/11 avec le métier, puis recalculer et comparer à la référence conservée.
