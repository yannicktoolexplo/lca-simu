# Rapprochement général du MRP et des flux en 2025

La référence qualifiée d’octobre donne un bilan descriptif sur l’année
civile. Les essais de novembre partagent un graphe et un profil d’usages
concurrents sur **152 jours du 1er janvier au 1er juin**. Sur cette fenêtre,
le contrôle, la réduction prudente des ordres figés et la variante avec
engagements avancés et autorisation d’atelier sont comparés sur les mêmes
données. La dernière variante reprend les décisions déjà testées au
7 mai, puis prolonge le calcul jusqu’au 1er juin sans ajuster leurs dates,
quantités et durées. La période au-delà du 7 mai vérifie les effets de bord
de l’essai d’atelier. Fin mai avait déjà servi au diagnostic de la règle
de réduction des ordres non commencés.
[Protocole](../../artifacts/testing/generalisation_mrp_2025_20261120/protocol.json)

Les photos de stock physique du lundi correspondent à la clôture simulée
du dimanche. Le relevé du 2 juin est présenté à part, face à la clôture
du 1er juin. Les semaines de mouvement complètes vont du lundi au dimanche.
Les comparaisons portent sur les dates et couples article-site observés,
avec conversion des unités sources. Pour agréger les erreurs de stock,
l’erreur absolue moyenne de chaque couple est divisée par son stock moyen
observé, puis les ratios sont moyennés entre couples. Les volumes en kg,
mètres et unités ne sont jamais additionnés entre eux.

À D1920, les mouvements signés se comparent à la variation nette de stock.
Le service quotidien simulé est rapproché de la demande chargée. La
livraison réelle en unités est inconnue, ainsi que le stock utilisable
industriel. Les étuis donnent un indicateur de prélèvement et un proxy
d’achèvement. Le MRP se compare par version connue et date de besoin ou
de disponibilité projetée. Les données d’achat et d’en-cours sont prévues
et agrégées, avec une couverture séparée des exécutions.

## Résultats sur les mêmes 152 jours

| Mesure | Témoin avec réduction des lots | Engagements et autorisation | Couverture |
| --- | ---: | ---: | --- |
| Erreur de stock physique par couple, en moyenne normalisée | 30,77 % | 29,91 % | 630 relevés, 30 couples |
| Erreur de stock physique de 268967 à D1920 | 60 845 UN | 32 873 UN | 21 relevés |
| Erreur hebdomadaire de retraits d’étuis de 268967 | 26 600 UN | 20 612 UN | 13 semaines |
| Écart entre achèvements simulés de 268967 et estimation par les étuis | 26 600 UN | 27 251 UN | 13 semaines |
| Erreur de stock physique de 268091 à D1920 | 277 106 UN | 277 106 UN | 21 relevés |
| Erreur relative médiane des besoins planifiés | 22,10 % | 21,15 % | 5 868 positions MRP, 30 couples |
| Erreur relative médiane du stock projeté | 43,12 % | 44,53 % | mêmes positions MRP |

Le stock physique se rapproche sur **6 couples**, reste égal sur **21**
et se dégrade sur **3**. À 1430, l’écart de stock des étuis 333362 passe de
114 338 à 64 346 unités, et celui de l’emballage 730384 de 37 003 à
27 458 mètres. Celui du semi-fini 773474 se dégrade de 5 072 à 5 844 kg.
Les stocks de 693055 à D1450 et à 1810 sont inchangés. Les prélèvements
se rapprochent sur 6 couples et se dégradent sur 2. Pour les entrées
physiques comparables, 25 couples sont inchangés et 2 se dégradent.
[Rapprochement de tous les flux couverts](../../artifacts/testing/generalisation_mrp_2025_20261120/physical_comparison.json)

Les deux simulations terminent **215 600 unités de 268967** sur la
fenêtre. La variante avance une partie du travail vers mars et avril.
Sur les semaines documentées, les retraits simulés passent de 107 800 à
215 600 pour 402 500 observés. Sur les deux semaines documentées après
le 7 mai, l’erreur hebdomadaire se dégrade de 25 025 à 53 375 étuis.
La variante explique mieux les prélèvements du début d’année. La
concentration et les dates de fin de lot restent à améliorer.

Les journaux du prolongement concordent avec l’essai de 127 jours sur
leur période commune, avec des mentions de provenance distinctes pour
le profil prolongé. Sur 152 jours, les deux produits gardent les mêmes
livraisons simulées chaque jour, 623 081 unités pour 268967 et
1 419 969 pour 268091. Le stock disponible à D1920 amortit les décalages.
[Contre-validation du prolongement](../../artifacts/testing/generalisation_mrp_2025_20261120/validator/generalisation_review.json)

