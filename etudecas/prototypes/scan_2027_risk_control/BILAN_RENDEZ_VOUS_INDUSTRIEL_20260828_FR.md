# Bilan pour le rendez-vous industriel

Date de mise à jour : 29 août 2026  
Périmètre : `etudecas` uniquement  
Objet : démontrer comment un incident fournisseur ou qualité se propage dans la chaîne, quels lots et clients sont exposés, et quelles réponses réduisent le retard au meilleur compromis de coût.

## Conclusion en une minute

Le démonstrateur demandé est maintenant disponible. Il réunit dans une nouvelle page, utilisable sans connexion Internet :

- deux incidents industriels suivis de l'amont jusqu'aux clients ;
- une référence normale, l'incident sans action et sept réponses possibles ;
- dix répétitions par cas pour montrer que le résultat varie selon l'état de la chaîne ;
- les courbes quotidiennes de stocks, flux, production et retards clients ;
- une traçabilité détaillée des matières et des lots sur une répétition de référence ;
- les jours récupérés, le coût simulé supplémentaire et le retard qui subsiste.

Le résultat le plus directement exploitable est le suivant :

- pour la retenue qualité simulée, le plan combiné réduit le plus fortement le retard client cumulé, mais coûte beaucoup plus cher ; le transport accéléré offre ici un compromis plus économique ;
- pour le retard du composant 338929, le transport accéléré supprime le retard client dans les deux répétitions touchées et coûte moins cher que le plan combiné ;
- certaines actions intuitives ne servent à rien dans ces cas, et la replanification testée sur 338929 aggrave même le retard. C'est précisément l'intérêt d'une simulation : tester avant d'engager une décision réelle.

Ce travail est présentable comme un démonstrateur avancé d'aide à la décision. Il ne faut pas encore le présenter comme un optimiseur autonome validé pour une entreprise : les coûts ne sont pas des euros, les règles qualité restent simplifiées et les réponses sont programmées à l'avance.

## Où voir le résultat

### Page principale du rendez-vous

[Ouvrir la démonstration industrielle hors ligne](C:/dev/lca-simu-pr40-validation-artifacts-20260726/industrial_demo_offline_20260828_v6/index.html)

Cette page est le point d'entrée recommandé. Elle raconte une chaîne simple :

> voici l'incident → voici les matières, lots et clients exposés → voici les solutions testées → voici les jours récupérés, le coût et le risque restant.

Elle est nouvelle et ne remplace aucune carte ni aucun tableau de bord existant. Les anciens résultats, le démarrage initial et les autres onglets ont été conservés.

### Résultats complets derrière la page

- [Série finale des 180 simulations](C:/dev/lca-simu-pr40-validation-artifacts-20260726/industrial_cascade_campaign_10seeds_20260828_v1)
- [Tableaux de comparaison des solutions](C:/dev/lca-simu-pr40-validation-artifacts-20260726/industrial_cascade_comparison_10seeds_20260828_v1)
- [Courbes quotidiennes complètes](C:/dev/lca-simu-pr40-validation-artifacts-20260726/industrial_cascade_trajectories_10seeds_20260828_v1)
- [Traçabilité détaillée de la retenue qualité, répétition 330281](C:/dev/lca-simu-pr40-validation-artifacts-20260726/industrial_registry_quality_seed330281_20260828_v2_units)
- [Traçabilité détaillée du retard 338929, répétition 330281](C:/dev/lca-simu-pr40-validation-artifacts-20260726/industrial_registry_delay_seed330281_20260828_v2_units)

Le paquet principal contient ses bibliothèques graphiques et ses données. Il peut donc être copié sur l'ordinateur du rendez-vous et ouvert localement.

## Ce qui a été sécurisé dans le modèle physique

Les mots suivants ont maintenant un sens distinct. Cette séparation évite de présenter une sortie journalière incomplète comme un lot fini disponible.

