# Trois contrôles prioritaires sur les écarts de 2025

Le contrôle de la demande annuelle explique l’écart de source.
Le test de répartition des lancements localise la limite du MRP à
couverture inchangée. Les relevés de D1920 permettent de quantifier
les apports minimums et de préparer les extractions d’exécution.
[Protocole](../../artifacts/testing/priorites_mrp_20261121/protocol.json)

## 268091 à D1810, le test de répartition après le gel

Les plans de clôture du 27 janvier et du 28 avril ont été reconstruits
à partir du dernier état connu, des engagements datés, des prévisions
publiées et de la sécurité du dépôt. Les 275 propositions natives
gardent leurs identités, leurs quantités et leurs besoins d’origine.
Les dates de lancement de la fenêtre testée concordent avec le journal.
Les 14 dates touchées plus tard par la fermeture d’août proviennent
du journal qualifié.

La règle candidate déplace un lot entier seulement si le manque
projeté ne s’aggrave à aucune date du plan. Les dates et quantités
des engagements existants, le gel de quatre semaines et la sécurité
sont conservés. Chaque lot est essayé aux jours ouvrés des sept jours
suivants. Aucun plafond de production ne limite les placements.

| Revue du plan | Premier jour hors gel | Lots regroupés | Reports admissibles | Couverture datée à ajouter pour reporter le plus petit lot au jour ouvré suivant |
| --- | --- | ---: | ---: | ---: |
| 27 janvier | 24 février | 8 lots, 259 200 unités | 0 sur 40 | 28 800 unités |
| 28 avril | 26 mai | 11 lots, 345 600 unités | 0 sur 55 | 19 402 unités |

En février, la projection usine porte déjà un manque à la première
date de disponibilité prévue. En mai, elle ne garde que 9 398 unités
de marge ce jour-là, face à un plus petit lot de 28 800. Retarder
plusieurs lots ne peut qu’accentuer ce manque, toute autre date fixe.
Les chiffres ci-dessus mesurent la couverture **du plan**. Les essais
historiques montrent que le stock de D1920 peut encore absorber une
partie du déplacement physique.

La règle simple échoue sur les deux épisodes. La question à traiter se
situe avant le gel. Il faut établir quels besoins du dépôt sont déjà
couverts à la bonne date par le stock utilisable, les transferts et les
engagements fermes, en comptant une seule fois chaque quantité entre
les deux sites.
[Rejeu et 95 variantes de dates](../../artifacts/testing/priorites_mrp_20261121/schedule_guard.json)

## Demande annuelle, écart réconcilié semaine par semaine

Sur les 51 semaines complètes, du 6 janvier au 28 décembre, chaque
ligne quotidienne de l’archive d’octobre correspond à l’ancien
classeur de demande. Le nouveau classeur distingue le feuillet
Historique et les versions prévisionnelles. Le delta se forme en
entrée du modèle, avant le calcul de stock et de livraison.

| Article | Ancienne archive | Historique industriel | Différence archive − historique | Semaines différentes |
| --- | ---: | ---: | ---: | ---: |
| 268091 | 3 563 142 | 4 145 843 | −582 701 | 36 sur 51 |
| 268967 | 1 688 810 | 1 691 923 | −3 113 | 3 sur 51 |

Pour 268091, l’écart représente −157 910 unités au premier semestre et
−424 791 au second. Le plus grand écart est le 15 septembre, avec
70 961 dans l’archive face à 213 014 dans l’historique. L’archive
rebascule en scénario synthétique le 29 décembre. Ce fragment reste
hors du score des semaines complètes.

Le chargement du **nominal actuel** retrouve l’historique sur les
102 semaines-produit et les 1 352 lignes de prévision du classeur. La
comparaison annuelle historique conserve donc sa portée d’archive.
Le candidat de 152 jours charge les mêmes tables. Dans ce candidat,
la demande de la dernière semaine est révélée le 2 juin. Au 1er juin,
77 899 unités de 268091 sont encore en attente de publication et la
demande de 268967 sur cette dernière semaine est explicitement nulle.
Pour comparer les deux calculs, il faut raccorder les dates de
publication et les semaines auxquelles la demande se rapporte.
[Rapprochement des 102 semaines](../../artifacts/testing/priorites_mrp_20261121/annual_demand_reconciled.json) · [Tableau hebdomadaire](../../artifacts/testing/priorites_mrp_20261121/demande_2025_hebdomadaire.csv)

