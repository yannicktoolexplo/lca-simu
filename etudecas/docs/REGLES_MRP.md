# Les règles MRP, simplement

**Référence acceptée — demande client et centre de distribution, 8 octobre 2026.**
Décision utilisateur : conserver le résultat `demand_pf_20261008` comme point
de départ sur ce périmètre. Le [registre](reference/mrp_current.json) identifie
le scénario exécuté sur 362 jours, le HTML et leurs empreintes. Un instantané
compressé conserve le graphe exact, la comparaison autonome, la commande
d'exécution et les preuves. Cette adoption conserve explicitement la nature
**estimée** de la réponse industrielle et les quatre semaines non estimables.
Elle ne signifie pas que tous les stocks amont sont calibrés.

**Sorties d'usines reconstituées — comparaison ajoutée le 8 octobre.**
L'[onglet Usines → Muret](../resultats/factory_dispatch_20261008/comparaison.html)
compare les deux PF sans changer cette référence client ni les règles du moteur.
La reconstitution utilise `entrées Muret estimées = stock lundi suivant − stock
lundi + historique Flow − Divers`, sous l'hypothèse explicite que cet historique
représente les sorties clients. La colonne I des mouvements, qui contient un
solde net, n'est pas utilisée comme livraison brute.
Les volumes sont attribués à une fenêtre de départ estimée en reculant les
bornes de réception du délai retenu ; les départs simulés `lane_ship` de l'usine
vers Muret sont sommés sur exactement cette fenêtre. Le décalage initial de
deux jours correspond aux dates exécutées dans les simulations, pas à une
mesure du transport industriel ; il est modifiable dans l'affichage.
Une valeur négative reconstituée signale une incohérence : elle reste dans le
tableau de calcul et interrompt la courbe, sans devenir zéro. Les dates exactes
des départs industriels et leur fréquence dans la semaine restent inconnues.

**Comparaison client — affichage rectifié le 8 octobre.** Le premier graphique
affiche la demande `demand_PF!Demande/E` utilisée par l'essai et les quantités
effectivement servies aux clients dans la simulation (`served_qty`). Il ne
remplace pas le service client par les départs simulés du dépôt.
La correction des quatre demandes négatives de Permixon à zéro reste une
hypothèse de cet essai, explicitement indiquée, pas une mesure industrielle.

Après la précision utilisateur demandant de croiser demande, sorties et CA
perdu, la troisième courbe est une **réponse réelle estimée**, explicitement
distincte d'un comptage des livraisons :
`livré estimé = demande PF × CA livré / (CA livré + CA perdu)`.
Cette formule suppose mêmes périmètres et même prix moyen pour les quantités
livrées et non livrées. Le complément donne le non-livré estimé. Aucun prix
client n'est inventé. Les quatre semaines de demande PF nulle avec du CA
positif restent inconnues, pas zéro, et interrompent la courbe Permixon.

Un tableau rapproche ces valeurs avec la colonne I signée des mouvements
de Muret et le service simulé. Cette colonne n'est pas transformée en livraison
brute : elle contient aussi des mouvements positifs et se rapproche des
variations nettes de stock. La nature de `Actual Demand` (commandes ou ventes)
reste à confirmer ; la série n'est pas renommée en livraison mesurée.
Le CA reste aussi consultable séparément, sans comparaison de son taux avec
le quotient hebdomadaire des unités simulées. Les références historiques
93 % / 80 % n'ont pas de définition suffisamment établie pour ce rapprochement.

