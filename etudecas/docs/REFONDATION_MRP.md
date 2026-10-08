# Reconstruire un MRP commun à partir des sources

Revue du 6 octobre, statut clarifié le 7 octobre 2026. Ce document fixe la
conception à éprouver ; il ne déclare pas qu'un nouveau moteur a déjà reproduit
l'année 2025. **C8R est la référence de comparaison conservée ; PGA est non retenu.**
Les références antérieures restent conservées. Le
[registre des règles et la matrice C8R](REGLES_MRP.md) distinguent le scénario
effectivement exécuté, les essais historiques et les conventions non démontrées.

**Préalable Scan3 :** l'exclusivité des sorties J aux seuls PF 268091/268967
n'est plus une confirmation acquise. L'[audit consolidé](../artifacts/testing/audit_perimetre_scan3_20261007.md)
doit guider la correspondance produit/vrac/étape avant de modifier les besoins
ou la BOM. La fermeture d'un bilan matière n'identifie pas son périmètre de
fabrication. Les modes A (besoins industriels connus) et B (chaîne depuis demande
client et BOM) restent deux expériences distinctes.

## Banc local A — protocole figé avant calcul, 7 octobre 2026

L'utilisateur a autorisé la suite après l'audit Scan3. Cette passe identifie le
calcul local à partir des états industriels ; elle ne modifie pas le moteur
physique ni la référence C8R. Les correspondances OF/vrac/PF restent ouvertes.
Le banc réutilise le planificateur pur existant et ses calendriers, sans lancer
la chaîne ni réinitialiser une simulation autonome sur des photos réelles.

**Question principale :** les besoins industriels connus rendent-ils nécessaires
de nouveaux approvisionnements de 049371 alors que les besoins reconstruits de
C8R n'en déclenchent pas ? Les étuis 338929/Avène et 333362/Gien sont des contrôles
sur les achats UN ; 773474/Gien contrôle une route interne, sans simuler la
disponibilité amont de Gaillac. Les quatre couples utilisent le même contrat
de besoin, avec des paramètres d'opération explicitement distincts.

### Entrées et protection contre les doubles comptes

- Une décision correspond à une seule version MRP connue, sur 52 semaines
  glissantes. Les versions 2025 peuvent prévoir 2026. Aucune version ultérieure
  ni photo du lendemain ne renseigne la décision.
- I MRP fournit les besoins locaux ; aucune BOM, sortie Scan3 ou consommation
  observée future n'est ajoutée. Deux hypothèses restent affichées pour I de la
  semaine courante : entièrement restant à servir, ou déjà absorbé/exclu.
  Les autres semaines sont réparties selon la convention dimanche–samedi de
  l'adaptateur, sans prétendre disposer de dates industrielles journalières.
- J courant est disponible ; J futur est un stock déjà présent, libéré plus
  tard. La photo de stock total ne s'ajoute pas à J. Elle sert seulement au
  rapprochement rétrospectif de périmètre.
- Seuls les encours initiaux dont G (arrivée physique prévue) reste postérieur
  à la décision peuvent ajouter une entrée externe, à leur disponibilité I
  source. Un ordre avec G passé et I futur n'est pas ajouté à nouveau au stock
  J : il est classé comme potentiellement déjà sur site. Le maintien des
  promesses initiales aux dates d'origine demeure une hypothèse, sans historique
  des révisions ni des nouvelles commandes de l'année.
- **Aucun H du plan, même courant, ne couvre le calcul prédictif principal.**
  H est une cible descriptive. Sa persistance entre versions ne prouve pas sa
  fermeté. Une réception hebdomadaire ne donne pas le nombre d'ordres.
- Les semaines absentes restent inconnues. Le masque et le préfixe contigu
  renseigné sont exportés. Le calcul sur les seuls besoins documentés est
  conditionnel et incomplet ; les dates après une lacune ne deviennent pas une
  prévision industrielle certifiée. Les scores sont séparés selon la couverture.

### Hypothèse chiffrée avant exécution du planificateur

Oracle direct sur 049371, avec **I courant entièrement restant**, uniquement
les lignes connues et les promesses initiales encore physiquement futures :

| Version MRP | I documenté (kg) | J total déjà détenu (kg) | Promesses initiales futures (kg) | Déficit net documenté (kg) | Avec plancher fixe de 888 kg (kg) |
|---|---:|---:|---:|---:|---:|
| 5 janvier | 23 754,000 | 3 916,930 | 19 800,000 | 37,070 | 925,070 |
| 30 mars | 26 196,000 | 7 021,240 | 10 800,000 | 8 374,760 | 9 262,760 |
| 29 juin | 26 418,050 | 6 480,000 | 0 | 19 938,050 | 20 826,050 |
| 28 septembre | 25 974,000 | 8 958,060 | 0 | 17 015,940 | 17 903,940 |

Formule : `max(0, somme I connue − somme J − promesses initiales retenues)`,
puis calcul séparé avec le plancher fixe. Ce sont des besoins de couverture
conditionnels avant dates et lots, **pas des achats annuels ni la preuve
d'absence de nouvelles commandes ERP**. Le 30 mars, J = 5 221,240 utilisables
+ 1 800 libérés plus tard. Les 26 196 kg du snapshot brut se distinguent des
26 037,429 kg répartis sur les fenêtres utilisées dans C8R.

