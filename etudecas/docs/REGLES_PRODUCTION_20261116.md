# Lancements de fabrication et fiabilité des preuves : 16 novembre 2026

Cette étude prolonge les [essais sur le carnet initial](BUDGETS_ET_CARNET_INITIAL_20261116.md).
Elle distingue une erreur du logiciel, des conventions de lancement encore
hypothétiques et les écarts aux observations industrielles. Les paramètres de
la référence ne sont pas recalibrés par produit.

## Erreur démontrée : perte de liaisons dans le réseau

Lors de la construction des calendriers fournisseurs, une variable locale
remplaçait la liste complète des liaisons par les seules liaisons du dernier
article examiné. L'ordre de parcours d'un ensemble pouvait changer ce dernier
article. Deux exécutions autrement identiques exportaient donc respectivement
trois et deux lignes du catalogue fournisseur, pour des fournisseurs différents.
Les autres résultats physiques comparés étaient identiques ; cela ne rendait
pas le catalogue correct.

La correction conserve la liste complète et utilise une variable distincte
pour les liaisons de l'article. Un exemple en mémoire exécute le vrai bloc de
code puis la vraie propagation : un besoin de 17 produits au dépôt doit encore
remonter à l'usine après la construction des calendriers. Le défaut ancien
perd ce lien ; la correction conserve les quatre liaisons de l'exemple dans
les deux ordres de parcours. Aucun fichier n'est altéré pour produire ce
contre-exemple.

Les preuves du premier témoin et de son **refus** restent conservées. Le nouveau
témoin retrouve les **36 liaisons fournisseurs** attendues. Ses ordres, plans
hebdomadaires, stocks, fabrications, livraisons, coûts opérationnels et allocations
matière sont identiques au calcul conservé. Quarante-neuf CSV sont identiques
octet pour octet ; le registre d'événements ne change que par sa provenance
corrigée. Le catalogue est volontairement différent, car auparavant incomplet.

Deux tableaux de diagnostic MRP changent aussi : 24 champs de trace et deux
champs de taux cible retrouvent la propagation du besoin dans le réseau.
Leur évolution est rapprochée des signaux et formules, sans déclarer tous les
CSV identiques. Le contrôle strict initial reste refusé ; une
[contre-vérification bornée](../artifacts/testing/regles_production_20261116/validator/control_reproduction_review_v2_bounded.json)
accepte explicitement la reproduction physique et ces changements expliqués.
Les classifications de surplus dérivées de ces signaux peuvent changer même
si le stock physique et le coût opérationnel sont inchangés. Les effets sur
d'autres modes de simulation ou les cascades de risques ne sont pas déduits
de cette seule reproduction.

## Pourquoi les trois lots de mars existent

Les trois lots de 28 800 unités de 268091 lancés les 17, 24 et 31 mars ont été
avancés depuis des dates de lancement calculées les 3, 4 et 5 avril. Ils deviennent
utilisables à D1920 les 2, 9 et 16 avril. Ils ne répondent donc pas directement
à un besoin de 2026.

Pour le premier lot, le plan comporte 1 127 489 unités de besoin cumulé au
6 avril et 1 127 455 unités déjà engagées. Le besoin **supplémentaire** est de
34 unités ; la taille minimale source de 28 800 et le multiple de 14 400 donnent
une nouvelle proposition de 28 800 unités. Ce résultat est calculé sans changer
la taille de lot pour améliorer la courbe.

Les 1 127 455 unités engagées comprennent toutefois des fabrications tardives.
Seulement 202 490 sont prévues disponibles au 6 avril dans cet instantané.
Le déficit projeté si l'on ne compte que les disponibilités à temps atteint
donc 924 999 unités. **34 unités à ajouter et 924 999 unités manquant à temps
ne désignent pas le même problème.** Ce dernier chiffre est un besoin projeté
de l'usine, pas une rupture client mesurée. Déduire les ordres tardifs évite
leur duplication ; cela ne règle pas leur retard.

## Deux décisions à départager

Les quatre essais conservent le même carnet initial, les mêmes lots, capacités,
prévisions, demandes, sécurités et calendriers. Ils concernent les deux produits.

| Essai | Peut avancer un lot futur du plan net ? | Prévisions de composants obligatoires pour lancer ? |
|---|---|---|
| Témoin | Oui | Oui |
| Lancements à échéance | Non | Oui |
| Budgets indicatifs | Oui | Non |
| Deux règles combinées | Non | Non |