| Notion | Sens dans le modèle |
|---|---|
| Campagne de fabrication | Besoin global de fabrication qui peut s'étendre sur plusieurs jours. C'est un objet de planification, pas nécessairement un lot physique unique. |
| Lot physique ou batch | Quantité réellement engagée dans une exécution de fabrication selon les règles de taille de lot. |
| Encours | Lot physique commencé : des composants ont pu être consommés, mais le produit fini n'est pas encore disponible. |
| Lot libéré | Produit fini rendu disponible uniquement lorsque le lot physique est terminé. Il peut alors entrer en stock, être consommé à l'étape suivante ou être expédié. |
| Jour 0 | Premier jour mesuré et comparé. La préparation antérieure est reprise avec ses stocks, transports en cours, encours et commandes en retard. |

Le passage au jour 0 a été corrigé pour que les campagnes et encours commencés avant la période ne disparaissent pas et ne soient pas artificiellement clôturés à leur première sortie. Pour une même répétition, le fonctionnement normal, l'incident sans action et les sept solutions repartent du même état au jour 0. La différence observée après ce point vient donc de l'incident et de la réponse testée, et non d'un démarrage différent.

Ces changements ont été ajoutés sans écraser le comportement historique : les anciens résultats restent accessibles et les nouveaux réglages de préparation sont neutres lorsqu'ils ne sont pas demandés.

## Ce qui a été simulé

Deux chaînes ont été retenues :

1. une retenue qualité simulée sur le composant 021081, qui traverse SDC-1450, le semi-fini 773474, M-1430, le produit 268967 puis les clients ;
2. un retard du composant 338929 vers l'usine M-1810, puis le produit 268091, le centre DC-1920 et les clients.

Pour chaque chaîne, neuf situations ont été calculées :

1. fonctionnement normal ;
2. incident sans action ;
3. transport accéléré ;
4. recours à un second fournisseur, réel dans la première chaîne et représenté par une approximation dans la seconde ;
5. achat exceptionnel ;
6. stock ciblé ;
7. priorité fournisseur ;
8. replanification ;
9. plan combinant plusieurs leviers.

Chaque situation a été répétée dix fois avec les mêmes dix variantes aléatoires. Cela représente 2 chaînes × 9 situations × 10 répétitions, soit 180 simulations comparables.

Le modèle est dynamique et dépend de son état : chaque jour, les stocks, transports en cours, composants disponibles, fabrications, lots libérés et retards modifient la suite de la simulation. En revanche, les actions de cette démonstration sont déclenchées selon un calendrier fixé à l'avance. Il s'agit donc de plans en boucle ouverte, pas encore d'une commande en boucle fermée qui déciderait en fonction d'une alerte observée pendant l'exécution.

## Comment lire les chiffres

### La charge cumulée de retard client

L'unité `UN·jours` additionne la quantité en retard et sa durée. Par exemple, 100 unités en retard pendant 5 jours représentent 500 UN·jours. Cette mesure permet de distinguer un petit retard bref d'un volume important bloqué longtemps.

Ce n'est ni un nombre de commandes, ni un délai moyen de livraison.

### Les jours récupérés

Les jours récupérés comparent la date à laquelle le système revient durablement à zéro retard additionnel. La moyenne est calculée seulement sur les répétitions où l'incident sans action atteint effectivement le client. Ce n'est pas une promesse de réduction du délai de chaque commande.

### Le coût

Le coût affiché est la différence moyenne entre une solution et l'incident sans action. Il est exprimé dans les unités monétaires du modèle. Il ne s'agit pas d'euros validés, et il n'intègre pas encore correctement tous les coûts de non-service, pertes de vente, pénalités, marges, qualification fournisseur ou rebut qualité.

### Client en retard et matière exposée ne veulent pas dire la même chose

Deux lectures sont volontairement séparées :

- **retard client causé par l'incident** : la simulation avec incident accumule plus de demande en retard que la référence sans incident ;
- **ascendance exposée** : une matière touchée par l'incident apparaît dans la généalogie d'un produit servi à un client.

Un client peut recevoir un produit possédant une ascendance exposée sans subir de retard, parce qu'un stock, un autre lot ou une marge de capacité a absorbé la perturbation. Les tableaux de performance utilisent la première définition ; le registre de lots utilise la seconde.

## Résultat 1 — retenue qualité simulée sur une chaîne à plusieurs niveaux