**Résultat attendu :** un besoin d'approvisionnement positif sur ces données,
malgré la faible demande reconstruite du simulateur. Si ce résultat apparaît,
il montrera une différence de diagnostic local ; le stock J et le carnet sont
également différents de l'état C8R, donc l'effet ne sera pas attribué aux seuls
besoins. Un contrôle de volume à état C8R figé isole ce dernier facteur au
30 mars : stock 12 911,930 + engagements 10 800 = 23 711,930 kg, contre
4 388,275 kg reconstruits ou 26 037,429 kg industriels sur les mêmes fenêtres.
Les déficits sans sécurité ni calendrier sont respectivement zéro et
2 325,499 kg. Cette substitution de volume n'est pas une trajectoire physique.
Elle ne valide ni les dates d'achat ni l'exclusivité Scan3.
Un premier achat peut rester très en retard : la fiche
049371 indique 147 jours calendaires puis 9 jours ouvrés de réception dans les
versions examinées, face aux 8 jours des encours initiaux. Ces derniers gardent
leurs propres dates et leurs lots de 1 800 kg chez VD0518550B ; les achats
nouveaux gardent l'offre VD0520132A et le standard de 1 600 kg, sans assimiler
automatiquement ce standard à une contrainte industrielle prouvée.

### Variantes, comparaison et rejet

Le témoin achat explicite l'anticipation des jours de sécurité **avec addition**
du stock fixe, comme C8R. Une variante change seulement l'opérateur du plancher
fixe en maximum. Les deux cas de I courant sont des hypothèses d'état, pas des
paramètres à choisir après lecture du meilleur score. Quantités, calendrier,
fournisseur, lot et fenêtre de regroupement restent identiques entre opérateurs.
Les deux étuis gardent leur standard non contraignant et leur revue dominicale ;
le lot de fabrication 3 200 kg de 773474 n'est pas imposé à son transfert.

Comparer séparément quantité totale d'un plan, premières nécessités, dates de
commande, arrivée physique, disponibilité, déficits chronologiques, engagements
tardifs et surplus. H est confronté à la fois aux arrivées et aux disponibilités
pour rendre visible sa convention encore ambiguë ; aucune correspondance
individuelle d'ordre n'en est déduite. Le total comparé à H inclut les encours
retenus et les propositions nouvelles ; J n'est pas une arrivée physique.
L'exclusion G ≤ décision suppose l'ordre déjà représenté dans J ; G exactement
à la décision reste ambigu faute d'ordre journalier des événements.
Les semaines renseignées et fenêtres
incomplètes ont des scores séparés ; une tolérance d'une semaine n'est publiée
que si l'appariement conserve les quantités sans double emploi. Aucun outil
conforme n'étant disponible, **seul le score à semaine exacte est exécuté dans
cette passe** ; la tolérance ±1 semaine est marquée non exécutée.

Les 52 versions ne sont **jamais additionnées comme des achats annuels**. Les
résultats sont présentés par article/unité et blocs chronologiques, sans total
kg+UN. Les essais locaux antérieurs restent comparatifs, notamment le banc
Gaillac du 5 octobre et la comparaison additive/MAX déjà peu concluante sur
049371. Cette nouvelle passe teste un contrat plus strict sans H fourni comme
réponse ; elle ne présente pas ces anciens constats comme des découvertes.

Rejeter tout candidat qui utilise H pour prédire H, crédite deux fois J/encours,
perd des besoins courants protégés, viole les calendriers ou les UN entières,
masque les lacunes ou transforme une promesse tardive en achat dupliqué.
Une amélioration locale ne suffit pas à modifier la chaîne : l'adoption exige
ensuite une comparaison physique 2025 contre C8R, avec stocks, consommations,
fabrications, transferts, achats, manques et service. Cette adoption n'est pas
préjugée par le banc A.

## Résultats du banc local A — 7 octobre 2026

Le [comparatif HTML](../resultats/mrp_local_20261007/comparaison.html) présente
**208 états industriels et 832 plans conditionnels** : quatre couples, 52 versions,
deux traitements du besoin courant et deux opérateurs de stock fixe. Aucun des
208 états ne renseigne les 52 semaines intégralement. Les totaux ci-dessous
portent seulement sur les besoins documentés ; ils ne sont ni des achats
annuels, ni des ordres engagés, ni des manques industriels observés.

### 049371 : besoin de couverture confirmé sous le contrat local

| Version | Nouvelles propositions, I courant restant (kg) | I courant exclu (kg) | Semaines renseignées / 52 | Préfixe contigu (semaines) |
|---|---:|---:|---:|---:|
| 5 janvier | 1 600 | 0 | 29 | 5 |
| 30 mars | 9 600 | 9 600 | 30 | 15 |
| 29 juin | 22 400 | 19 200 | 27 | 2 |
| 28 septembre | 19 200 | 16 000 | 29 | 13 |

Ces quantités sont identiques entre addition et maximum sur ces quatre dates,
avec la convention de multiple 1 600 kg reprise de C8R, **non démontrée comme
contrainte d'achat industrielle**. Les dates protégées changent cependant :
au 5 janvier, la première proposition additive est disponible le 22 juillet,
contre le 29 août en maximum. Le choix du seul opérateur de sécurité n'explique
donc pas le défaut de volume des besoins reconstruits par la chaîne.

Au 30 mars, la première proposition nouvelle part le jour de la décision :
arrivée physique le 24 août, disponibilité le 4 septembre, avec 147 jours
calendaires puis 9 ouvrés. Au 29 juin, sa disponibilité la plus tôt est le
4 décembre ; au 28 septembre, le 5 mars 2026. Le dépassement de 2025 est une
projection MRP, sans simulation physique en 2026. Les besoins couverts tardivement
dans les plans de juin et septembre atteignent respectivement 9 852,907 et
7 565,083 kg sous l'hypothèse du courant restant. Ce résultat est conditionnel
au carnet initial seul : les commandes nouvelles réellement engagées depuis
janvier ne sont pas connues. Il ne prouve pas des ruptures industrielles.

Le rapprochement H précise surtout la signification des dates : au 5 janvier,
les 19 800 kg des onze encours correspondent aux semaines de **G physique**
dans H, et non à leurs dates I de disponibilité. Sur le préfixe de cinq semaines,
5 400 kg H sont retrouvés exactement par ces encours connus, sans contribution
d'une nouvelle proposition. Ce rapprochement n'est donc pas une prévision
réussie d'achats nouveaux. Au 30 mars, le préfixe de quinze semaines contient
12 600 kg H ; seuls 7 200 kg correspondent à semaine physique exacte. Les
promesses, replanifications et nouvelles commandes manquantes restent à identifier.