À quatre semaines, les erreurs MRP de besoin et de stock projeté
s’améliorent légèrement sur l’ensemble des couples, de 31,34 à 30,01 %
et de 46,12 à 45,52 %. À D1920, l’erreur de stock projeté à quatre
semaines de 268967 passe en revanche de 78 458 à 94 260 unités. Le taux
de révision du programme simulé passe de 53,20 à 53,33 % pour 268967
et reste à 64,22 % pour 268091. Les versions industrielles agrègent des
quantités, sans identifiants d’ordres exploitables pour un taux analogue.
L’ouverture des cas couvre 88 des 104 positions de la source, dont 68
dans le pipeline et 20 en conditionnement. Certaines séries de besoins
du MRP sont déjà prises comme entrées du modèle.
[Comparaison du MRP et de l’ouverture](../../artifacts/testing/generalisation_mrp_2025_20261120/planning/planning_comparison.json)

## Repère annuel descriptif

La référence d’octobre se compare à **1 563 relevés de stock** sur
**31 couples** et **1 296 mouvements nets** sur semaines complètes.
L’erreur moyenne normalisée des stocks est de **34,95 %**. Les écarts
moyens à D1920 sur 52 relevés sont **160 323 unités pour 268967** et
**289 191 pour 268091**. Sur les semaines documentées, les retraits
d’étuis simulés sont respectivement inférieurs de **26,45 %** et de
**15,00 %**. La demande de 268091 sur les 51 semaines complètes vaut
3 563 142 unités dans cette référence, face à 4 145 843 dans le classeur
historique. Cet écart de périmètre de demande affecte l’interprétation
des stocks et du service annuels. Le rapprochement des demandes
publiées sur la fenêtre récente est un contrôle d’entrée.

La progression est nette pour le 268967 à D1920 et plusieurs composants.
Le gain global de stock est modeste. Les écarts du MRP de stock, les
entrées à l’usine et le profil de 268967 en mai restent sensibles. La
généralisation utile consiste à conserver le lien entre engagement et
achat, puis à vérifier l’autorisation, la durée et la libération aux
dates opérationnelles. Les résultats laissent ouverte la couverture des
ordres de 268091 et l’origine des apports supplémentaires de 268967.
[Courbes interactives](../../resultats/comparaison_generale_mrp_2025_20261120.html)

## Écart prioritaire pour 268091

Du 12 mai au 1er juin, les 732 180 unités achevées en simulation
comprennent une position d’ouverture de 141 780 unités et **590 400
unités issues de 18 nouveaux ordres**. Les prélèvements observés d’étuis
représentent 268 600 unités sur ces trois semaines. Onze des nouveaux
ordres sont figés le **29 avril** pour le **26 mai** et totalisent
345 600 unités. Le 2 juin, le relevé physique de D1920 vaut **976 157**
unités, face à **2 211 304** à la clôture simulée du 1er juin. Il faut
remonter les besoins nets déjà couverts et le regroupement des dates
avant le gel du 29 avril. Le journal situe la concentration dans le
programme simulé et laisse ouverte sa cause métier.
[Ordres simulés de fin mai](../../artifacts/testing/generalisation_mrp_2025_20261120/may_268091_orders.json)

## Test d’une règle commune sur mai–décembre

Pour chaque semaine, le test retient la dernière version MRP commune
publiée à temps pour le gel usine. Il cherche deux retraits planifiés
d’emballage positifs et concordants à une unité près après conversion par
la nomenclature. Sur les semaines où les deux prévisions concordent et
le retrait d’étuis est renseigné, **sept des neuf** semaines de 268967 et
**sept des huit** de 268091 ont un retrait positif. Les autres ont un zéro
observé. Une nouvelle concordance à la veille de la semaine ne conserve
qu’un des sept cas positifs de 268967 et garde ses deux zéros. Pour 268091,
elle conserve cinq des sept cas positifs et filtre son zéro.

La concordance des composants peut signaler un besoin à examiner avant
le gel. La règle de lancement automatique par cette seule concordance
échoue sur les deux produits. Une autorisation d’atelier exige une
information indépendante sur l’ordre et le kit réellement disponible.
[Test des versions MRP](../../artifacts/testing/generalisation_mrp_2025_20261120/rule_signal_holdout.json)

Quatre tests ciblés, la qualification du run de 152 jours et le
rapprochement des empreintes passent. L’oracle indépendant exécute
6 420 contrôles. La page autonome a été ouverte dans Chromium hors
ligne, avec sélection des fenêtres et des couples, clic, navigation
au clavier et vérification sur écran étroit. Les 28 combinaisons
contrôlées affichent les quantités du jeu utilisé.
[Manifeste des preuves](../../artifacts/testing/generalisation_mrp_2025_20261120/final_manifest.json)