Le second graphique compare les **besoins prévus** : colonne I du plan MRP
industriel et besoins projetés par la simulation au même jour, pour le PF à
Muret. Le choix de version est indépendant du site sélectionné ailleurs.
Les semaines de projection suivent la convention dimanche–samedi existante ;
les quantités clients sont agrégées lundi–dimanche. Les entrées prévues et les
stocks projetés restent dans l'onglet MRP. Aucun plan n'est une livraison exécutée.
La simulation n'est pas recalculée pour cette correction d'affichage.
La [vérification indépendante de l'affichage précédent](../artifacts/testing/demand_pf_20261008/quantity_view_validation.json)
rapproche 17 711 contrôles sans erreur : demande, service et besoins MRP des
deux produits avec leurs sources Excel/CSV. Les
[22 contrôles JavaScript historiques en mémoire](../artifacts/testing/demand_pf_20261008/quantity_view_javascript.json)
vérifient notamment l'ordre des graphiques et le changement de version MRP.
Le navigateur n'a pas été exécuté ; ces preuves ne certifient pas la calibration.
Le [rendu des trois courbes](../artifacts/testing/demand_pf_20261008/quantity_reconciliation_revision.json)
conserve exactement les mêmes données et résultats de simulation. Ses
[contrôles JavaScript](../artifacts/testing/demand_pf_20261008/quantity_reconciliation_javascript.json)
vérifient les trois rôles, le calcul estimé et les quatre semaines incohérentes.

**Essai demandé le 8 octobre — retour à la demande `demand_PF`.**
La comparaison `demand_pf_20261008` utilise `demand_PF.xlsx`, feuille
`Demande`, colonne E (`real demand`), comme demande physique des clients.
Pour cet essai seulement, `demande = max(0, real demand)` : les quatre
valeurs négatives de Permixon deviennent zéro, sans réduire les demandes
positives suivantes. Le brut signé et les cellules sources restent visibles.
L'historique de `Flow_Data_Customer_Demand` est affiché séparément ; il
n'est pas renommé en expéditions industrielles mesurées.

Les prévisions datées `Flow / Projection`, les règles MRP, les stocks et
engagements initiaux sont conservés. Seul `meta.customer_demand_history`
change dans le graphe de l'essai. La répartition quotidienne reste entière
et la simulation expédie uniquement pour satisfaire la demande connue.
La réponse simulée comparée est le service exécuté au client, après transport.

La source PF contient des numéros de semaine, sans dates explicites.
Convention de comparaison : `step 1 = lundi 30 décembre 2024`.
Ses 52 semaines se terminent le 28 décembre 2025 ; l'exécution couvre donc
362 jours, sans fabriquer la demande des 29–31 décembre. La part des deux
jours de 2024 n'est pas redistribuée en 2025. Les totaux des 51 semaines
complètes affichées se distinguent de ceux des 362 jours exécutés.
La référence de travail précédente reste conservée comme témoin. La décision
utilisateur ci-dessus promeut cet essai sur le périmètre demande / dépôt ;
elle ne prouve pas le sens industriel des valeurs négatives.

Résultat vérifié : l'écart absolu moyen de stock à Muret, sur les mêmes
52 photos (celle du 29 décembre représente la clôture du 28), passe de
240 023 à 289 191 UN pour Cicalfate et de 177 434 à 177 680 UN pour Permixon.
Ce retour à la demande PF ne suffit donc pas à améliorer ces deux stocks.
La [comparaison interactive](../resultats/demand_pf_20261008/comparaison.html)
conserve les deux calculs ; la [vérification indépendante](../artifacts/testing/demand_pf_20261008/validation.json)
rapproche sources, quantités quotidiennes, événements et valeurs du HTML.
Le [rapport d'exécution](../artifacts/testing/demand_pf_20261008/report_pf_zero.json)
et le [contrôle des bilans et tests](../artifacts/testing/demand_pf_20261008/toolbox/gate-83c1f1c7841c42939a294f9315f3874d/manifest.json)
documentent cet essai ; aucun contrôle navigateur n'a été exécuté.

**Référence MRP 2025 précédente — conservée pour comparaison.** La version
`customer_orders_only_20261008/run_candidate_365`, avec son graphe
`graph_candidate.json`, était le point de départ avant l'adoption de la
référence demande / centre de distribution ci-dessus.
Elle conserve les règles amont C8R et limite les départs clients à la demande
connue (`known_demand_only_v1`). C8R devient un témoin historique, hors du
parcours courant ; ses résultats restent conservés pour mesurer les progrès
et les régressions. Ce choix corrige une incohérence métier, mais ne signifie
pas que tous les stocks se rapprochent des sources : les écarts de Cicalfate
baissent et ceux de Permixon augmentent sur les 52 photos 2025. Le nominal
historique de cinq ans et ses campagnes de risques restent distincts de cette
référence de travail annuelle.
Le [registre de cette référence](reference/mrp_current.json) fixe le graphe,
les paramètres de la commande exécutée, les fichiers du moteur et les résultats.

**Comparaison prévisions / départs.** Pour chaque semaine complète de 2025,
retenir une seule valeur prévisionnelle de cette semaine, dans la dernière
version qui la renseigne et qui était connue au lundi d'ouverture. Si le
nouveau plan omet la semaine courante, conserver sa dernière valeur explicite
du plan antérieur ; une absence n'est pas un zéro. Ne pas sommer les versions
mensuelles. Le total ainsi obtenu est un total de prévisions glissantes,
pas celui d'un plan annuel unique. Les départs simulés sont les événements
`lane_ship` de Muret vers le client, non les réceptions ni le service après
transport. `Actual Demand` reste l'historique client source, sans être assimilé
à des expéditions industrielles tant que son sens physique n'est pas confirmé.
Les mouvements signés du dépôt ne permettent pas de reconstruire ces départs
bruts avec certitude. La concordance historique/départs simulés n'est pas un
test indépendant, puisque cet historique alimente aussi la simulation.

**Clarification client du 8 octobre — commandes connues uniquement.** L'utilisateur
confirme qu'il s'agit de clients, sans politique de stock de distribution à
réapprovisionner depuis une prévision. Les prévisions servent à planifier les
fabrications et les approvisionnements ; elles ne constituent pas des commandes
physiques à expédier. La règle `known_demand_only_v1`, sélectionnée explicitement
par article/client, remplace la couverture prévisionnelle historique :

```text
après les réceptions et le service du jour :
quantité à expédier = max(0, demande connue restant à servir
                            − stock client encore utilisable
                            − quantités déjà engagées vers ce client)
```

Tous les engagements ouverts couvrent le besoin une seule fois, même si leur
date est tardive. Stock, transport et quantités UN entières restent applicables.
Ni le reliquat d'une prévision hebdomadaire ni une prévision future ne créent
un départ client dans ce mode. Les anciennes règles restent reproductibles.

Les sources donnent une demande historique hebdomadaire, sans dates de prise
de commande et de livraison souhaitée. La comparaison conserve sa répartition
journalière existante et la considère connue le jour où elle apparaît. Avec
deux jours de transport, cela peut produire un reliquat durant le transit : ce
compteur ne démontre pas un retard industriel. Ne pas supprimer le délai ou
utiliser la demande future pour le masquer. L'étude séparée
`artifacts/testing/customer_orders_only_20261008` conserve les exécutions et
leurs preuves ; la conformité à cette règle ne certifie pas la calibration
des stocks ni le calendrier des fabrications.

**Résultat de l'essai 2025 :** les deux PF n'ont aucun départ excédant la
demande connue, aucun stock client après service et aucune demande connue
restant à expédier. L'attente finale correspond entièrement au transport de
deux jours. Les 48 tests ciblés et les qualifications CSV passent ;
l'oracle indépendant contrôle 19 872 assertions. L'erreur moyenne de stock
Muret sur 52 photos passe de 254 470 à 240 023 UN pour 268091, mais de
145 076 à 177 434 UN pour 268967. La correction d'expédition ne résout donc
pas la calibration amont. Le témoin reproduit les deux PF sur 90 jours ;
une différence préexistante de 1 UN sur 338929 empêche de déclarer une
reproduction strictement identique de tous les articles face à C8R.
Voir le [rapport et les courbes](../resultats/customer_orders_only_20261008/rapport.md),
le [manifeste des contrôles techniques](../artifacts/testing/customer_orders_only_20261008/toolbox/gate-d577048ba68147be867d048de1865495/manifest.json)
et l'[oracle indépendant](../artifacts/testing/customer_orders_only_20261008/validation/dispatch_oracle.json).

**Suite du 7 octobre — banc local A :** le [protocole et les résultats](REFONDATION_MRP.md#résultats-du-banc-local-a--7-octobre-2026)
portent sur quatre couples, 208 versions et 832 plans conditionnels, avec H
réservé à la comparaison. L'[HTML local](../resultats/mrp_local_20261007/comparaison.html)
sépare courant restant/exclu, addition/maximum, arrivée/disponibilité et
couverture. Le banc est retenu pour le diagnostic ; **aucune nouvelle politique
de chaîne n'est adoptée**. La matrice C8R ci-dessous reste celle de la référence
conservée. Les [preuves](../artifacts/testing/mrp_local_20261007/manifest.json)
précisent les contrôles exécutés et leurs limites.

**Correction numérique retenue :** les incréments de l'enveloppe de protection
sont publiés en fragments datés dont les représentations décimales conservent
exactement le budget. Un arrondi intermédiaire vers le haut créait auparavant
une UN supplémentaire dans 316 plans du banc. Aucun paramètre de sécurité, lot,
fournisseur ou périmètre industriel n'est modifié. Les références C8R antérieures
ne sont pas recalculées ; lire le bilan du banc pour le diff ciblé et les preuves.

**Audit aval, 7 octobre :** la lecture de la demande client et les conservations
DC/client/transit sont vérifiées sur C8R, mais le stock client anticipé n'est
pas observé. Les 10/15 jours de réception PF sont sourcés dans la division
Muret ; leur localisation avant départ dans les usines reste hypothétique.
Les départs C8R sont revus quotidiennement, sans attente camion plein ; leurs
multiples dérivent des lots de fabrication. Aucune cadence industrielle n'est
identifiée dans les soldes hebdomadaires Muret. Lire l'[audit aval](REFONDATION_MRP.md#audit-aval--demande-muret-et-expéditions-pf-7-octobre-2026)
et ses [preuves](../artifacts/testing/mrp_local_20261007/dc_dispatch_audit_manifest.json)
avant de généraliser la règle « PF directement au dépôt ».

## Registre consolidé au 7 octobre 2026 : référence C8R

**C8R est le compromis de comparaison conservé, pas un modèle industriel calibré.**
Le [graphe exact](../artifacts/testing/mrp_packaging_solutions_20261006/graph_C8R.json)
et le [rapport d'exécution](../artifacts/testing/mrp_packaging_solutions_20261006/report_C8R.json)
désignent 365 jours physiques de 2025. Les projections restent glissantes sur
52 semaines et peuvent dépasser décembre. Les résultats de C8R ont été produits
sur un code stable à l'exécution ; le moteur de travail a changé depuis. Lire
ses CSV ne constitue pas une réexécution de ce moteur actuel.

L'[inventaire machine du scénario](../artifacts/testing/scan3_scope_20261007/scenario_audit.json)
joint le graphe, la commande et `run_C8R_365/run/policy.json`. C'est indispensable : le
graphe garde notamment 1 825 jours et `state_scale=0.02`, mais la commande
exécutée impose **365 jours et une échelle 1**. Les flags dynamiques finaux
annulent les anciens couples statiques ; le résumé effectif donne une liste
statique vide. La projection MRP vaut **364 jours**, soit 52 semaines, et non
la durée physique de simulation.

**L'exclusivité Scan3 aux seuls PF 268091/268967 est une hypothèse rouverte.**
I = « Sorties » et J = « Sorties_article_scan3 » dans le fichier de mouvements.
Leurs signes participent au bilan ; I n'est ni un total incluant J, ni une
consommation hors projet prouvée partout. Dans le fichier MRP, I désigne au
contraire les besoins et J des contributions de stock datées. Ces deux contrats
de colonnes ne sont jamais interchangeables. Voir l'[audit consolidé](../artifacts/testing/audit_perimetre_scan3_20261007.md).

La table ci-dessous prime pour l'activation C8R. Les fiches qui suivent conservent
les formules et essais historiques, avec leurs noms C, A, Q, PACK, etc. Une règle
présente dans ces fiches n'est pas automatiquement active dans C8R.

| Règle et formule | Périmètre et condition réelle C8R | Origine / statut de preuve |
|---|---|---|
| Prévision connue : dernière version publiée avant la décision ; `reste = max(0, prévision semaine − demande arrivée)` | Clients des deux PF puis réseau amont ; 52 semaines glissantes. Les prévisions 2026 sources sont conservées sans +5 %. | Classeur client + convention de publication au lundi ; consommation de prévision programmée, pas mode ERP identifié. |
| Besoin composant : `Σ(fabrication restante × coefficient BOM de son étape) + autres usages prévus` | `separate_own_and_other_v1` ; le total MRP industriel reste une comparaison, sauf les deux étuis ci-dessous. Ne pas transformer l'écart industriel/BOM en consommation physique. | BOM source ; séparation des usages et estimation complémentaire hypothétiques tant que Scan3 n'est pas identifié. |
| Étuis : sur semaine renseignée, `besoin = max(besoin industriel restant, besoin déjà engagé)` ; sinon besoin du modèle | 338929/Avène et 333362/Gien seulement : `source_weekly_with_committed_floor_v1`. | Compromis C8R ; identité commune des OF et des besoins MRP non prouvée. C9/C10 exclusifs et C11/C12 cumulés non retenus. |
| Révision industrielle : dernière version connue de l'article/site pour le futur ; semaine en cours gelée à sa version préalable | `latest_vintage_v1`. Une semaine supprimée n'est pas réimportée d'une ancienne version ; absence ne signifie pas zéro. | Correction de sélection des versions ; repli BOM/autres usages conservé. Distinct du calendrier de prévisions client. |
| Exécution historique I : répartir `−I` sur les sept jours de la semaine ; UN par différences de cumuls entiers | Couples admissibles seulement : aucune I positive, pas de fabrication locale ni de transfert sortant déjà représenté. Jour documenté remplace estimation ; jour absent garde estimation. | Observation hebdomadaire + convention de répartition journalière ; l'affectation aux « autres usages » demeure hypothétique. Ce rejeu n'est pas une prévision autonome. |
| Position : `disponible + entrées utilisables à t − besoins restants à t` ; `déficit = max(0, protection − position)` | Tous les stocks effectivement planifiés ; disponible, réservé, indisponible, fabrication et transit restent séparés. | Noyau commun ; déduire chaque engagement une seule fois. Une libération ne crée pas une réception physique. |
| Achat protégé : `date besoin − sécurité ouvrée − réception ouvrée − délai fournisseur` | Achats datés déterministes ; calendrier réellement appliqué ; regroupement 1 jour, sauf politique explicitement configurée. | Jours source et confirmation lundi–vendredi ; délai fournisseur sans Erlang dans cette phase. |
| Sécurité achats : anticipation des besoins + stock fixe ; autres nœuds : `max(stock fixe, besoins pendant jours source)` | Ne pas ajouter une seconde anticipation à un besoin déjà avancé. 049371, 333362, 730384, 708073 possèdent les deux paramètres. | Convention actuelle à identifier ; l'addition et le maximum ne sont pas deux formulations équivalentes du même choix métier. |
| Dépôt Muret : 20 jours 268091, 25 jours 268967, à 100 % | Comparaison 2025, sans coefficient 0,75. | Choix utilisateur ; distinct des politiques plus récentes conservées dans les sources. |
| Fournisseur : offre choisie/parts configurées, ou principal/secours si déclaré | 001848/Avène : principal 1,58 €/kg, 56 j, 6 000 kg ; secours 4,20 €/kg, 21 j, 4 000 kg. Ne pas généraliser cette sélection. | Offres source et principal confirmé ; déclencheur du secours et parts des autres offres restent conventions. |
| Quantité : arrondi net masse au kg le plus proche, demi supérieur ; puis minimum/multiple/plafond propres à l'opération | UN physiques entières. 268091 : min 28 800, multiple 14 400, plafond 142 485 (plus grand multiple admissible 129 600). 268967 : 107 800 UN ; 773474 : 3 200 kg ; 693055 : 600 kg. | Sources + conventions utilisateur/modèle ; un standard achat n'est pas nécessairement un multiple. Standards des deux étuis non contraignants dans C8R. |
| Complément carnet initial : `max(0, H premier plan − engagements représentés)` | Deux étuis ; connu au premier plan du 5 janvier. 423 027 UN supplémentaires à Avène, sans créditer le stock du 1er janvier ni créer un achat nouveau. | Reconstruction hypothétique d'engagements ; jour et fermeté non démontrés. |
| Report de promesse : retirer sa seule couverture, rechercher son besoin, garder identité/quantité/fournisseur et plancher de date originale | Promesses d'achats des deux étuis supposées modifiables ; revue hebdomadaire. Ni réception exécutée ni transport parti déplacés. | Hypothèse de statut ; C8R meilleur compromis local du lot d'essais, pas validation des commandes ERP. |
| PACK initial : `reste à conditionner = quantité OF − quantité déjà conditionnée`, limité par emballages, capacité et calendrier | 20 OF initiaux Avène, 1 945 715 PF ; matières supposées incorporées avant ouverture, Pack prélevé au conditionnement. Pas de même OF initial à Gien. | Rôle Pack source ; statut matière/emballage initial hypothétique. **Actif dans C8R**, même si les premières fiches ci-dessous le décrivent comme essai. |
| Lancement : minimum du besoin dû, composants utilisables, capacité et lots admissibles | Avène/Gien/Gaillac. Fermeture Avène 4–15 août inclus. `tau_process` reste un paramètre de planification. | Contraintes programmées ; aucune durée physique de fabrication déduite sans confirmation. Capacité Gaillac d'un lot/jour conventionnelle. |
| Libération et circulation : présence physique puis disponibilité ; PF libérés poussés à Muret sous contraintes | PF Avène 10 j ouvrés, Gien 15 ; Gaillac 693055 28 ouvrés, 773474 33 ouvrés. Routes semi-finis : 773474 transport 10 j puis réception Gien 6 ouvrés ; 693055 transport 7 j puis Avène 7 ouvrés. PF → Muret : 2,5 j ; Muret → client : 2 j. | Sources/conventions localisées ; transports 693055, PF/Muret et Muret/client hypothétiques. Les 70 j FIA ne sont pas 70 j de camion. `stochastic_lead_times=false` malgré le type historique `erlang_pipeline` des routes. |
| Fabrication 693055 : lot Gaillac avec intrant fictif explicite | BOM amont industrielle absente. | Hypothèse autorisée ; ne prouve ni formule ni consommation industrielle réelle. |
| Bilan : `stock fin = stock début + entrées + mouvements signés` ; `retard fin = retard début + besoin arrivé − servi` | Chaque article/site ; propositions, achats engagés, fabrications, départs, réceptions, disponibilité et deux suivis de lots restent distincts. | Invariants physiques ; fermeture numérique ≠ calibration. Objectif d'un an médicament global, pas un an à chaque nœud. |

### Matrice d'application par nœud et opération

| Nœud / articles | Besoin utilisé | Protection / ordre / exécution | Limite à garder visible |
|---|---|---|---|
| Clients 268091/268967 → DC-1920 Muret | Historique au jour courant + prévision résiduelle connue | Dépôt 20/25 jours ; couverture client pendant transport ; expédition puis service | Demande arrivée n'est pas livraison industrielle mesurée ; tampon client non observé. |
| M-1810 Avène / 268091 | Besoin net dépôt, engagements, BOM | Fabrication par lots ; PACK initial ; libération 10 ouvrés puis transfert | Correspondance matières/conditionnement/Scan3 non résolue. |
| M-1430 Gien / 268967 | Besoin net dépôt, engagements, BOM | Lot 107 800 ; libération 15 ouvrés puis transfert | PGA inactif ; 60,342 capsules/PF ne justifie pas une BOM multipliée par cinq. |
| M-1810 / 338929 ; M-1430 / 333362 | Besoin industriel des semaines renseignées, plancher engagé ; modèle hors couverture | Achat protégé, standard non contraignant, complément ouverture, revue et report hebdomadaires | Compromis C8R limité aux étuis, non généralisable à 049371. |
| M-1810 / autres composants BOM, dont 049371 | BOM + prévision séparée des autres usages ; MRP industriel comme comparaison | Achat par offre ou transfert 693055 ; rejeu I uniquement si admissible | I peut contenir des contre-mouvements ; les couples avec I positive sont exclus du rejeu et gardent l'estimation. |
| M-1430 / autres composants BOM, dont 773474 et 042342 | BOM + autres usages prévus | Achats externes ou transfert 773474 ; délais/réception propres | Quantités de capsules et semi-fini cohérentes entre elles, périmètre de l'étui différent ou étape à documenter. |
| Gaillac / 773474 → Gien | Besoin interne de Gien + besoins locaux distincts | Fabrication 3 200 kg, stock Gaillac, transport 10 j, réception 6 ouvrés | I Gaillac peut être transfert ; égalité annuelle 67 200 kg ne relie pas individuellement les ordres. |
| Gaillac / 693055 → Avène | Besoin interne d'Avène + besoins locaux distincts | Fabrication 600 kg, intrant fictif, transport 7 j hypothétique, réception 7 ouvrés | Absence de BOM amont ; hypothèse explicitement séparée des données source. |
| Gaillac / 021081 | Explosion BOM de 773474 | Achat selon offres et calendriers | Coefficient 8,94 kg pour 1 kg de 773474 ; transformation, pas égalité de masses sans rendements/coproducts. |
| Autres couples présents dans les Excel | Ne pas les créer par simple présence documentaire | Déclarer état, route et politique propres avant approvisionnement | Couverture partielle/absente et unités restent visibles dans le classement historique. |

Périmètres exacts tirés de la politique exécutée, sans confondre présence dans
les sources et activation :

| Site | Besoins MRP industriels (24 couples) | Rejeu physique I admissible (21 couples) |
|---|---|---|
| Gien | 038005, 042342, 333362, 344135, 708073, 730384, 734545, 773474 | 001848, 038005, 333362, 344135, 708073, 730384, 734545, 773474 |
| Avène | 001757, 001848, 001893, 002612, 007923, 016332, 029313, 039668, 049371, 055703, 099439, 338928, 338929, 426331, 693055 | 001757, 001848, 002612, 007923, 049371, 055703, 338928, 338929, 426331, 693055 |
| Gaillac | 021081 | 001893, 002612, 021081 |

Les prévisions séparées d'autres usages concernent **18 couples**, listés avec
les paramètres détaillés dans l'inventaire machine. Une I positive sur une seule
semaine exclut **tout le couple** du rejeu, même si son total annuel reste négatif :
c'est le cas de 001893/Avène. Les quatre autres exclusions de matières Avène sont
016332, 029313, 039668, 099439. L'absence de rejeu ne signifie pas absence d'usage.

001848/Gien utilise une **politique candidate** de multiple 7 000 kg et protection
26 jours ouvrés, pas une sécurité source confirmée. Gaillac 001893/002612 restent
partiellement représentés, sans politique complète d'approvisionnement.

**Transferts expérimentaux inactifs dans C8R :** les trois clés
`internal_transfer_planning_lot_policy` (L), `internal_transfer_commitment_policy`
(K), `internal_transfer_rescheduling_policy` (A) sont absentes du graphe et du
journal exécuté. `production_programme_policy` (PGA) est également absente.
Le multiple physique de transfert 600 kg de 693055 reste actif ; le lot de
fabrication 3 200 kg de 773474 n'est **pas** un multiple de transfert actif C8R.

### Essais et décisions

- C8R : reproduction annuelle de C8 après correction décimale ; mêmes achats,
  réceptions et contraintes, au plus 1 UN d'écart sur 11 clôtures 338929.
  Compromis conservé ; 9 des 27 stocks annuels restent au-dessus de 50 % d'écart
  moyen rapporté au stock réel moyen. [Bilan et preuves](../artifacts/testing/mrp_packaging_solutions_20261006/bilan.md).
- PGA : avancement d'un lot existant dans chaque usine ; **non retenu**,
  9 stocks améliorés, 15 dégradés, 3 identiques, volumes annuels inchangés.
  [Bilan annuel](../artifacts/testing/mrp_production_programme_20261006/bilan.md).
- Q et C11/C12 (enveloppes cumulées), C9/C10 (industriel exclusif), essais de
  maintien/avancement des transferts : conserver leurs résultats et limites
  propres ; aucune adoption implicite par leur présence dans le code.
- Audit Scan3 du 7 octobre : **correction documentaire retenue** ; périmètre
  produit/vrac encore hypothétique ; aucune modification ni nouvelle simulation
  du moteur. A = identification locale avec besoins industriels connus ;
  B = chaîne depuis demande/BOM. Un rejeu des observations ne valide pas B.

## Fiches historiques et formules détaillées

Les paragraphes suivants décrivent leurs références nommées, principalement C,
puis les essais successifs. Les anciens essais restent dans le
[journal d'analyse](../data/reports/mrp_source_rules.md).

## Deux essais isolés sur les emballages

La référence C conserve ses règles. Les options suivantes ne sont activées que
dans les graphes expérimentaux PACK et REPORT, sur 365 jours. Les résultats et
leurs vérifications sont conservés dans
`artifacts/testing/packaging_trials_20261005` ; la présence du code ne signifie
pas que la règle est validée industriellement ou adoptée dans le nominal.

**PACK — terminer le conditionnement des fabrications initiales.** Pour les OF
explicitement sélectionnés et les composants classés « Pack » dans la BOM :

```text
reste à conditionner = quantité de l'OF − quantité déjà conditionnée
quantité réalisable = minimum(reste, capacité libre, quantité permise par les emballages disponibles)
besoin d'emballage restant = besoin total de l'OF − prélèvements déjà exécutés
```

Les OF initiaux sont servis dans l'ordre de leur date source, avant les nouvelles
fabrications, sur la même capacité journalière. Les emballages sont prévus dans
le MRP et prélevés physiquement lors du conditionnement. Les matières déjà
incorporées dans l'encours ne sont pas prélevées une seconde fois. Les unités
physiques restent entières ; l'arrondi cumulé par OF évite de répéter l'arrondi
à chaque fraction. Un retard de conditionnement décale la libération en
conservant la durée en jours ouvrés entre les dates G et I de l'OF source.
L'état « matières incorporées, emballages non encore prélevés » est une hypothèse
de cet essai, pas un statut industriel disponible dans les fichiers.

**REPORT — décaler une réception encore modifiable.** Uniquement pour un
engagement déclaré non expédié, non réceptionné et replanifiable :

```text
date limite = première date où, sans cet engagement, le stock projeté passe sous la protection
nouvelle disponibilité = au plus tard cette date, sans avancer la réception existante
```

Les autres engagements restent déduits du besoin. La quantité et l'identité
sont conservées, puis le MRP est recalculé avant tout nouvel achat. En l'absence
de déficit, le report reste limité à l'horizon continu des prévisions connues ;
une semaine absente n'est pas un besoin nul. Le délai de traitement à réception
reste compté du lundi au vendredi. Le scénario Gien porte sur six commandes
initiales ; leur permission expérimentale de report expire avant leur date
physique initiale, même si leur réception a entre-temps été décalée. Les sources
ne prouvent pas leur statut d'expédition. La date reconstruite de lancement
d'une commande n'est donc pas utilisée comme preuve de départ d'un camion.

## Le principe commun

On part de la demande client, puis on remonte les besoins vers le dépôt, les
usines de produits finis, les semi-finis et les fournisseurs. On exécute ensuite
les mouvements dans l'autre sens, avec les matières réellement disponibles.

```text
position prévue à t = disponible aujourd'hui
                      + entrées utilisables d'ici t
                      − besoins restant à servir d'ici t

déficit à t = max(0, protection demandée à t − position prévue à t)
```

Un déficit de date ne signifie pas automatiquement une nouvelle commande :
si une quantité est déjà commandée mais arrive trop tard, il faut traiter sa
date et son retard sans la commander deux fois. Le moteur conserve ces deux
questions : **combien manque-t-il réellement** et **quand cette quantité sera-t-elle disponible**.

## Toutes les règles de décision de ce parcours

| N° | Règle simple | À quoi elle s'applique |
|---|---|---|
| 1 | **Recalculer sur 52 semaines glissantes**, avec les prévisions connues au jour du calcul. | Toute la chaîne ; le calcul physique de comparaison reste limité à 2025. |
| 2 | **Ne pas ajouter la demande réelle à la prévision complète.** `Prévision restante = max(0, prévision de la semaine − demande déjà arrivée)`. | Demande des clients, puis besoins remontés à Muret et aux usines. |
| 3 | **Propager les besoins par la nomenclature.** `Besoin du composant = fabrication prévue × quantité de composant par produit`. Diviser la quantité BOM par sa taille de base et convertir les unités. Utiliser la date de lancement de la fabrication. | Usines PF vers matières/emballages/semi-finis ; usine de semi-finis vers ses matières. |
| 4 | **Compléter les besoins BOM à partir du plan industriel.** Dans C, pour une semaine documentée : `complément prévu = max(0, besoin industriel total − besoin propre calculé par BOM)`. Ce maximum hebdomadaire peut gonfler le total lorsque les deux calendriers représentent un même usage décalé. | Matières et composants ayant un plan industriel. Le rapprochement des usages reste une hypothèse ; voir l'essai Q ci-dessous. |
| 5 | **Utiliser le stock disponible avant de commander.** Le stock bloqué/libéré plus tard, la fabrication en cours et le transit ont chacun leur date de disponibilité. | Tous les stocks. La sécurité est un objectif, pas une quantité physiquement bloquée. |
| 6 | **Déduire chaque engagement une seule fois.** Une quantité en commande, fabrication ou transit ne doit pas provoquer une seconde commande pour le même besoin. | Achats, fabrications et transferts. Une entrée tardive reste signalée comme tardive. |
| 7 | **Protéger les besoins avec les jours de sécurité et le stock fixe configurés.** Recalculer cette protection à chaque date future. | Matières, composants internes, fabrications et dépôts ayant une politique de stock. Voir les deux modes ci-dessous. |
| 8 | **Commander assez tôt pour disposer de la matière à la date protégée.** Retrancher traitement à réception, puis délai fournisseur, en respectant leurs calendriers. | Achats de matières et emballages. Pour les transferts internes, utiliser le transport et le traitement propres à la route. |
| 9 | **Choisir un créneau réellement autorisé.** Prendre le dernier départ/lancement permettant de respecter la date ; si elle est déjà impossible, prendre le premier encore possible et conserver le retard. | Transferts et fabrications datés. Les créneaux sont ceux du modèle, pas des rendez-vous industriels identifiés. |
| 10 | **Choisir le fournisseur selon la politique du couple article/site.** Fournisseur désigné, principal/secours ou répartition configurée ; utiliser son prix, son délai et son lot. | Achats externes des usines PF et de Gaillac. Le moins cher n'est pas imposé universellement. |
| 11 | **Dimensionner selon minimum, multiple et maximum.** Arrondir au multiple supérieur lorsqu'il est obligatoire ; découper si le maximum par lot est dépassé. Le surplus sert aux besoins suivants. | Commandes, lots de fabrication et transferts disposant d'une contrainte explicite. |
| 12 | **Regrouper seulement les besoins encore non couverts dans la fenêtre configurée.** La fenêtre d'achat actuelle est de **1 jour**. | Achats datés ; aucun regroupement mensuel universel n'est établi. Un départ hebdomadaire ne signifie pas une commande hebdomadaire. |
| 13 | **Ne lancer la fabrication que lorsqu'elle est due et réalisable.** Limiter par composants disponibles, capacité, lots et calendrier. Une autorisation n'est pas une fabrication terminée. | Gaillac, Gien et Avène. Les encours restent distincts du produit disponible. |
| 14 | **Rendre le produit utilisable après le traitement configuré.** Une matière reçue ou un produit terminé peut être présent mais encore indisponible. | Réceptions fournisseurs, semi-finis et PF. Un changement de disponibilité ne crée pas une seconde entrée physique. |
| 15 | **Envoyer au dépôt les PF libérés de l'usine**, au créneau d'expédition et dans les limites physiques. | Avène → Muret et Gien → Muret. Le stock encore en contrôle reste à l'usine selon la convention retenue. |
| 16 | **Expédier seulement la demande client connue non couverte** : `max(0, demande restant à servir − stock client utilisable − engagements ouverts)`. | Muret → client, mode `known_demand_only_v1` testé le 8 octobre. L'ancienne couverture prévisionnelle pendant le transport reste reproductible dans C8R ; elle autorisait des envois sans demande correspondante. |
| 17 | **Reporter ce qui n'a pas été servi.** `Retard fin = retard début + besoin arrivé − quantité servie`. | Demande client et autres consommations physiques ; besoins de fabrication restent en attente si les composants manquent. |
| 18 | **Recalculer les propositions non exécutées ; conserver les ordres réellement engagés.** Une proposition modifiable n'est pas une commande ferme. | Tout le plan daté. Les achats externes fermes ne sont pas automatiquement annulés ou avancés. |
| 19 | **Garder le même lot dans le plan et dans le transport interne.** | Essai L, repris dans K et A : routes internes uniques ayant un multiple physique explicite ; 3 200 kg pour 773474, 600 kg déjà configurés pour 693055. |
| 20 | **Maintenir puis avancer un transfert engagé lorsqu'un départ plus proche est nécessaire et physiquement possible.** Garder son identité et déduire la quantité effectivement expédiée. | Essai A vérifié sur 2025, sur les transferts admissibles Gaillac → Gien/Avène. Le blocage de janvier est corrigé ; A ne remplace pas globalement C. |
| 21 | **Rapprocher les besoins cumulés sans retarder les échéances.** `Cumul retenu à t = max(cumul industriel à t, cumul BOM à t)` sur les dates couvertes. | Essai Q, pour tous les composants disposant des deux prévisions. Ce n'est pas une règle ERP démontrée ni un remplacement automatique de C. |

## Les formules et conditions à ne pas confondre

### Rapprochement des besoins — essai Q

Le calcul utilise seulement les prévisions connues au jour de décision et les
dates futures effectivement documentées. Une semaine absente n'est pas un zéro.

```text
cumul BOM(t) = somme des besoins BOM couverts, jusqu'à t
cumul industriel(t) = somme des besoins industriels couverts, jusqu'à t
cumul retenu(t) = max(cumul BOM(t), cumul industriel(t))
besoin retenu(t) = cumul retenu(t) − cumul retenu(date couverte précédente)
```

Chaque quantité BOM est rattachée à ses fragments de prévision, dans l'ordre
des échéances. Sa date peut être avancée, jamais retardée. La consommation
physique reste déclenchée par la fabrication ; aucune consommation future
observée n'est injectée. Les engagements et les réserves ne sont pas des besoins
à fusionner. Les besoins hors couverture et les arriérés restent conservés.

À la fin de la période couverte, la quantité prévue vaut le plus grand des deux
totaux ; à chaque date, elle couvre au moins chacun des deux cumuls. Cette
construction suppose toutefois que les deux prévisions décrivent des usages
qui se recouvrent. Elle pourrait sous-estimer deux usages réellement distincts.
La comparaison des stocks, des fabrications et des manques matière doit donc
accompagner la vérification du calcul. Le [bilan de l'essai](../artifacts/testing/mrp_scope_reconciliation_20261005/bilan.md)
consigne les résultats et la décision de conservation.

Une journée avec un événement de manque matière peut encore comporter une
fabrication partielle. Ce compteur n'est ni un nombre de commandes manquées,
ni un nombre de journées sans production. De même, un stock disponible nul
ne prouve pas, à lui seul, qu'un besoin est resté non servi.

Le premier essai P ne protégeait que le total final : il pouvait effacer un
besoin proche en le compensant par une BOM lointaine. Ses résultats annuels
sont conservés, mais cette variante n'est pas retenue comme règle générale.

### Sécurité et dates

Pour les achats externes, le mode actif anticipe chaque besoin et conserve le
stock fixe en plus :

```text
date protégée du besoin = date du besoin − jours de sécurité ouvrés
arrivée physique visée = date protégée − traitement à réception ouvré
dernière date de commande = arrivée physique visée − délai fournisseur

quantité protégée cumulée = stock fixe source + besoins cumulés ainsi anticipés
```

Les calendriers sont inversés réellement : on ne remplace pas 20 jours ouvrés
par 20 jours calendaires. Le délai fournisseur est déterministe dans ces essais,
sans tirage Erlang. Le traitement à réception et la sécurité utilisent lundi–vendredi.

Pour les fabrications, dépôts et composants internes utilisant un plancher de
stock, la règle active est :

```text
sécurité(t) = max(stock fixe source,
                  besoins prévus entre t et la fin des jours de sécurité)
```

On n'ajoute pas une seconde anticipation de sécurité au même besoin. Aux achats,
stock fixe et anticipation sont additionnés par la politique actuelle ; aux
autres nœuds, le plancher est le maximum ci-dessus. Cette différence est explicite,
elle ne doit pas être masquée par une formule unique approximative.

### Fournisseurs et quantités

- **001848/Avène** : principal confirmé à 1,58 €/kg, 56 jours, standard 6 000 kg ;
  secours à 4,20 €/kg, 21 jours, standard 4 000 kg. Le secours est proposé pour un
  besoin non couvert avant la disponibilité du principal, s'il arrive plus tôt.
  Son déclencheur exact reste une convention testée, pas une date de commande ERP prouvée.
- Pour les autres couples, le fournisseur sélectionné ou les parts configurées
  restent appliqués. La règle principal/secours n'a pas été confirmée partout.
- Les propositions lointaines principal/secours peuvent utiliser le plus petit
  standard admissible ; au lancement, le lot du fournisseur réellement choisi
  s'applique et son surplus est immédiatement déduit des besoins suivants.
- Les standards de **338929 et 333362** restent non contraignants dans cette
  référence. Ce sont des réglages particuliers à revoir, pas une règle générale.
- Les besoins nets de masse sont arrondis **au kg le plus proche**, demi vers le
  haut, avant le dimensionnement en lots ; le résidu reste dans le calcul. Ce
  n'est pas la même chose que l'arrondi au multiple supérieur d'une commande.
  Les quantités physiques en **UN sont entières** ; les prévisions peuvent être fractionnaires.
- Un maximum de lot limite un lot, pas la production annuelle. Pour 268091 :
  minimum 28 800 UN, multiple 14 400 UN et plafond source 142 485 UN ; le plus grand
  multiple admissible est donc 129 600 UN. Plusieurs lots peuvent être nécessaires.
  268967 utilise 107 800 UN ; 773474, 3 200 kg ; 693055, 600 kg.

### Avancement d'un engagement interne — essai A

On conserve le plan normal, puis on regarde ce qui devrait partir aujourd'hui
sans les seules promesses internes encore futures. Les engagements déjà dus
restent dans ce second calcul.

```text
supplément à avancer = min(reliquat des promesses futures,
                          max(0, nouvelles propositions dues aujourd'hui sans ces promesses
                                 − nouvelles propositions normales dues aujourd'hui))
```

Ce calcul ne lance aucune autre proposition de fabrication ou d'achat. Le
contrôleur physique vérifie ensuite les lots, le créneau, le disponible, la
capacité et le partage du stock. Seule la quantité réellement partie est
affectée à l'engagement existant. Ses dates originales restent traçables ; un
reliquat non expédié conserve sa date. Le transit remplace cette partie de la
promesse, sans addition des deux.

## À chaque liaison, quelle décision ?

| Liaison | Origine du besoin | Décision |
|---|---|---|
| Client → Muret | Demande arrivée, prévision restante et retard | Préparer les expéditions et les besoins futurs du dépôt. |
| Muret → usine PF | Demande, stock/engagements du dépôt et sécurité | Proposer des fabrications PF ; les quantités libérées sont ensuite poussées au dépôt. |
| Usine PF → Gaillac semi-fini | Fabrications PF prévues, BOM, usages industriels documentés et sécurité du composant | Transférer le semi-fini, puis produire à Gaillac la quantité amont non couverte. |
| Usine PF → fournisseur | Besoins matières/emballages et autres usages prévus | Commander selon délai, réception, sécurité et lot du fournisseur. |
| Gaillac producteur → fournisseur | Besoins de fabrication des semi-finis | Même calcul d'achat pour les matières réellement représentées. |
| Site jouant le rôle de réserve → autre site | Besoin du site destinataire | Transfert du stock existant ; aucune transformation si aucune BOM n'est utilisée. Seulement pour les routes effectivement modélisées. |

## Conventions importantes et limites actuelles

- **Périmètre** : la présence d'un article/site dans un Excel ne suffit pas à
  l'activer dans le moteur. Le [bilan de couverture](../artifacts/testing/mrp_reference_coverage_20261005/bilan.md)
  distingue 27 comparaisons annuelles, 2 partielles et 4 couples non représentés
  ou non rapprochables. Un ordre initial seul n'est pas une simulation MRP complète.
  Les achats pour des usages hors BOM exigent un stock, une route et une politique
  locale documentés ; une sécurité absente reste inconnue.
- **Démarrage** : utiliser stocks et ordres en cours sources. Les matières des OF
  initiaux sont supposées déjà prélevées ; elles ne sont pas consommées deux fois.
  Cette hypothèse n'est pas démontrée pour les emballages : la
  [revue des encours](../artifacts/testing/mrp_scope_reconciliation_20261005/opening_review.md)
  identifie des prélèvements de janvier proches des dates des OF d'Avène.
  Leur séparation par étape de fabrication n'est pas encore implémentée.
- **Sécurité à Muret en 2025** : 20 jours ouvrés pour 268091 et 25 pour 268967,
  conformément au choix utilisateur historique ; 100 % des jours retenus, sans
  coefficient 0,75. Les valeurs plus récentes du classeur restent conservées.
- **Prévisions client absentes** : reprendre une version connue contenant la semaine ;
  à défaut, utiliser le repli documenté sur une période connue. Les prévisions
  2026 présentes dans le fichier client sont conservées, sans leur ajouter 5 %.
- **Révision des besoins industriels composants (correction du 6 octobre)** :
  avec `industrial_forecast_revision_policy=latest_vintage_v1`, utiliser le
  dernier plan connu de l'article/site pour les semaines futures. Ne pas reprendre
  une ancienne semaine absente du nouveau plan : un besoin déplacé risquerait
  d'être acheté deux fois. La semaine en cours conserve la dernière version connue
  avant son début. Une semaine absente reste inconnue : les besoins BOM et le
  repli documenté pour les autres usages restent applicables, sans observation
  fictive de zéro. Cette règle est indépendante des prévisions client. La
  référence C conserve son ancien comportement pour mesurer l'effet.
  Exemple source : les 110 495 UN de 333362 au 16 mars dans le plan du 23 février
  disparaissent de cette semaine et apparaissent au 23 mars dans le plan du
  2 mars. Le bilan source est `400 250 + 124 000 − 110 495 = 413 755` ; conserver
  l'ancien besoin donnerait un bilan faux de 110 495 UN.
  Les essais annuels et leurs limites sont dans le
  [bilan du 6 octobre](../artifacts/testing/mrp_overstock_root_20261006/bilan.md).
  La correction ne résout pas la replanification des achats déjà engagés :
  leurs quantités et dates restent conservées lorsque les propositions de
  fabrication évoluent. Une prévision source élevée puis révisée peut ainsi
  laisser arriver des composants sans fabrication immédiatement à lancer.
  Il faut distinguer cette limite de la sélection erronée d'anciennes versions ;
  le modèle ne connaît pas la date industrielle de départ de chaque commande.
- **Fermeture** : Avène du 4 au 15 août 2025 inclus. Les autres fermetures ne
  sont pas inventées. Le calendrier de fabrication n'est pas automatiquement
  assimilé au calendrier lundi–vendredi des traitements et de la sécurité.
- **Libération PF** : 10 jours ouvrés à Avène pour 268091 ; 15 à Gien pour 268967.
  **Gaillac** : 28 jours pour 693055, 33 pour 773474, après fabrication selon la
  convention retenue. Ces nombres sources ne prouvent pas à eux seuls un statut qualité.
- **Transferts** : 773474, 10 jours de transport puis 6 ouvrés à Gien ; 693055,
  hypothèse de 7 jours de transport puis 7 ouvrés à Avène. La référence achat de
  70 jours pour 693055 n'est pas considérée comme 70 jours de camion.
- **Fabrication** : `tau_process` garde sa signification de planification.
  À Gaillac, la capacité non fournie conserve une convention d'un lot par jour ;
  693055 utilise la matière fictive autorisée, sans prétendre disposer de sa vraie BOM.
- **Usages partagés physiques** : C, K et A conservent les consommations estimées.
  L'essai E utilisant les sorties physiques I est séparé ; il n'est pas adopté globalement.
  Les sorties Scan3 et les quantités de la BOM ne concordent pas encore partout.
- **Objectif d'un an sur la chaîne médicament** : il ne constitue pas une règle
  automatique imposant un an à chaque site. La contrainte globale bout en bout
  n'est pas identifiée ni validée comme un contrôleur distinct dans ce calcul.
- **Hors de cet essai** : pas de tirage de retards fournisseurs, pas de nouveaux
  incidents, pas de recalage du stock sur chaque photo réelle. Les données réelles
  servent à comparer, pas à imposer artificiellement le résultat physique.

## Révision des anciennes règles — essais du 6 octobre

Le nouveau scénario `separate_own_and_other_v1` teste une simplification, sans
remplacer automatiquement la référence C :

```text
besoin composant à la date t = besoin BOM des fabrications prévues à t
                              + prévision des autres usages à t
```

Les identités, dates et quantités de ces deux catégories restent conservées.
Le besoin total du fichier MRP sert à comparer ; un écart entre ce total et
notre BOM ne devient plus automatiquement une consommation supplémentaire.
La variante cumulative antérieure pouvait aussi avancer un besoin matière
sans avancer la fabrication correspondante ; ce déplacement est absent ici.

Cette règle s'applique au périmètre de composants configuré, achats externes
et entrées de transferts internes protégées. Elle ne remplace pas la demande
client ni la nomenclature d'un produit fabriqué au même site. Le taux utilisé
pour convertir les jours de protection en quantité provient des besoins propres
et autres usages sur la fenêtre prévue. Les jours et planchers source restent
inchangés. Retirer une observation MRP, ou fournir une semaine à zéro, ne change
pas ces besoins ni ce taux : le périmètre est configuré indépendamment des observations.

**Les anciennes prévisions des autres usages restent des estimations.** Le
libellé « Pack » n'établit pas qu'un article est réservé à nos produits. Les
sorties physiques documentent par exemple d'autres usages pour 338928 et
730384 ; inversement, les anciennes estimations en attribuent beaucoup trop
à 001848. Le [contrôle de périmètre](../artifacts/testing/mrp_rule_revision_20261006/scope/note.md)
donne les valeurs et la couverture des sources.

Trois essais annuels isolent les effets : **D**, règle simplifiée ; **DE**, D
avec rejeu des autres sorties physiques disponibles ; **DEP**, DE avec
conditionnement des OF initiaux. Le rejeu DE utilise les consommations au jour
d'exécution, sans fournir à la prévision leurs valeurs futures. Une journée
non renseignée conserve le repli estimé ; zéro documenté reste zéro. DEP
conserve l'hypothèse d'emballages encore à prélever sur les OF initiaux d'Avène ;
ce n'est pas une preuve de leur statut industriel.

**Résultat annuel : aucun des trois essais n'est adopté globalement.** D réduit
l'écart des deux emballages suivis par rapport au dernier essai VP, mais
augmente les jours avec manque matière à Avène de 11 à 19 et dégrade le stock
de 773474 à Gien. DE/DEP exposent une prévision manquante : les autres usages
physiques du tube 338928 sont exécutés mais ne sont pas anticipés par son
calendrier conservé. Les [résultats complets et preuves](../artifacts/testing/mrp_rule_revision_20261006/bilan.md)
distinguent baisse d'erreur de stock, ruptures et conformité des calculs.

Les nouvelles commandes restent engagées lorsque les fabrications prévues
reculent. Les sources montrent des reports de quantités entre versions MRP,
mais ne prouvent pas que chaque commande est encore modifiable. Un futur
report doit préserver son identité, sa quantité et sa couverture, distinguer
promesse et départ physique, et ne pas faire passer une réception décalée en
2026 pour un achat économisé. Le [contrat proposé](../artifacts/testing/mrp_rule_revision_20261006/orders/note.md)
est une analyse de faisabilité, pas une règle activée.

## Stock local hors BOM : 001848 à Gien (essais G1/G2)

Un article/site consommé par d'autres produits doit avoir sa propre boucle
d'approvisionnement. L'ajouter au stock et aux sorties sans route d'achat
produit mécaniquement un épuisement : c'était la limite de l'essai N.

La correction utilise les besoins I du dernier plan local connu pour planifier,
et les mouvements physiques à leur date pour consommer. Ces deux calendriers
ne s'additionnent pas. Les achats sont calculés, pas copiés des réceptions H
futures. Le netting tient compte des commandes déjà engagées et de leur date
de disponibilité ; le passage du détenu au disponible n'est pas une nouvelle
entrée physique.

Pour Gien, le multiple de 7 000 kg est une hypothèse fortement soutenue par les
plans. Le délai de l'offre fournisseur est de 56 jours calendaires et le
traitement local de 26 jours ouvrés. **La protection supplémentaire de 26 jours
ouvrés reste une hypothèse non confirmée**, car aucune sécurité locale n'a été
retrouvée. Elle ne devient pas une règle générale ni un paramètre source.

G1 conserve l'encours Extract ; G2 ajoute conditionnellement deux positions
initiales de 7 000 kg du premier plan, antérieures à la première livraison
nouvelle possible. Leur statut engagé et leur fournisseur ne sont pas prouvés.
Les engagements ne sont pas automatiquement annulés ou reportés lorsque les
prévisions diminuent : cela reste une limite à étudier, pas une permission de
réécrire rétrospectivement les commandes.

Voir le [bilan et la recette G1/G2](../artifacts/testing/mrp_gien_supply_20261006/bilan.md).
Les deux stocks Gaillac de N restent sans réapprovisionnement paramétré.

## Étuis et composants partagés : correction B1/B2/B3

G2 conserve les règles d'emballages de C ; il ne contient pas automatiquement
les anciennes variantes V ou D. Les nouveaux essais réunissent le dernier
plan industriel connu et la séparation `besoins BOM + autres usages prévus`,
avec les emballages prélevés lors du conditionnement des encours initiaux
(statut matière hypothétique conservé comme tel).

Pour B2, la prévision d'autres usages devient `part historique connue × I du
dernier plan connu`. Cette part est calculée sur les seules semaines physiques
terminées ; les prévisions restent séparées de la consommation exécutée.
B3 réserve ce remplacement aux couples dont les autres usages ont une
couverture physique source. Ce périmètre est choisi pour l'étude rétrospective,
pas présenté comme une information ERP disponible au 1er janvier.

Les délais, sécurités sources, prix, BOM et quantités initiales sont conservés.
Une baisse de stock obtenue en déplaçant un manque vers un autre composant
ne suffit pas à adopter une variante. Les [bilans, conditions et vérifications](../artifacts/testing/mrp_packaging_audit_20261006/bilan.md)
distinguent notamment le surplus d'achats à Gien et les consommations
d'emballages manquantes à Avène. B2 est écarté : le changement de prévision
sur des consommations encore estimées produit 250 jours de contrainte matière
à Avène. B3 ramène ce chiffre à 35 et améliore les deux étuis, mais améliore
12 stocks annuels et en dégrade 15 ; son adoption globale n'est pas validée.

Pour poursuivre le diagnostic des étuis, utiliser explicitement le graphe B3
et ses limites, en conservant G2 comme témoin. Ne pas repartir implicitement
de C ou G2 puis présenter leurs anciennes règles comme les corrections B3.
Les constantes sources et les fichiers historiques restent conservés.

## Essais des étuis du 6 octobre : règles d'achat explicites

Ces essais concernent **338929 à Avène et 333362 à Gien**, sur 2025. Ce ne
sont pas des paramètres adoptés pour toutes les matières. Les délais, sécurités,
BOM et fichiers industriels restent inchangés. Le [bilan des variantes](../artifacts/testing/mrp_packaging_solutions_20261006/bilan.md)
conserve aussi les essais écartés et leurs conséquences sur la fabrication.

1. **Ne compter qu'une fois le besoin et les engagements.** Dans une semaine
   industrielle renseignée : `besoin = engagé + max(0, I restant − engagé)`.
   La consommation physique reste celle des fabrications exécutées. Le cas des
   semaines omises est une hypothèse de prévision, pas une donnée industrielle
   égale à zéro. Les essais C9/C10 retirant toute prévision BOM dans ces semaines
   sont écartés : ils ne couvrent plus correctement les fabrications du modèle.
2. **Déduire le stock et les réceptions une fois.** Pour chaque besoin daté :
   `achat = plafond_UN(max(0, besoin − stock affecté − réceptions affectées − surplus déjà proposé))`.
   Une affectation ne couvre pas deux besoins. Dans ces essais, le standard FIA
   de 5 000 est non contraignant : la formule n'impose pas un multiple de 5 000.
3. **Anticiper avec les calendriers sources.**
   `date protégée = date de besoin − jours de sécurité ouvrés` ;
   `disponibilité = départ + délai fournisseur calendaire + réception ouvrée`.
   Le plan choisit le dernier dimanche de revue permettant de tenir la date
   protégée. Sans solution à temps, il conserve le retard. La première revue est
   le 5 janvier. Le plancher fixe s'ajoute une seule fois ; les jours de sécurité
   ne deviennent pas une seconde quantité ajoutée après l'anticipation.
4. **Compléter les encours sans créer un deuxième achat.**
   `complément initial = max(0, H du premier plan − engagements déjà représentés)`.
   Le complément devient connu le 5 janvier, pas au 1er janvier. Les 423 027
   étuis ajoutés au carnet d'Avène sont des réceptions supposées déjà engagées,
   jamais de nouveaux achats décidés ce jour-là. Le jour exact et la fermeté
   restent des hypothèses documentées.
5. **Réviser une date sans dupliquer l'ordre.** Pour une promesse explicitement
   supposée encore modifiable, projeter le stock en retirant seulement cette
   promesse, puis placer sa disponibilité au besoin découvert, sans avancer avant
   sa date originale. Un report peut revenir à cette date originale. Quantité,
   fournisseur et identité restent inchangés ; les réceptions exécutées et les
   transports déjà partis ne sont pas modifiés.

Les essais avec report utilisent la couverture du modèle ; elle ne prouve pas
la fermeté réelle des commandes. Une baisse de l'écart moyen accompagnée de
manques supplémentaires en fabrication est un échec, même si le stock PF
permet encore de servir les clients. Voir les [formules et paramètres détaillés](../artifacts/testing/mrp_packaging_solutions_20261006/engine/cinq_regles_effectives.md).

**Variantes C11/C12 testées puis écartées :** conserver tous les besoins engagés
`E` à leur date, affecter leur volume au budget industriel `I` selon une convention
FIFO explicite, puis rapprocher le reliquat `I'` et la prévision révocable BOM `B` :
`R(t) = max(cumul I'(t), cumul B(t))` et `besoin révocable(t) = R(t) − R(t−1)`.
Le besoin total vaut `E + besoin révocable`, avant protection et déduction du
stock/réceptions. Sur l'horizon couvert, le volume final est `max(E+B, I)` ;
aucun besoin BOM n'est retardé. Cette égalité de volumes ne prouve pas l'identité
des ordres industriels. En particulier, affecter I à un engagement plus tardif
ne couvre pas automatiquement la date industrielle antérieure : cet écart est
tracé. Hors horizon connu, le besoin initial est conservé. Les [conditions et
contrôles de cette variante](../artifacts/testing/mrp_packaging_solutions_20261006/engine/cumulative_purchase_envelope.md)
restent distincts de sa performance sur les stocks.

Les neuf calculs annuels sont terminés. C8 reste le meilleur compromis des
deux étuis : écart moyen réduit de 33 % et 59 % face à B3, sans adoption globale.
C11 augmente les écarts ; C12 crée neuf jours de contrainte sur les étuis de
Gien. La réussite des 93 tests ciblés et des bilans CSV ne suffit donc pas à
retenir ces deux variantes. Le [bilan](../artifacts/testing/mrp_packaging_solutions_20261006/bilan.md)
conserve les chiffres, les scénarios exacts et les limites du programme PF.

C8 a ensuite été réexécuté sous le nom C8R avec le moteur final et le même
graphe : achats, réceptions et contraintes identiques ; au plus une unité de
différence sur 11 clôtures de stock de 338929 après réparation des arrondis.
La [comparaison à utiliser](../resultats/mrp_packaging_solutions_20261006/comparaison_corrigee.html)
affiche cette reproduction, pas uniquement un ancien export requalifié.

## Programme de fabrication : pilote local du 6–7 octobre

L'essai part de C8R et ajoute une règle facultative, commune aux processus
sélectionnés de Gien et d'Avène : **avancer une fabrication déjà proposée si les
besoins de composants du plan connu la justifient et si elle est réalisable
aujourd'hui**. Le scénario nominal ne l'active pas automatiquement.

**Après test sur 2025, cet essai n'est pas retenu à la place de C8R.** Il
améliore les deux stocks PF, mais dégrade légèrement les deux étuis et le
semi-fini de Gien. Le progrès du début d'année ne suffit pas sur l'année entière.

```text
budget composant restant = max(0, besoin source de la semaine
                                  − usages déjà exécutés − besoins déjà engagés)
quantité proposée avant = lot avancé + propositions restantes après son crédit
```

Le lot doit être couvert par les budgets, le stock utilisable, la capacité et
les calendriers. Tout OF initial de conditionnement restant bloque l'avance,
car les lignes MRP ne permettent pas de prouver qu'il s'agit d'une autre
fabrication. La campagne est créée au moment du lancement physique ; aucune
promesse préalable ne déclenche des achats avant une éventuelle annulation.
Les libérations, transports, nomenclatures et sécurités existants restent actifs.

Ce pilote est limité à une avance par processus. Un budget d'une matière
partagée ne prouve pas l'identité d'un OF, et aucun taux de perte n'est inventé.
Le [bilan et les comparaisons](../artifacts/testing/mrp_production_programme_20261006/bilan.md)
séparent les progrès du pilote janvier–avril sur les étuis et le PF des
contreparties sur le semi-fini et des dégradations constatées sur l'année.
Les tests de conservation ne certifient pas la calibration industrielle.

## Expédition client : ancienne variante datée expérimentale

Cette variante précède la clarification client du 8 octobre et conserve encore
une couverture physique prévisionnelle. Elle n'est pas la correction
`known_demand_only_v1` décrite en tête de ce document.

Le contrat optionnel `customer_dispatch_forecast_policy` avec le mode
`dated_source_profile_v1` modifie uniquement la couverture physique des
couples explicitement sélectionnés. Il plafonne le signal futur au profil
quotidien source et au reliquat de la semaine ; il ne réécrit ni la prévision
ni sa consommation globale. La politique d'ouverture
`observed_to_date_mean_v1` utilise seulement la demande déjà connue lorsque
la semaine initiale n'a pas de prévision. Elle reste une hypothèse d'essai.

Le [premier essai Cicalfate sur 90 jours](../resultats/cicalfate_correction_20261008/rapport.md)
améliore les stocks mais ajoute trois jours de retard lorsque la demande
dépasse la prévision. Ce résultat interdit de présenter cette variante comme
un nominal validé. Sans activation du contrat, la règle antérieure demeure.

## Correspondance avec le code

Les règles ci-dessus se lisent dans
[mrp_planning.py](../simulation/engine/mrp_planning.py) :
`plan_dated_requirements`, `plan_anticipated_requirements`,
`plan_with_stock_protection`, `plan_sourced_requirements`,
`plan_allocated_purchase_requirements`, `reconcile_industrial_requirements`
et `InternalTransferCommitments`.

Le raccord aux mouvements physiques est dans
[run_first_simulation.py](../simulation/engine/run_first_simulation.py) :
`plan_component_network`, `customer_physical_cover_need`,
`finished_goods_dispatch_need`, `dated_supply_release_calendar`,
`dated_production_release` et la boucle quotidienne.

Les paramètres exacts viennent du [graphe de référence C](../artifacts/testing/customer_comparison_20261005/graph_C.json),
de la [recette d'avancement A et du témoin R](../artifacts/testing/mrp_transfer_advance_20261005/study.py)
et des sources citées dans leurs métadonnées. Les résultats de A doivent être lus
dans [son bilan de qualification](../artifacts/testing/mrp_transfer_advance_20261005/bilan.md) ; une règle correctement calculée ne garantit
pas, à elle seule, la reproduction du comportement industriel.