### Contrôles croisés et décision

- **338929/Avène :** stock fixe nul, les deux opérateurs donnent les mêmes
  plans. Au 5 janvier, avec I courant entièrement restant, 423 027 UN sont
  couverts tardivement dans le banc sans complément H (280 573 UN si le courant
  est exclu). C'est le volume du complément de carnet hypothétique déjà
  utilisé dans C8R ; ce rapprochement justifie de rechercher les engagements
  manquants, sans utiliser H comme réponse du calcul prédictif.
- **333362/Gien :** les nouveaux achats restent entiers. L'écart d'une unité
  observé initialement entre addition et maximum au 5 janvier provenait d'un
  défaut numérique, corrigé ci-dessous. Il ne constituait pas un effet métier
  du choix de sécurité. Les deux opérateurs restent des hypothèses à identifier.
- **773474/Gien :** les propositions sont des transferts locaux sous
  disponibilité amont supposée. Le lot de fabrication 3 200 kg n'est pas
  imposé au transport. Ce contrôle ne qualifie ni la production ni le stock
  de Gaillac, dont l'anomalie de bilan demeure ouverte.

### Correction numérique découverte pendant les contrôles

Le premier lancement des sept tests en mémoire donne six réussites et un échec :
un besoin de 10 UN réparti sur sept jours déclenche 11 UN. Le budget de départ
était exact ; la conversion d'un incrément de protection en un seul flottant
arrondi vers le haut le portait à `10 + 1e-16`. L'arrondi physique UN transformait
ce résidu artificiel en achat supplémentaire. La contre-vérification indépendante
retrouve ce surachat de 1 UN dans **316 des 416 plans UN** du premier banc.
Les bilans se fermaient malgré le défaut, l'unité supplémentaire restant en stock.

La correction du seul bloc de publication de `plan_anticipated_requirements`
décompose chaque incrément en fragments datés conservant exactement son budget
décimal. Elle ne retranche aucune demande et ne pose aucun epsilon : 10 exacts
doivent acheter 10 ; un besoin explicitement égal à `10 + 1e-16` doit toujours
acheter 11. La date, le préfixe et l'identité du premier fragment sont conservés.
Le [comparatif numérique](../artifacts/testing/mrp_local_20261007/numeric_comparison.json)
isole le diff de cette passe et les effets par plan. Le premier banc et son
audit refusé sont conservés ; les résultats présentés dans le HTML sont ceux
du calcul corrigé.

Le recalcul retire exactement 1 UN dans les 208 plans 338929 et dans 108 des
208 plans 333362. Les dates et les quantités proposées en kg sont inchangées ;
les seuls écarts kg concernent la précision numérique des indicateurs de retard
protégé, inférieure à 7 × 10⁻¹⁰ dans leurs unités respectives. Les 19 tests
ciblés finalement exécutés réussissent, ainsi que doctor et le gate limité à
ces deux catégories. Ce gate ne qualifie ni une carte en navigateur ni la chaîne.

La revue indépendante conserve **quatre échecs de comparaison strictement
identique entre versions** : sur les quatre modes 338929 du 24 août, le retard
cumulé passe de 3 326 364 à 3 326 363,9999999995 UN·jour. L'écart vaut
5 × 10⁻¹⁰ UN·jour, sans changement de quantité tardive ni de date. Les oracles
arithmétiques, calendaires et de minimum UN passent leurs tolérances fixées
avant contrôle ; ces quatre comparaisons strictes restent néanmoins échouées
dans la preuve. La vérification complète n'est donc pas présentée comme un
succès sans réserve.

**Retenus :** la correction de conservation numérique et le banc reproductible
comme outil de diagnostic. **Aucune modification de politique de chaîne adoptée.** C8R
et ses résultats restent conservés ; aucun nouveau bilan annuel physique
n'est produit dans cette passe. Le test de volume à état C8R figé reste distinct
des plans locaux initialisés par J et le carnet source.

La priorité suivante est de documenter le **carnet d'achats 049371 aux quatre
dates repères**, ses révisions, ses fournisseurs et la validité des conditions
147 jours / 1 600 kg. En parallèle, quelques liens OF–vrac–PF–format et stocks
intermédiaires permettront de départager les périmètres Scan3. Le sens du I
courant et la convention de semaine restent à confirmer. Ensuite seulement,
un candidat pourra être comparé physiquement à C8R sur 2025, avec bilan de toute
la chaîne et critères de service, de retard et de stock.

Les [preuves consolidées](../artifacts/testing/mrp_local_20261007/manifest.json)
référencent le contrat source, l'oracle indépendant, les tests de calcul en
mémoire sélectionnés après relecture et la vérification statique des valeurs
HTML. Le navigateur, l'appariement avec tolérance ±1 semaine et la qualification
CSV d'une nouvelle chaîne ne sont pas exécutés. Les invariants du banc ne
certifient pas la calibration industrielle.

## Audit aval — demande, Muret et expéditions PF, 7 octobre 2026

L'utilisateur demande de vérifier d'abord le début de la chaîne MRP et remet
en question l'interprétation industrielle de l'envoi direct des PF au dépôt.
Cette passe lit les sources et les exports historiques C8R ; **aucun moteur,
paramètre, stock ou résultat C8R n'est modifié**. Le
[manifeste aval](../artifacts/testing/mrp_local_20261007/dc_dispatch_audit_manifest.json)
réunit les preuves et leurs limites.

### Le calcul se conserve, mais la frontière client reste à identifier