Dans tous les cas, matière physique, capacité, ordres initiaux et besoins connus
des autres usages restent protégés. Une prévision absente reste inconnue ; elle
ne devient pas une quantité nulle. Une prévision de composants connue conserve
son rôle antérieur dans le calcul des achats. Les options et leurs limites
sont décrites dans les [règles MRP](REGLES_MRP.md#séparer-date-de-lancement-et-rôle-des-prévisions-de-composants).

## Contrôles corrigés et limites conservées

### Connaissance des ordres au démarrage

Les 20 positions de 268091, soit 1 945 715 unités, concordent avec les quantités
et dates de `Extract_En_cours.xlsx/Sheet1!E/G/I72:91`. Le modèle les engage dès
le 1er janvier ; l'export conserve néanmoins la décision industrielle originale
comme inconnue. Le fichier ne renseigne ni création ni statut ferme. Il s'agit
d'une convention d'initialisation déjà documentée, pas d'une nouvelle erreur
de calcul.

Le rapprochement antérieur de 49 achats sur 49 ne confirme pas ces ordres de
fabrication. Les 2 528 lignes MRP de 268091 portent sur 1920 ; aucune ne décrit
directement les ordres de l'usine 1810.

Une borne arithmétique illustre l'enjeu dans l'instantané du 16 mars. Sur les
1 127 455 unités déduites comme engagements, 60 695 sont déjà fabriquées mais
encore retenues ; 1 066 760 restent à fabriquer. En conservant l'état physique
et en faisant varier seulement la quantité des ordres non achevés considérée
connue, le besoin supplémentaire calculé va de **34 à 1 066 794 unités**, avant
lotification. Ce n'est ni une estimation de la production réellement manquante
ni une date de création déduite des données.

La [preuve des 20 positions et de cette borne](../artifacts/testing/regles_production_20261116/opening_knowledge/review.json)
ne modifie aucun ordre et ne lance aucune simulation. Masquer des ordres puis
exécuter de nouvelles propositions avant de réintroduire les mêmes engagements
risquerait de doubler la fabrication. Un tel essai exige d'abord des identités,
dates de connaissance et règles de passage du prévu au ferme défendables.

### Périmètre des contrôles

Le diagnostic distingue cinq anciennes familles de refus. Les transferts de
produits finis étaient absents du périmètre de contrôle des libérations ;
261 budgets de semaines futures étaient exigés comme s'ils avaient déjà été
clôturés ; 211 événements portaient un libellé de provenance erroné ; 46 exports
de clôture omettaient la distinction entre périmètre source confirmé et
attribution inconnue du résidu. Les deux contrôles portant sur ces 46 exports
échouaient. Ces constats ne démontraient pas de perte physique.

La qualification corrigée conserve les contrôles d'origine, de dates et de
généalogie des transferts, valide tous les budgets archivés et contrôle
exhaustivement les clôtures effectivement exécutées. Elle n'accepte pas une
consommation future et ne transforme pas un résidu calculé en observation d'un
autre produit. Les anciens résultats incomplets restent conservés, sans
réétiquetage rétroactif. Voir le [contrat de vérification](TEST_VALIDATION.md#périmètre-des-transferts-et-clôtures-historiques).

La production réelle comparée reste **estimée par les retraits d'étuis
enregistrés**. Les semaines absentes restent inconnues. Les compléments du
carnet initial sont des réceptions planifiées supposées engagées, sans preuve
industrielle de leur caractère ferme. Les capacités demeurent partiellement
hypothétiques. Les invariants du logiciel ne valident pas ces hypothèses.

## Résultats et décision

**Aucune des trois variantes n'est retenue.** Le témoin reste le plus proche
pour 268967, sans devenir pour autant un modèle industriel validé. Les essais
couvrent le 1er janvier au 1er juin 2025, pas une année complète. Les écarts de
production utilisent les mêmes 13 semaines documentées pour 268967 et les
mêmes 21 pour 268091 ; les stocks utilisent les mêmes 22 photos comparables
par produit. La photo du 1er janvier est visible mais exclue de cette dernière
métrique, car sa clôture de veille n'est pas simulée.

| Essai | Erreur moyenne hebdomadaire 268967, unités | Erreur moyenne de stock 268967, unités | Erreur moyenne hebdomadaire 268091, unités | Erreur moyenne de stock 268091, unités |
|---|---:|---:|---:|---:|
| Témoin | **11 323** | **19 737** | 44 147 | **184 843** |
| Lancements à échéance | 22 669 | 58 497 | **42 090** | 201 207 |
| Budgets indicatifs | 30 138 | 64 894 | 69 214 | 231 410 |
| Deux règles combinées | 37 288 | 48 697 | 60 528 | 223 462 |

Ces erreurs sont la moyenne des écarts en quantité, pris positivement pour
empêcher un excès de compenser un manque. Le biais moyen de stock du témoin
268091 est seulement de +2,62 %, mais son erreur moyenne atteint 184 843 unités
et son surplus final 535 828 unités : le biais seul masque les décalages.

| Essai | 268967 : production sur semaines connues | Écart aux 402 500 unités réelles estimées | 268091 : production sur semaines connues | Écart aux 2 409 100 unités réelles estimées |
|---|---:|---:|---:|---:|
| Témoin | 323 400 | −19,65 % | 2 579 315 | +7,07 % |
| Lancements à échéance | 107 800 | −73,22 % | 2 622 515 | +8,86 % |
| Budgets indicatifs | 177 100 | −56,00 % | 2 838 515 | +17,82 % |
| Deux règles combinées | 107 800 | −73,22 % | 2 838 515 | +17,82 % |

Pour les budgets indicatifs de 268967, le travail simulé sur **tous** les jours
atteint 369 600 unités, dont 192 500 hors des semaines documentées ; 46 200
unités sont encore en cours de fabrication à la fin. Le volume achevé est de
323 400 unités. Aucun de ces périmètres ne remplace silencieusement celui de
177 100 utilisé dans la comparaison au réel connu. Toutes les courbes simulées
sont conservées dans le rapport.

### Explications établies

Attendre les échéances n'a pas supprimé seulement des avances : le recalcul
choisit ensuite d'autres lots. Pour 268091, trois lots de mars disparaissent
(−86 400 unités), mais les lots d'avril et mai augmentent de 72 000, 28 800 et
28 800 unités. Le total augmente donc de **43 200**, avec six lots au lieu de
neuf et les mêmes règles de taille de lot.

Pour 268967, le 7 avril, un lot de 107 800 est arrivé à échéance, mais les
budgets de composants bloquent encore son lancement. Le budget d'étuis est de
66 523 unités ; il manque 41 277 unités de cette autorisation hypothétique.
Ce déficit de budget n'est pas une pénurie physique d'étuis démontrée. Le lot
est accepté le 14 avril. D'autres propositions sont repoussées par les versions
successives du plan et restent futures. Supprimer seulement le budget ne
résout pas le calendrier : cela autorise aussi des anticipations peu conformes
aux observations. Les effets combinés sont mesurés séparément dans les preuves.

Les **20 ordres initiaux gardent leurs quantités et dates dans les quatre cas**.
Les demandes, expéditions et arrivées clients quotidiennes sont également
identiques. Les stocks absorbent les changements de fabrication. Pour 268967,
les 215 600 unités produites en moins dans l'essai à échéance correspondent à
107 800 unités de stock D1920 en moins et 107 800 de transport usine–D1920 en
moins. Ce dernier lot du témoin part le 1er juin ; sa réception du 3 juin et sa
disponibilité du 24 juin sont seulement **prévues**, hors du calcul.

Le statut administratif d'un ordre `in_transit` peut aussi désigner une réception
déjà physique mais non libérée. Il ne suffit pas à mesurer le transport réel.
Par exemple, 300 180 unités de 268091 sont déjà à D1920 en contrôle dans le
témoin. Le nouveau bilan utilise les événements de départ/réception et les
dates physiques pour distinguer transport et stock retenu, sans double comptage.

Les besoins exogènes des autres usages restent inchangés. Les résidus historiques
reconstitués après fabrication varient avec les consommations propres ; ce ne
sont pas de nouvelles observations industrielles. L'attente sur 029313 diminue
de 2,92 kilogrammes-jours dans l'essai à échéance ; le seul budget indicatif
ajoute 6,88 kilogrammes-jours sur 029313 et 54,43 sur 016332. Ces effets et leurs
unités sont conservés séparément des attentes clients en unités-jours.

Certains coûts simulés baissent malgré le moins bon rapprochement : le coût
d'immobilisation cumulé passe de 680 568,47 à 678 648,12 dans l'essai à échéance.
Les montants restent dans l'unité monétaire du modèle ; leur exhaustivité
financière n'est pas certifiée ici. Produire moins peut réduire un coût sans
mieux représenter les volumes industriels. Les sept postes de coûts et les
interactions sont conservés dans la revue indépendante.

### Vérification et suite

Les 119 tests ciblés passent sur les 669 fichiers gelés ; les quatre calculs
finaux passent la qualification des exports. La contre-vérification indépendante
des quatre cas passe **284 contrôles**. Les refus intermédiaires sont conservés :
catalogue incomplet, différences justifiées de diagnostics, puis confusion de
statut administratif avec le transport physique dans un premier oracle.
Les contrôles documentaires globaux restent refusés sur cinq domaines dont
les empreintes ou pages générées nécessitent une relecture ; ils ne sont pas
comptés comme réussis. Aucun navigateur ni suite globale n'est exécuté.

L'extension annuelle optionnelle n'est pas lancée : aucune variante n'améliore
conjointement production et stocks de 268967, et aucun gain client ne justifie
d'élargir ces candidats. Cela ne prétend pas prédire leurs résultats annuels.
Le prochain travail discriminant porte sur la **chronologie et la fermeté du
carnet initial**, puis sur les règles permettant de déplacer les ordres existants,
avant de réintroduire de nouvelles fabrications ou de régler davantage les
capacités. Les seules dates de livraison ne suffisent pas à établir cette
chronologie. Les options expérimentales restent disponibles, sans activation
automatique ni promotion de la référence.

[Rapport interactif local](../resultats/regles_production_20261116.html) ·
[Revue indépendante des quatre cas](../artifacts/testing/regles_production_20261116/validator/factorial_csv_review_v3.json) ·
[Manifeste final](../artifacts/testing/regles_production_20261116/final_manifest.json).

Les protocoles, refus conservés et preuves locales se trouvent dans
[`regles_production_20261116`](../artifacts/testing/regles_production_20261116/).