### Incident représenté

Le modèle retarde de 90 jours la mise à disposition de nouvelles expéditions du composant 021081 sur les flux concernés. La propagation physique est :

> 021081 retenu → disponibilité réduite à SDC-1450 → production de 773474 perturbée → alimentation de M-1430 perturbée → production de 268967 décalée → commandes clients en retard.

La référence sans incident ne présente aucun retard client sur les dix répétitions, même si son état initial reste volontairement tendu. Avec l'incident sans action :

- 9 répétitions sur 10 produisent un retard client supplémentaire ;
- 1 répétition absorbe entièrement l'incident avant le client ;
- la charge cumulée moyenne est de **6 932 942 UN·jours**, zéro compris pour le cas absorbé ;
- le cas le plus défavorable atteint **20 940 590 UN·jours**.

Cette dispersion est un résultat métier important : le même incident n'a pas toujours la même conséquence. Son effet dépend des stocks, transports, encours et fabrications déjà présents quand il survient.

### Solutions comparées

| Réponse testée | Retard restant moyen | Jours récupérés | Surcoût moyen du modèle | Lecture métier |
|---|---:|---:|---:|---|
| Incident sans action | 6 932 942 UN·jours | Référence | Référence | L'incident atteint le client dans 9 cas sur 10. |
| Plan combiné | **2 392 036 UN·jours** | **129,0 jours** | **+4 880 627** | Meilleure réduction globale parmi les réponses testées, mais le retard n'est pas supprimé et le coût est élevé. |
| Transport accéléré | **4 193 975 UN·jours** | **94,1 jours** | **+402 352** | Réduction moins forte que le plan combiné, mais avec un surcoût simulé très inférieur. C'est le compromis le plus intéressant à discuter. |
| Achat exceptionnel | 6 116 484 UN·jours | 77,2 jours | +6 442 011 | Effet limité sur la charge cumulée pour un coût très élevé dans cette représentation. |
| Replanification | 6 932 942 UN·jours | 0 jour | 0 | Aucun effet client mesurable dans ce cas. |
| Second fournisseur | 6 932 942 UN·jours | 0 jour | 0 | Le changement d'allocation testé ne modifie pas le résultat client dans ce cas précis. |
| Priorité fournisseur | 6 932 942 UN·jours | 0 jour | 0 | Aucun effet client mesurable dans cette configuration. |
| Stock ciblé | 6 932 942 UN·jours | 0 jour | 0 | Le réglage testé ne protège pas davantage le client dans cette configuration. |

Les jours récupérés sont moyennés sur les neuf répétitions où le client est touché. Les retards et les coûts sont moyennés sur les dix répétitions, y compris le cas où les stocks absorbent l'incident.

### Conseil métier à présenter

La simulation ne dit pas que le transport accéléré sera toujours préférable. Elle montre qu'ici, ajouter plusieurs leviers réduit davantage le retard, mais que le gain supplémentaire coûte très cher. La bonne question à poser à l'industriel est donc : combien vaut un jour de reprise et combien coûte réellement une unité client en retard ? Avec leurs euros, pénalités et marges, ce compromis devient une décision économique.

## Résultat 2 — retard du composant 338929 vers M-1810 et le produit 268091

### Incident représenté

Les nouvelles expéditions de 338929 concernées reçoivent 35 jours de délai supplémentaire pendant les 90 premiers jours mesurés. La propagation physique est :

> 338929 retardé → disponibilité réduite à M-1810 → fabrication de 268091 contrainte → stock de DC-1920 réduit → demande client potentiellement en retard.

La référence sans incident ne présente aucun retard client sur les dix répétitions, même si son état initial reste volontairement tendu. Avec l'incident sans action :

- l'incident est physiquement appliqué dans les dix répétitions ;
- il crée un retard client dans **2 répétitions sur 10** ;
- dans les huit autres, les stocks et flux existants l'absorbent avant le client ;
- la charge cumulée moyenne sur les dix répétitions est de **65 423 UN·jours** ;
- le cas le plus défavorable atteint **345 419 UN·jours**.