Les 730 demandes journalières des deux PF correspondent exactement à
`Flow_Data_Customer_Demand.xlsx!Historique`, après répartition entière des
semaines lundi–dimanche et respect des bornes 2025. Totaux : 4 173 776 UN de
268091 et 1 719 549 UN de 268967. Les 21 jours nuls de 268967 proviennent de
trois zéros explicites, pas d'une donnée absente remplacée par zéro.
Les bilans quotidiens Muret/client/transit ferment exactement. Cela vérifie
les opérations programmées, pas leur adéquation au fonctionnement industriel.

C8R consomme la demande **chez un client agrégé**, deux jours après le départ
de Muret au plus tôt. Après service, il demande un transport couvrant
`backlog + prévision des deux prochains jours − stock client − arrivages
engagés dans la fenêtre`, arrondi aux UN entières. Ce stock client n'est pas
observé dans les classeurs. La sémantique d'« Actual Demand » ne suffit pas à
trancher entre sortie du dépôt, commande à livrer et consommation finale.

Exemple au 1er janvier pour 268091 : demande physique 1 900 UN ; prévision
de la semaine initiale absente, remplacée par une période future déjà connue
de 329 532 UN/semaine (`Projection!A2:E2`). Le tampon transport vaut
`2 × 47 076 = 94 152 UN`. Le départ de Muret atteint donc **96 052 UN**,
et son stock passe de 430 538 à 334 486. Il s'agit d'une anticipation de la
prévision, pas d'un double débit nécessaire pour expliquer le mouvement.
La vieille cible client de 14 jours reste dans des colonnes de diagnostic,
mais n'est pas la cible effective de ce départ.

Sur 2025, le stock client simulé moyen est de **162 956 UN** pour 268091
(maximum 509 304), et de 53 348 UN pour 268967 (maximum 316 572). Pendant
les **17 jours où Muret est vide pour 268091**, les 185 933 UN demandées
sont toutes servies à partir du stock client, sans backlog. Un dépôt vide
dans cette simulation ne prouve donc pas une rupture industrielle.

Diagnostic de frontière, sans déplacer aucun stock : aux 52 photos après
initialisation, le biais Muret de 268091 est −166 392 UN et le stock client
moyen vaut 178 120 UN. Additionner ces deux compartiments annulerait presque
le biais moyen, mais ne ramènerait l'écart absolu moyen que de 254 470 à
243 497 UN. **Ce rapprochement n'est ni un recalage autorisé ni une résolution
des écarts de calendrier.** Pour 268967, ajouter ce stock client aggraverait
l'écart absolu moyen. Les différences n'ont donc pas une cause unique.

### Les 10/15 jours sources ne prouvent pas une attente dans les usines

`Flow_Data_MRP_results.xlsx!Feuille1!D545:E545` indique **1920 / 10 jours**
pour 268091 ; `D593:E593` indique **1920 / 15 jours** pour 268967. Les valeurs
de réception sont portées par la division **Muret**, alors que C8R place cette
attente après fabrication et avant expédition dans les usines.

Des J futurs existent également dans les plans Muret : `J594 = 108 017 UN`
de 268967 libérés au repère du 12 janvier dans la version du 5 janvier ;
`J1502 = 95 130 UN` de 268091 au repère du 19 janvier dans la version du
12 janvier, avec H nul sur ces lignes. Dans le contrat J retenu, il s'agit
de stock déjà détenu disponible plus tard, distinct d'une livraison H.
Ces lignes **ne localisent toutefois pas physiquement ce stock ni son contrôle
qualité**. L'attente à l'usine demeure une hypothèse à réexaminer, et non une
règle industrielle démontrée par E545/E593.

Aux mêmes 52 dates, C8R détient en moyenne 183 250 UN de PF bloqués à Avène
et 80 850 à Gien. Leur affectation à un lieu peut donc fortement déplacer les
courbes locales. Les stockages initiaux usine/client et les transits initiaux
restent insuffisamment observés ; les stocks totaux initiaux Muret sont, eux,
repris des sources.

### Ce que fait réellement C8R pour les expéditions

| Route | Décisions exécutées en 2025 | Quantités par groupe | Cadence et attente après libération |
|---|---:|---:|---|
| Avène → Muret, 268091 | 75 groupes sur 75 jours | 195 à 144 000 UN | 4 327 304 UN expédiées le jour de libération, 237 016 le lendemain, 2 195 après deux jours |
| Gien → Muret, 268967 | 13 groupes sur 13 jours | 107 800 UN chaque fois | Toute la quantité expédiée le jour de libération ; intervalles entre départs de 4 à 67 jours |

Ces groupes sont des identifiants d'expédition **simulés, pas des camions
industriels observés**. La revue effective est quotidienne ; elle ne suit pas
une fréquence hebdomadaire fixe et n'attend pas un camion plein. Les multiples
de 14 400 UN à Avène et 107 800 à Gien proviennent des lots de fabrication ;
le registre historique les atteste comme conventions de départ, sans fournir
une preuve autonome de capacité camion. Un reliquat inférieur au multiple peut
partir séparément : le départ de 195 UN en est un exemple.

Les routes PF utilisent effectivement deux jours calendaires de transport,
issus de l'arrondi de la moyenne hypothétique de 2,5 jours. Les départs ne
sont pas bornés à lundi–vendredi. Les contraintes 33 palettes/23 tonnes et
le regroupement par route/semaine du module logistique sont un
**post-traitement sans rétroaction sur ces départs C8R**. La mutualisation des
deux PF n'est pas une décision de transport exécutée par ce scénario.

### Ce que les sources permettent d'affirmer, et la priorité suivante

Les deux PF ont des photos et mouvements **à Muret uniquement** dans les
classeurs examinés : aucune série de stock PF usine ni journal de départs
usine/réceptions dépôt. H et J sont explicitement nuls sur les 52 semaines
rapprochées ; I contient des soldes signés. Les 25 semaines positives de
268091 et les 18 de 268967 ne sont pas un comptage des réceptions. Les
fréquences et délais des relations usine–dépôt sont vides. Aucun journal de
camions, multiple de palette ou capacité physique PF n'a été identifié.