## 268967, apports et nomenclature à vérifier

Entre le 17 mars et le 27 avril, quatre hausses de stock imposent
ensemble au moins **112 695 unités d’apports à D1920**, soit 4 895 de
plus que le lot simulé de 107 800, quel que soit son fractionnement.
Cette borne ne requiert aucune hypothèse de service. Le plan du
27 avril contient deux échéances de disponibilité à D1920, avec
65 394 unités au 18 mai et 54 432 au 1er juin. Ce sont des quantités
physiquement présentes et datées au plan. Leur progression ne permet
pas de compter les réceptions ou les lots.

Le composant **344135** est dans la nomenclature utilisée par le
simulateur au printemps. À D1430, ses 553 lignes MRP commencent le
**7 septembre**, et ses deux mouvements et trois photos datent de
décembre. Les exports disponibles ne datent pas sa première utilisation.
La référence de remplacement et son stock initial restent des
hypothèses. Il faut récupérer la **version de nomenclature effective**
pour évaluer le manque de ce composant au printemps.

**Extraction industrielle pour 268967.** Fenêtre du 17 mars au 27 avril,
de D1430 1430 à D1920 1920. Relier par identifiants OF et lot la
nomenclature effective, les composants utilisés, la quantité achevée et
sa date, les départs et réceptions par tranche, les dates et quantités
libérées après contrôle. Inclure les produits déjà achevés avant le
17 mars qui ont ensuite été transférés et les autres apports. Les
identifiants anonymisés stables suffisent. Les exports disponibles
fournissent des semaines, des quantités et des plans agrégés.
[Contrôles sur les classeurs](../../artifacts/testing/priorites_mrp_20261121/operational_extracts.json)

## Clients, huit semaines-produit d’octobre comparées

Pour 268091 le 13 octobre, il y a 72 428 unités demandées et une baisse
de stock de 1 370, dont 435 d’ajustement et 935 de mouvement net. Un
départ de 935 sans réception et un départ de 72 428 avec 71 493 reçues
satisfont tous deux ce bilan. La part de CA livré vaut 98,718 %. Pour
268967 le 20 octobre, le mouvement net est positif et la part financière
livrée vaut 83,774 %. Les résidus du bilan des photos des 13 et 20 octobre
s’annulent sur deux semaines, sans isoler les départs par client.

**Extraction industrielle pour les clients.** Les deux PF à D1920,
avec échéance initiale, départ, livraison ou annulation du 6 octobre
au 2 novembre. Garder les événements de ces lignes au moins
jusqu’au 16 novembre. Exporter une clé commande-ligne pseudonymisée,
les quantités demandées, les dates promises initiales et révisées,
les départs et réceptions réels par partiel, les annulations, les
retours, les soldes et les motifs. Ajouter le lien vers les écritures
de CA si disponible. La mesure client pourra alors compter les unités
reçues à l’échéance initiale, les livraisons tardives et les pertes
définitives séparément.
[Vérification des huit cas](../../artifacts/testing/priorites_mrp_20261121/operational_extracts.json) · [Explorateur D1920](../../resultats/remontee_D1920_reel_20261119.html)

Le travail réutilise des simulations qualifiées existantes. Les
dates candidates et le chargement du nominal ont été éprouvés en
mémoire. Un calcul indépendant a retrouvé les 275 propositions et les
95 verdicts à partir des prévisions et engagements archivés. Les deux
extractions restent à produire dans les journaux opérationnels.
[Contrôle indépendant du gel](../../artifacts/testing/priorites_mrp_20261121/validation/freeze_independent.json)
[Manifeste](../../artifacts/testing/priorites_mrp_20261121/final_manifest.json)