Le faible nombre de cas touchés ne signifie pas que l'incident est absent. Il montre que la chaîne possède souvent assez de protection dans cette configuration, mais pas toujours.

### Solutions comparées

| Réponse testée | Retard restant moyen | Jours récupérés | Surcoût moyen du modèle | Lecture métier |
|---|---:|---:|---:|---|
| Incident sans action | 65 423 UN·jours | Référence | Référence | Deux répétitions atteignent le client ; huit sont absorbées. |
| Transport accéléré | **0 UN·jour** | **16,0 jours** | **+33 532** | Supprime le retard additionnel dans les deux cas touchés. |
| Plan combiné | **0 UN·jour** | **16,0 jours** | **+70 698** | Même résultat client que le transport accéléré, pour un coût simulé plus élevé. |
| Achat exceptionnel | 65 423 UN·jours | 0 jour | +368 | Aucun bénéfice client dans cette représentation. |
| Second fournisseur représenté par approximation | 65 423 UN·jours | 0 jour | +433 | Aucun bénéfice observé ; ce cas n'est pas un vrai fournisseur supplémentaire dans le réseau. |
| Priorité fournisseur | 65 423 UN·jours | 0 jour | 0 | Action non exécutée : 338929 n'a qu'une voie fournisseur, donc aucune voie concurrente à favoriser. |
| Stock ciblé | 65 423 UN·jours | 0 jour | +46 919 | Action seulement partiellement exécutée selon les contrôles ; aucun bénéfice client démontré. Elle est exclue du classement. |
| Replanification | **282 512 UN·jours** | **−11,5 jours** | +2 742 | Aggrave le résultat : le retard cumulé moyen sur les dix répétitions représente **4,32 fois** celui de l'incident sans action. |

Les jours récupérés sont moyennés sur les deux répétitions touchées. Les retards et les coûts sont moyennés sur les dix répétitions.

### Conseil métier à présenter

Dans ce scénario, le transport accéléré domine le plan combiné : il obtient le même résultat client pour environ la moitié du surcoût simulé. La replanification ne doit pas être recommandée sous cette forme. Elle démontre qu'augmenter ou déplacer un objectif de production sans résoudre la contrainte physique peut détériorer le service.

L'absence de bénéfice de l'achat exceptionnel ou du second fournisseur approximé ne prouve pas que ces solutions seraient inutiles dans la réalité. Elle indique que leurs représentations actuelles ne créent pas le bon flux physique vers M-1810. Il faut les reconstruire avec les véritables fournisseurs, délais de qualification, capacités, prix et liaisons logistiques de l'industriel.

## Ce que la traçabilité prouve, et ce qu'elle ne prouve pas encore

L'identifiant de l'incident est maintenant porté directement par les expéditions fournisseur touchées et leurs réceptions. À partir de ces réceptions, le moteur suit les consommations, fabrications, lots finis, expéditions aval et services clients par la généalogie physique.

Sur la répétition détaillée 330281 :

- la retenue qualité suit **120 000 kg** de matière ; la quantité est entièrement retrouvée entre la source et la réception ;
- le retard 338929 suit **1 985 000 unités** ; la quantité est également entièrement retrouvée entre la source et la réception ;
- les unités sont conservées à chaque étape : les kilogrammes et les unités ne sont jamais additionnés comme s'ils étaient comparables.

Après la réception, certaines fabrications mélangent plusieurs lots parents ou les fractionnent. Le registre suit alors la généalogie et fournit des bornes d'exposition lorsque l'attribution exacte n'est pas identifiable. Il ne faut donc pas affirmer qu'une quantité exacte d'un lot source précis se trouve dans une commande client précise lorsqu'un mélange l'empêche.

Le registre rattache aussi les coûts observés aux flux de matière exposés. Le surcoût total d'une solution est calculé séparément par la comparaison avec l'incident sans action. Cette séparation évite de confondre « coût porté par un flux exposé » et « coût supplémentaire causé ou évité par une décision ».

La traçabilité détaillée n'a été produite que pour la répétition 330281 de chaque incident. Les dix répétitions disposent des résultats de performance et des courbes, mais pas du même registre détaillé de chaque lot. Cette distinction doit rester visible pendant le rendez-vous.