Les bilans observés comportent aussi des écarts à expliquer : 13 écarts
hebdomadaires compensés pour 268091, et cinq écarts pour 268967 dont le résidu
annuel +13 608 UN déjà ouvert. Leur compensation ne prouve pas une cause de
datation. La première semaine couvre en partie décembre
2024 ; elle n'est pas strictement alignée sur la photo du 1er janvier.

**Priorité : fixer la frontière de demande et les lieux physiques avant de
modifier la règle d'expédition ou les sécurités.** Il faut confirmer le sens
d'Historique et la localisation des PF pendant les 10/15 jours, puis obtenir
un journal de transferts datés avec quantité, origine/destination et numéro
de livraison ; palettes/poids sont nécessaires pour éprouver « camion plein ».
On pourra ensuite identifier cadence fixe, seuil de charge et départ partiel,
séparément des lots de fabrication. Un futur candidat sera comparé sur 2025
avec stocks, réceptions, expéditions et service ; aucune de ces hypothèses
n'est adoptée dans cet audit. Le problème Scan3 des matières reste ouvert.

## Conclusion

**Un noyau de calcul commun ; des paramètres par article/site/route et des
politiques explicites selon le type d'opération.** Une même fonction doit
calculer le manque pour une commande, une fabrication ou un transfert.
La réponse à ce manque dépend de l'opération disponible, pas d'une exception
codée sous le numéro d'un article.

La lecture directe de dix classeurs recense 27 politiques locales, 35 offres
FIA, 24 lignes BOM et 33 couples article/site dans les plans MRP. Les 53 398
bilans successifs de stock projeté sont cohérents à la précision numérique
des sources, avec un résidu maximal de 3 × 10⁻⁸ dans leurs unités respectives.
Cela valide ce contrôle de lecture ; cela n'identifie pas le calcul d'ordres.
La [matrice des sources et cellules](../artifacts/testing/mrp_refoundation_20261006/sources/note.md)
consigne les paramètres, contradictions et informations absentes.

Uniformité ne veut pas dire mêmes délais, mêmes lots, mêmes fournisseurs ou
même sécurité partout. Une référence présente à deux sites a deux positions
de stock et éventuellement deux moyens d'approvisionnement. Gaillac peut
fabriquer, conserver une réserve et expédier : son nom ne définit pas un
algorithme unique pour tous ses articles.

L'objectif réaliste est d'identifier le plus petit ensemble de règles qui
explique les décisions observées et se généralise. Les données agrégées ne
permettent pas toujours de retrouver un paramétrage ERP unique. Nous pouvons
reproduire des quantités hebdomadaires et des comportements sans prétendre
avoir retrouvé les identifiants de toutes les commandes.

## Ce que la reprise de l'analyse change

1. **Le moteur existant n'est plus l'oracle métier.** Une branche de code ou un
   essai qui rapproche une courbe n'est pas une règle industrielle démontrée.
2. **Une seule origine pour chaque besoin.** Le besoin MRP industriel total
   n'est pas ajouté à la BOM des fabrications qui expliquent déjà ce besoin.
3. **Même périmètre prévu et exécuté.** Les usages des autres produits doivent
   avoir une prévision et une consommation identifiées séparément. Il ne suffit
   pas de corriger les sorties physiques : les derniers essais le montrent
   avec les tubes 338928.
4. **Le carnet d'ordres est un état du système.** Les propositions, commandes
   engagées, départs, encours et réceptions ne sont pas interchangeables.
5. **Les sources sont versionnées.** Valeur récente, valeur applicable à 2025
   et choix utilisateur doivent rester distingués. Une date de validité absente
   ne doit pas être inventée.

## Les cinq règles communes proposées

### 1. Former les besoins sans doublon

À la date du calcul, retenir seulement les informations déjà connues. La
projection couvre les 52 semaines suivantes, y compris après le 31 décembre.

```text
besoin du PF = commandes restant à servir + prévision résiduelle
besoin du composant = somme(quantités restant à réaliser par étape × coefficient BOM de l'étape)
                     + prévision distincte des autres usages
besoin du site fournisseur interne = départs prévus vers les sites demandeurs
                                    + autres besoins locaux distincts
```

Les commandes arrivées consomment la prévision selon une période explicite.
La prévision résiduelle tient compte de toutes les commandes déjà prises en
compte, y compris celles déjà servies : servir une commande ne reconstitue
pas la prévision. Le carnet ouvert ne contient que les quantités non servies.
La même semaine est notre convention actuelle, pas une fenêtre ERP déjà
identifiée. Les besoins composants prennent la date de leur étape d'emploi ;
le prélèvement de vrac et le conditionnement peuvent être des étapes différentes.
L'état matière des OF déjà ouverts reste une information distincte.
Les composants déjà incorporés ou prélevés ne figurent plus dans le besoin
restant : la quantité de l'OF ne doit pas être explosée une deuxième fois en entier.

La relecture des 53 398 lignes du fichier MRP ne trouve aucun couple
268091/1810 ou 268967/1430 : les PF sont planifiés dans ce fichier au dépôt
1920. Leurs besoins usine doivent donc être reconstruits depuis le dépôt,
les encours et les mouvements. Ils ne disposent pas ici d'un plan PF usine
indépendant permettant une comparaison directe.

Deux modes de comparaison doivent rester séparés :

- **Identifier le planificateur local** : lui fournir les besoins industriels
  de son périmètre, sans ajouter une BOM représentant les mêmes besoins.
- **Simuler toute la chaîne** : dériver les besoins propres par BOM et prévoir
  les usages hors périmètre. Comparer le total obtenu au MRP industriel.

Une différence entre ces deux modes est un diagnostic de périmètre, de dates
ou de prévision ; elle ne devient pas automatiquement un troisième besoin.

### 2. Calculer une position disponible datée

Pour une date future t, avant la nouvelle proposition :

```text
position(t) = disponible utilisable aujourd'hui
              + réceptions utilisables d'ici t
              + propositions précédentes du même calcul utilisables d'ici t
              − besoins ouverts jusqu'à t
besoin net(t) = max(0, protection(t) − position(t))
```

Les besoins échus non servis sont inclus une seule fois. Une réservation
réduit le disponible ou figure comme besoin ouvert, jamais les deux sans
rapprochement de son identité. Une réception promise après t ne couvre pas
physiquement t ; elle peut justifier une proposition d'avancement plutôt
qu'une deuxième commande. Les quantités non replanifiables conservent leur
date et le risque de retard reste visible.

Le stock physique présent mais non utilisable reste sur son site. Sa
libération future alimente la disponibilité, sans seconde entrée physique.
J du fichier MRP, H et un ordre d'ouverture rapproché ne doivent pas devenir
trois réceptions du même stock.

### 3. Calculer quantité et dates avec la politique déclarée

```text
quantité proposée = règle de lot(besoin net non couvert)
date utilisable visée = échéance protégée
arrivée physique visée = inverse_calendrier_réception(date utilisable visée)
date de commande / départ / lancement = inverse_calendrier_opération(arrivée physique visée)
```

Règle de lot : besoin exact, minimum, multiple obligatoire, plafond par lot ou
regroupement dans une période documentée. Une « quantité standard » ne prouve
pas à elle seule un multiple obligatoire. Le surplus d'un lot couvre les
échéances suivantes. Une quantité hebdomadaire agrégée ne donne pas le nombre
d'ordres individuels. Les UN physiques sont entières ; les calculs prévisionnels
peuvent être fractionnaires.

Exemple : 333362 a un standard FIA de 5 000 UN, mais un engagement initial de
124 000 UN. Pour 730384, la FIA fournit 370 000 m ; les 92 500 m utilisés dans
l'essai sont un choix utilisateur, pas une nouvelle valeur extraite du fichier.
Ces cas interdisent de transformer silencieusement tous les standards en
multiples obligatoires.

Pour un achat, l'opération dépend du fournisseur choisi. Pour une fabrication,
elle dépend des étapes, de la capacité et du calendrier. Pour un transfert,
elle dépend de la route, du départ possible et du traitement à destination.
Un délai achat global et un délai de camion ne s'additionnent pas s'ils
décrivent déjà la même durée de bout en bout.

Les sources ne démontrent pas si le plan industriel tient compte de toute la
capacité future de l'atelier. Ce choix doit être explicite ; la faisabilité
physique reste toujours vérifiée à l'exécution.

### 4. Revoir les propositions et les engagements sans les confondre

À chaque révision : recalculer les propositions modifiables ; rapprocher les
besoins des engagements existants ; proposer avancement, report ou annulation
si une discordance apparaît. **Proposer n'est pas exécuter.** L'acceptation
d'une modification dépend du statut de l'ordre et de la politique fournisseur
ou atelier. Sans information, conserver le statut inconnu et tester les
alternatives comme hypothèses séparées.

Conserver l'identité, le fournisseur, la quantité restante, les quantités déjà
exécutées et l'historique de dates. Ne pas détruire une commande pour la recréer
silencieusement. Reporter une réception à 2026 n'est pas économiser l'achat.

### 5. Exécuter selon l'état physique, puis refermer la boucle

```text
stock physique fin = stock physique début + entrées physiques − sorties physiques
retard fin = retard début + besoins arrivés − quantités réellement servies
```

Une proposition de fabrication n'est exécutable qu'avec composants, capacité
et calendrier compatibles. La production réellement terminée entre dans le
stock détenu puis utilisable selon son traitement. Les PF libérés sont poussés
vers Muret selon les départs possibles, conformément à la consigne métier.
Chaque transfert retire à l'origine, passe en transit, puis entre à destination.

La dynamique des systèmes et la dépendance à l'état restent dans cette boucle :
les décisions dépendent du stock, des commandes, de la capacité et des incidents
du jour ; leurs effets modifient les décisions suivantes. Le planificateur pur
ne remplace pas le moteur physique, les lots, les coûts ou les cascades de risque.

## Ce qui varie réellement entre les opérations

| Opération | Particularité justifiée | Ce qui reste commun |
|---|---|---|
| Client → Muret | Demande indépendante et consommation de prévision ; vérifier si les dates source désignent commande ou expédition | Besoin ouvert, protection, engagements et service |
| Muret → usine PF | Besoin de disponibilité au dépôt ; transport et libération à leur véritable emplacement | Calcul net et conservation des engagements |
| Fabrication PF → composants / semi-finis | Nomenclature, étape de prélèvement, lot et capacité | Besoins datés et disponibilité |
| Fabrication semi-fini → matières | Même mécanisme BOM ; matières absentes explicitement représentées par une hypothèse | Aucun algorithme « Gaillac » particulier |
| Fournisseur → site | Offre, prix, délai, lot, disponibilité ; principal/secours si confirmé | Même manque net et même carnet d'ordres |
| Réserve interne → site demandeur | Départ du stock source, transport, traitement destination ; pas de transformation | Même propagation datée et bilan matière |

693055 fabriqué à Gaillac avec matière fictive autorisée est un cas de données
incomplètes, pas une nouvelle règle MRP. La cible d'environ un an sur la chaîne
du médicament est une éventuelle contrainte de couverture globale exprimée
en équivalent PF, pas un an à chaque nœud. Son contrôleur et son périmètre
restent à identifier. Les stocks hors nomenclature ne peuvent pas être
additionnés à ce total sans facteur de conversion justifié.

## Sécurité : un point à réidentifier, pas à régler à la main