## Limites à dire clairement

### La retenue qualité n'est pas encore une vraie quarantaine

Le premier incident est une **retenue avant mise à disposition** : les expéditions nouvelles sont retardées de 90 jours puis entièrement libérées. Le modèle ne représente pas encore un statut local « en quarantaine », un plan d'inspection, l'acceptation ou le rejet, le rebut, la retouche, le rappel ou une libération partielle par décision qualité. Il faut employer « retenue qualité simulée », pas « quarantaine industrielle complète ».

### Certaines solutions sont des approximations

- sur 338929, il n'existe qu'une voie fournisseur dans le réseau ; le « second fournisseur » augmente une alimentation amont existante mais ne crée pas une nouvelle voie qualifiée vers M-1810 ;
- l'achat exceptionnel augmente également une alimentation amont du modèle ; ce n'est pas encore un achat spot livré directement à l'usine ;
- la priorité testée est une priorité entre voies fournisseur, pas une priorité de commande client, de campagne ou de lot ; elle ne peut pas agir sur 338929 qui est mono-source ;
- le stock ciblé sur 338929 n'a été que partiellement exécuté dans la plupart des répétitions et ne doit pas être classé parmi les solutions validées ;
- la replanification modifie des objectifs quotidiens MRP et de production ; elle ne séquence pas les campagnes avec un véritable solveur APS à capacité finie ;
- le transport accéléré raccourcit le délai des nouvelles expéditions et ajoute une prime ; il ne choisit ni transporteur ni mode et ne rattrape pas une matière déjà en transit.

### Les chiffres décrivent le démonstrateur, pas une entreprise réelle

- les coûts sont des unités du modèle, pas des euros ;
- dix répétitions montrent une moyenne, une dispersion et un cas défavorable dans les hypothèses choisies ; elles ne fournissent pas une probabilité industrielle d'incident ou de perte ;
- les stocks initiaux et flux en cours ont été réglés pour obtenir une référence normale propre et isoler l'incident ; ils ne prétendent pas reproduire un bilan ERP réel ;
- les actions sont programmées à l'avance, donc en boucle ouverte ;
- les règles d'incident sont imposées au modèle ; elles ne prédisent pas automatiquement l'arrivée d'un incident réel ;
- la généalogie détaillée est disponible sur une répétition par cascade et utilise des bornes lorsque les lots sont mélangés.

Ces réserves ne diminuent pas l'intérêt du démonstrateur. Elles définissent précisément le travail de calibration et de validation à réaliser avec un industriel.

## Ce que nous pouvons proposer dès maintenant

Le démonstrateur permet de proposer une démarche en quatre étapes :

1. **Cartographier les dépendances critiques** : fournisseurs, composants, nomenclatures, sites, capacités, lots, clients et voies logistiques.
2. **Reproduire un incident historique** : état initial, chronologie, décisions prises, lots touchés, délais de reprise et coûts observés.
3. **Tester les réponses avant de les engager** : transport accéléré, achat exceptionnel, second fournisseur, stock ciblé, priorité et replanification.
4. **Construire un pilotage quotidien contrôlé** : observer la situation, déclencher une réponse seulement si nécessaire, simuler son effet et faire valider la décision par les équipes.

La valeur métier n'est pas seulement de montrer qu'un incident crée un retard. Elle est de déterminer :

- quand les stocks suffisent et qu'une action coûteuse est inutile ;
- quels lots, produits et clients nécessitent une protection ;
- quelle action réduit réellement le retard ;
- quelle action ne change rien ou aggrave la situation ;
- combien coûte chaque jour ou chaque unité de service récupérée.

## Prochaine étape avec les données de l'industriel

### 1. Calibrer le réseau réel

Demander les données ERP, MES, WMS et transport nécessaires :