Les jours de sécurité et les traitements utilisent lundi–vendredi selon les
confirmations utilisateur. Le délai fournisseur reste déterministe. Les jours
sources restent conservés, avec les choix explicites de 20/25 jours au dépôt
pour la comparaison 2025. `tau_process` reste une convention de planification.

Quatre politiques locales ont à la fois jours et quantité fixe : 333362,
730384, 049371 et 708073. Le classeur ne dit pas si ces protections s'ajoutent
ou sont prises au maximum. Deux hypothèses doivent être confrontées aux
décisions source, avec les mêmes paramètres :

```text
anticipation + stock fixe : protection(t) = stock fixe + besoins de la fenêtre protégée
plancher de couverture :    protection(t) = max(stock fixe, besoins de cette fenêtre)
```

Sur un même axe de jours ouvrés et avec les mêmes bornes, décaler les besoins
dans le calcul revient à imposer le premier plancher sur la position calculée
aux dates d'usage originales. Les besoins anticipés devenus échus ne doivent
pas disparaître à l'ouverture. Il ne faut pas ajouter à nouveau le même
tampon aux besoins déjà décalés. Les dates physiques de consommation restent
inchangées.

Un [oracle mathématique indépendant](../artifacts/testing/mrp_refoundation_20261006/safety_equivalence.json)
vérifie cette équivalence sur 7 320 cas en mémoire. Il ne démontre pas la
politique industrielle. Il compare des déficits projetés sur les mêmes
entrées ; il ne prouve pas à lui seul l'équivalence de boucles complètes avec
lotissement, revues espacées et replanifications. La position est utilisable
et projetée, pas une photo de stock physique total.
Exemple fictif : position150, stock fixe100,
besoins protégés120 donnent un manque70 avec addition, zéro avec maximum.
Ce choix peut donc expliquer de vraies différences de commandes et doit être
évalué sur les quatre articles, pas fixé selon le nom du site.

## Comment retrouver les règles sans valider artificiellement le modèle

**Étape A — fiabiliser la lecture.** Vérifier unités, dates de versions et
périodes, bilans H/I/J/K et stocks/mouvements, périmètre propre/partagé,
ordres initiaux et politiques. Une donnée absente reste inconnue. Les soldes
ne déterminent pas tous les flux bruts manquants.

**Étape B — identifier les décisions locales.** Pour plusieurs snapshots,
placer le candidat devant le même état et les mêmes besoins connus que le
MRP industriel. Prédire les propositions, puis les comparer aux réceptions
prévues et à leurs révisions. Ne jamais lui donner les mêmes lignes H comme
engagements puis prétendre qu'il les a prédites. Les engagements prouvés par
Extract_En_cours sont distincts ; les états ambigus sont évalués par hypothèses.

**Étape C — généraliser.** Éprouver chaque famille de règle sur plusieurs
articles, sites, délais et périodes. Définir avant la sélection des familles
non utilisées pour régler la règle. Puis geler les choix pour une validation
chronologique ; une révision d'octobre ne renseigne pas une décision de mars.
Les variations de sécurité, lots et source de besoin sont testées séparément.
Toute l'année 2025 ayant déjà été explorée, ce découpage reste une validation
rétrospective : il ne remplace pas une future validation sur des réalisations
industrielles encore inédites. Les prévisions 2026 ne sont pas des réalisations
2026 permettant cette validation.

**Étape D — simulation autonome 365 jours.** Partir des stocks et encours
initiaux puis laisser vivre la chaîne sans recaler chaque semaine les stocks
sur les observations. Conserver les prévisions dans leur version connue.
Un rejeu des autres usages réels est un diagnostic distinct d'une prévision
autonome des autres usages. Comparer également les deux chaînes complètes.

Mesures : volumes d'entrée/sortie, chronologie des réceptions, erreur de stock,
biais, jours de manque avec besoin effectif, retards, production, service,
achats engagés et engagements au-delà du 31 décembre. Rapporter la comparaison
à semaine exacte et avec tolérance d'une semaine, sans déplacer la courbe
réelle a posteriori. Les quantités appariées ne sont consommées qu'une fois
dans le rapprochement ; le reliquat reste une erreur. Aucun score ne mélange
kg, mètres et unités sans normalisation explicitée.

Le passage A→B ne certifie pas D : fermer les bilans du fichier prouve sa
lecture, pas que le simulateur retrouve la décision qui les a produits.

## Architecture cible et ordre de remplacement

Cinq responsabilités suffisent, en réutilisant les composants actuels :

1. **Données métier compilées** : article/site, route, BOM, unité, calendrier,
   politique effective, version connue, cellule source, statut confirmé/inféré.
2. **Besoins versionnés** : client, dépendants BOM, autres usages, identité et
   date. Un seul contrat, pas plusieurs compléments concurrents.
3. **Planificateur pur** : position, protection, lots, dates, choix d'opération,
   propositions et motifs. Aucun mouvement de stock directement écrit ici.
4. **Exécution et carnet** : états d'ordres, stocks, capacité, lots, incidents,
   coûts et mouvements conservatifs. Le modèle dynamique reste ici.
5. **Pilotage et restitution** : boucle temporelle, comparaison, journal et
   formats compatibles avec les cartes et les deux suivis de lots.

Ce sont des frontières logiques, pas cinq dossiers supplémentaires à créer.
Chaque plan porte un identifiant de snapshot, l'instant du calcul et la
version des données connues. La première substitution conserve les phases
quotidiennes actuelles, notamment les décisions avant/après expédition et
le plan préparant la fabrication suivante. Une modification de ces phases
sera ensuite une décision métier testée séparément, pas un effet caché du rangement.
Les comparaisons et exports peuvent rester hors du calcul physique quotidien.
La cible est de regrouper ou réutiliser, puis retirer les branches remplacées
après preuve d'équivalence ou correction justifiée. Une configuration d'étude
reste une donnée ; elle ne devient pas un nouvel algorithme par référence.

Premier chantier : table des politiques effectives et contrats de besoins,
puis banc de décisions locales sur achats/partagés et transferts. Ensuite
substituer le planificateur derrière le moteur physique conservé. Les cartes,
lots, événements et risques ne doivent pas être réécrits pour tester le MRP.
Une livraison comportera le plan exact « besoin → couverture → règle → ordre »
avant sa validation annuelle. Les dernières variantes non retenues ne servent
pas de nouvelle référence nominale.

## Préalable : les stocks sont définis par article et par site

Un site physique reste un seul site dans le réseau. Son stock est identifié
par le couple `(node_id, item_id)` : **001848 · Gien (M-1430)** et
**001848 · Avène (M-1810)** sont deux stocks distincts, avec leurs propres
quantités, usages et engagements. La présence d'une courbe ou de 365 lignes
dans un export ne prouve pas que ce stock est réellement planifié.

L'audit du 6 octobre a identifié trois stocks avec des usages documentés mais
sans état initial dans le graphe C : 001848 à Gien, 001893 et 002612 à Gaillac.
Leurs usages ne sont pas reliés aux deux BOM fournies ; leur affectation
industrielle reste à documenter. Ils ne doivent pas être ajoutés arbitrairement
à la nomenclature des deux produits finis étudiés.

Le contrat `managed_inventory_pairs` permet de déclarer ces stocks physiques
séparément des composants BOM. Le premier raccordement exécute leurs usages
externes documentés, dans la limite du stock disponible, et conserve les
engagements initiaux. Il ne transforme pas les réceptions futures observées
en commandes simulées. Les usages observés deviennent connus le jour de leur
exécution ; ils ne constituent pas des prévisions de demande.

Le statut `supply_status: unconfigured` signifie que l'approvisionnement
automatique n'est pas encore paramétré. Aucun délai d'un jour, stock de sécurité
nul ou fournisseur d'un autre site n'est déduit par défaut. Ces couples restent
des **simulations partielles**, même avec 365 clôtures de stock. Leur épuisement
ne constitue pas une prédiction industrielle de rupture : il signale notamment
l'absence de renouvellement automatique dans ce périmètre incomplet.

Les disponibilités initiales inconnues et les mouvements « Divers » non
représentés doivent rester explicites. Pour 001848 à Gien, les 7 000 kg du
stock initial rendus disponibles plus tard et la commande initiale de
7 000 kg sont deux quantités distinctes. La ventilation disponible/indisponible
du premier plan du 5 janvier est une hypothèse de reconstruction de l'ouverture,
pas une information attestée connue le 1er janvier.

007923 à Gien est un autre cas : un reliquat suivi d'une sortie « Divers »,
sans besoin de réapprovisionnement identifié. 029313 à Gien n'a pas de stock
ni de mouvement documenté permettant de créer un état physique. Ces situations
ne justifient ni une nouvelle BOM ni un stock initial arbitraire.

## Essai de démarrage Cicalfate du 8 octobre 2026

Une variante optionnelle `customer_dispatch_forecast_policy` limite les
expéditions physiques au profil prévisionnel daté connu, sans concentrer le
reliquat sur la fin de semaine. Pour la semaine initiale sans prévision,
elle utilise uniquement la moyenne des demandes déjà connues. La consommation
prévisionnelle du MRP global reste inchangée. Le périmètre essayé est
`(C-XXXXX, item:268091)` ; C8R reste conservé comme référence.

Sur 90 jours, l'écart moyen aux stocks Muret baisse de 28 %, mais trois jours
supplémentaires de retard client apparaissent du 14 au 16 mars, après
épuisement d'une prévision inférieure à la demande. Cette variante n'est donc
pas promue en nominal. Le [rapport et les courbes](../resultats/cicalfate_correction_20261008/rapport.md)
présentent ce compromis et les preuves. La couverture d'une demande supérieure
à la prévision et le pipeline usine–Muret initial restent les priorités.

## Références ERP et portée

L'ERP de l'industriel n'est pas identifié. Les documents SAP ci-dessous servent
à vérifier la cohérence des familles de mécanismes, pas à attribuer au client
une transaction, un paramétrage ou une stratégie SAP particulière.

- La [procédure MRP SAP](https://help.sap.com/docs/SAP_S4HANA_ON-PREMISE/fe39e10a9a864a8f8dc9537704f0fa13/d5aace5314894208e10000000a174cb4.html)
  combine calcul net, taille de lot, dates et explosion de nomenclature, avec
  une politique de lot paramétrée par article.
- La [sécurité en temps](https://help.sap.com/docs/SAP_ERP_SPV/85d3fce10e264972a0155c8b46ecf93b/8aaace5314894208e10000000a174cb4.html)
  avance la couverture en jours ouvrés tout en conservant la date réelle du
  besoin. La documentation la distingue d'un tampon en quantité.
- Le [contrôle de replanification](https://help.sap.com/docs/SUPPORT_CONTENT/mrp/3138697863.html)
  recherche une couverture par un engagement existant et peut proposer son
  avancement ou son report. Ce message ne prouve pas une modification exécutée.
- Les [modes de consommation des prévisions](https://help.sap.com/docs/SAP_ERP/74c0b3a391174482a66a3a23bb28c10d/5a23bf53d25ab64ce10000000a174cb4.html?locale=en-US)
  utilisent des fenêtres et directions configurées ; notre rapprochement par
  semaine est une convention à vérifier.

Les preuves de cette revue sont regroupées dans
[mrp_refoundation_20261006](../artifacts/testing/mrp_refoundation_20261006/).
Cette passe est une analyse de refondation avec contrôles en lecture seule et
calculs en mémoire. Elle n'a ni remplacé le moteur nominal ni lancé une nouvelle
simulation annuelle. Les chiffres de comparaison C/D/DE/DEP appartiennent à
la passe précédente et restent identifiés comme tels.