- stocks, commandes d'achat, commandes clients et transports en cours au jour de départ ;
- nomenclatures, substitutions, rendements et versions de recettes ;
- fournisseurs, capacités, prix, délais, fréquences de livraison et voies alternatives ;
- ordres de fabrication, campagnes, lots physiques, encours et dates de libération ;
- généalogie des lots, fractionnements, mélanges, expéditions et réceptions ;
- lignes, calendriers, changements de série et contraintes de séquencement ;
- statuts qualité, inspections, quarantaines, libérations, rejets, rebuts, retouches et rappels ;
- priorités clients, niveaux de service, marges et pénalités ;
- coûts en euros du transport accéléré, de l'achat d'urgence, du stock, de la rupture, du rebut et de la qualification d'un fournisseur.

### 2. Rejouer deux incidents connus

Choisir avec les équipes un incident qualité et un incident fournisseur déjà documentés. Comparer la chronologie simulée aux faits : flux touchés, arrêt ou décalage de production, lots exposés, clients touchés, date de reprise et coûts. Corriger le modèle jusqu'à ce que les écarts soient compris et acceptés.

### 3. Élargir l'étude statistique

Une fois les données et règles validées, augmenter le nombre de répétitions et faire varier la date, la durée et la gravité des incidents. Le nombre final devra être fixé par la stabilité des moyennes et des cas défavorables, pas par un chiffre arbitraire.

### 4. Passer à une vraie boucle fermée

Le prolongement naturel est une politique conditionnelle :

> observer chaque jour les stocks, encours, retards, délais fournisseurs et capacités → détecter un seuil de risque → simuler plusieurs réponses → appliquer la réponse autorisée qui respecte les contraintes de service et de coût → réévaluer le lendemain.

Cette boucle devra inclure des règles métier explicites, des limites d'action, des délais de mise en œuvre et une validation humaine. Elle sera comparée au plan fixe actuel sur des incidents jamais utilisés pour la régler.

## Déroulé conseillé du rendez-vous — 15 à 20 minutes

### 1. Poser la question métier — 1 minute

« Lorsqu'un composant est retenu ou retardé, quels lots, produits et clients seront réellement touchés, et quelle réponse réduit le retard au coût acceptable ? »

### 2. Montrer le fonctionnement normal — 2 minutes

Ouvrir la page hors ligne, présenter la chaîne, les stocks, les transports, les fabrications et la référence normale. Expliquer que toutes les solutions repartent du même état au jour 0.

### 3. Dérouler la retenue qualité — 4 minutes

Suivre 021081 vers 773474 puis 268967. Montrer que le client est touché dans 9 cas sur 10, que le pire cas est beaucoup plus sévère que la moyenne, puis comparer le plan combiné et le transport accéléré.

Message à faire passer : « Nous mesurons à la fois l'efficacité et le prix de la protection. »

### 4. Dérouler le retard 338929 — 4 minutes

Montrer que huit cas sont absorbés sans retard client, puis que le transport accéléré supprime le retard dans les deux cas touchés. Comparer son coût au plan combiné et montrer honnêtement que la replanification testée aggrave le résultat.

Message à faire passer : « Le modèle évite de payer une action inutile et détecte aussi les fausses bonnes idées. »

### 5. Montrer les lots exposés — 3 minutes

Ouvrir la traçabilité de la répétition 330281. Distinguer clairement matière d'ascendance exposée et client effectivement en retard. Expliquer les bornes utilisées lors des mélanges de lots.

### 6. Dire les limites — 2 minutes

Préciser que la retenue qualité est simplifiée, que certains leviers sont des approximations, que les coûts ne sont pas encore des euros et que dix répétitions ne sont pas des probabilités industrielles.

Message à faire passer : « Nous savons ce qui est démontré, ce qui doit être calibré et quelles données sont nécessaires. »

### 7. Proposer la collaboration — 2 à 4 minutes

Proposer un premier travail court : récupérer un extrait ERP/MES/WMS, rejouer deux incidents historiques, valider les règles de lots et de qualité, convertir les coûts en euros, puis construire une politique conditionnelle testée avec les équipes achats, planification, production, qualité et logistique.

La conclusion commerciale recommandée est simple :

> « Le démonstrateur montre déjà où un incident se propage et quelles réponses fonctionnent dans le modèle. Avec vos données et vos règles opérationnelles, nous pouvons transformer cette preuve en outil de décision calibré sur votre chaîne. »
