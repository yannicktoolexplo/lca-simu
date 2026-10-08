# Règles MRP : analyse des sources industrielles et comparaison avec le moteur

## Statut de lecture au 7 octobre 2026 — reprise Scan3

**Ce fichier est un journal historique, pas la configuration active.** La référence
de comparaison conservée est **C8R** ; PGA est non retenu. L'ancienne confirmation
« Scan3 concerne uniquement 268091 et 268967 » est **remise en question par
l'utilisateur**. Les conclusions ci-dessous qui s'appuyaient sur cette exclusivité
ne constituent donc plus une preuve de périmètre. I porte le libellé « Sorties »,
pas « autres produits » ; I et J participent tous deux aux bilans signés.

Le [registre consolidé et la matrice C8R](../../docs/REGLES_MRP.md) distinguent
activation, convention et preuve. L'[audit Scan3 consolidé](../../artifacts/testing/audit_perimetre_scan3_20261007.md)
rapproche les nomenclatures, les mouvements et les stocks sans modifier les sources
ni le moteur. Les résultats historiques et leurs décisions restent conservés.

## Essais séparés de conditionnement et de report — 5 octobre 2026

Les options PACK et REPORT sont décrites dans la
[fiche des règles](../../docs/REGLES_MRP.md). Les recettes et preuves sont
regroupées sous `artifacts/testing/packaging_trials_20261005` : PACK reprend
les rôles « Pack » de la BOM pour les encours initiaux d'Avène ; REPORT teste
la révision des dates des six achats initiaux de 333362/Gien, sous hypothèse
explicite de commandes encore non expédiées et modifiables.

Ces essais sont indépendants. Les graphes sources, quantités initiales,
sécurités, demande client et référence C sont conservés. Un témoin R sans
option doit reproduire C. Les résultats annuels, leurs limites et leur statut
de qualification sont consignés dans le bilan de cette étude ; ces deux
options ne sont pas activées automatiquement dans le nominal.

## Décomposition des écarts d'emballages — 5 octobre 2026

La [décomposition indépendante des flux](../../artifacts/testing/packaging_diagnosis_20261005/bilan.md)
précise le diagnostic après les essais P/Q. Aux 52 photos de 2025, le surstock
de 333362/Gien provient principalement des réceptions ; celui de 338929/Avène
provient principalement de consommations trop faibles, avec également des
réceptions inférieures aux sources. Une correction commune diminuant les
commandes ne traite donc pas ces deux écarts de la même façon.

Au dernier point commun, photo du 29 décembre et flux jusqu'au 28 inclus :
333362 reçoit 1 104 891 UN de plus que les sources et consomme 137 550 UN de
plus ; 338929 reçoit 1 782 564 UN de moins et consomme 2 107 900 UN Scan3 de
moins. Les 1 945 715 étuis associés aux OF initiaux d'Avène sont une explication
plausible de l'essentiel de ce second écart, sans preuve du statut individuel
des OF. Les mouvements Divers et résidus de rapprochement restent séparés.

Ces résultats sont des diagnostics sur C conservé, pas des corrections
appliquées ni une nouvelle simulation annuelle. Les substitutions à flux figés
et les tests de planification ne sont pas assimilés à des trajectoires faisables.

## Rapprochement des besoins, essais P et Q — 5 octobre 2026

Deux règles communes ont été testées sur 365 jours, avec deux témoins reproduisant
42 CSV sur 42 exactement identiques à C. P rapproche les volumes sur les périodes
couvertes ; Q utilise `cumul retenu(t) = max(cumul industriel(t), cumul BOM(t))`
et conserve la trace des prévisions BOM avancées. Les dates physiques et les
paramètres sources ne sont pas recalés sur les observations.

Q améliore 15 stocks annuels et en dégrade 12. Les écarts moyens de 333362/Gien
et 338929/Avène baissent respectivement de 473 276 à 338 914 UN et de 602 411 à
430 625 UN. Les journées avec événement de manque matière à Avène passent
toutefois de 4 à 11, et une journée supplémentaire apparaît à Gien. Ce compteur
inclut des productions partielles. **Aucun des deux essais ne remplace globalement C.**

La [comparaison C / Q](../../resultats/mrp_scope_reconciliation_20261005/comparaison.html)
conserve tous les couples, leurs sources et leurs défauts de couverture. Le
[bilan](../../artifacts/testing/mrp_scope_reconciliation_20261005/bilan.md)
détaille les 47 tests en mémoire, les oracles indépendants, les témoins, les
limites et les échecs intermédiaires conservés. La
[fiche des règles](../../docs/REGLES_MRP.md) précise les conditions de Q.

La revue des encours établit que le crédit de 1 945 715 emballages avant janvier
à Avène est une convention calculée, pas un prélèvement source identifié.
La correction par étape de conditionnement reste à implémenter. À Gien,
aucun OF initial 268967 ne justifie la même correction ; le lancement d'avril
se calcule avec les délais actuels, alors que les flux industriels commencent
en mars. Ajouter tout le PF usine au stock de Muret ne résout pas les deux PF.
Les trois diagnostics et leurs contre-calculs sont liés depuis le bilan.

## Couverture de toutes les références et classement — 5 octobre 2026

Le [classement C / A](../../resultats/mrp_reference_coverage_20261005/comparaison.html)
porte sur 26 articles et 33 couples article/site. Le calcul indépendant retrouve
27 séries annuelles, 2 partielles et 4 couples non représentés ou non rapprochables.
001848/Gien n'est pas une simulation MRP complète : seul un ordre initial est
présent. 344135/Gien ne possède que trois photos de décembre. L'affichage et les
exports distinguent désormais ces situations ; aucun stock absent ne vaut zéro.

Les principaux écarts annuels concernent 333362/Gien, 338929/Avène,
730384/Gien et 042342/Gien. Les flux distinguent excès d'entrées, consommations
manquantes ou décalées, autres usages et hypothèses sur les OF d'ouverture.
Le [bilan détaillé](../../artifacts/testing/mrp_reference_coverage_20261005/bilan.md)
conserve toutes les valeurs, leurs unités et les limites des rapprochements.

Les trois couples actifs hors périmètre nécessitent un approvisionnement local
documenté ; ils ne sont pas ajoutés fictivement à la BOM des deux PF. Cette
étape corrige la comparaison et son classement, sans modifier le moteur ni
resimuler C/A. Les sources, stocks, sécurité et résultats physiques restent inchangés.

## Avancement des transferts engagés — 5 octobre 2026

La [fiche simple des règles et de leurs conditions](../../docs/REGLES_MRP.md)
décrit le calcul courant, ses différences entre achats et flux internes et
les conventions encore à confirmer. Le présent fichier conserve l'historique.

L'essai **A** ajoute à K une replanification des promesses internes futures :
calculer le supplément dû aujourd'hui sans ces promesses, le limiter au
reliquat engagé, puis expédier seulement la quantité physiquement réalisable.
L'identité et les dates originales restent tracées. La quantité affectée au
départ diminue le reliquat une seule fois ; le transit remplace cette promesse.

Le cas du 22 janvier est corrigé : 3 200 kg de 773474 partent de Gaillac,
arrivent à Gien le 1er février et deviennent utilisables le 10 février.
Il s'agit du même engagement, auparavant disponible le 14 avril.
La MAE de Gien passe de 9 870 kg dans K à 5 121 kg dans A, mais reste au-dessus
des 4 444 kg de C. A et C expédient le même total annuel ; deux départs plus
précoces à l'automne expliquent leur différence résiduelle de stock.

Deux simulations de 365 jours ont été exécutées. Avec la règle désactivée,
**43 CSV sur 43 sont identiques à K**. Par rapport à C, A retrouve 25 stocks
comparables, en améliore un et en dégrade trois : **C reste la référence**.
Les sources, la BOM, les stocks initiaux, la sécurité et les délais ne changent pas.

[Comparaison C / K / A](../../resultats/mrp_transfer_advance_20261005/comparaison.html)
· [Bilan et reproduction](../../artifacts/testing/mrp_transfer_advance_20261005/bilan.md)
· [Preuves](../../artifacts/testing/mrp_transfer_advance_20261005/manifest.json).

## Essais des consommations et transferts — 5 octobre 2026

Trois simulations de **365 jours** ont été comparées à C, sans modifier les
sources, la BOM, les stocks initiaux, les jours de sécurité ou les délais.
**Aucun essai ne remplace C.** La [comparaison des essais](../../resultats/mrp_corrections_20261005/comparaison.html)
et le [bilan complet](../../artifacts/testing/mrp_corrections_20261005/bilan.md)
conservent aussi les dégradations.

| Essai | Règle et condition | Résultat sur les stocks |
|---|---|---|
| E | Pour un autre usage physique identifiable, remplacer l'estimation du jour par `−I source`. Une absence garde l'estimation ; un zéro explicite vaut zéro. Les prévisions et prélèvements BOM restent distincts. | 11 couples améliorés, 11 dégradés, 7 inchangés. Pas d'adoption globale. |
| L | Pour un composant transféré par une route interne unique avec multiple physique explicite : `lot prévu = multiple × plafond(besoin net / multiple)`. Reporter le surplus sur les besoins suivants une seule fois. | Plans corrigés, 29 trajectoires de stock inchangées. L'exécution arrondissait déjà les départs. |
| K | L + maintenir un transfert entièrement financé dès le démarrage réel de la fabrication amont. Le solde d'engagement baisse seulement à l'expédition affectée ; aucune création de stock physique. | 9 améliorations, 10 dégradations, 10 inchangés. 773474/Gien se dégrade nettement ; hypothèse non retenue. |

E est une reconstruction historique des autres consommations, pas une règle de
prévision autonome. K teste le maintien d'engagements ; il ne prouve pas les
statuts ERP ni une règle universelle de gel ou d'avancement. Les 29 couples
incluent deux périmètres partiels explicités dans le bilan. EL n'a pas été simulé.

Pour 773474, K conserve davantage de stock à Gaillac et moins à Gien, avec un
stock moyen cumulé presque inchangé. La MAE à Gien passe de **4 444 à 9 870 kg**.
Il faut donc examiner le calendrier et la replanification des transferts,
sans compenser par une hausse de sécurité. Dès le 22 janvier, K supprime un
départ de 3 200 kg parce qu'il compte une promesse disponible le 14 avril,
alors que Gaillac possède 9 600 kg utilisables. Le calcul signale le retard
mais n'avance pas cette promesse : le prochain essai doit distinguer
**maintien de la quantité engagée et replanification de sa date**, sans créer
une seconde commande. Les sorties Scan3 des matières de
268091 restent par ailleurs incompatibles avec les seuls volumes conditionnés
selon la BOM fournie. Un contrôle journalier confirme l'application exacte de
cette BOM ; aucun multiplicateur de consommation n'a été ajouté.

## Demande client datée et comparaison des flux — 5 octobre 2026

L'essai **C** prolonge M sur **365 jours de 2025** avec
`Flow_Data_Customer_Demand.xlsx`. Il conserve stocks initiaux, sécurité,
nomenclatures et politiques de M ; les deux résultats restent accessibles.
Recette : `python -B etudecas/artifacts/testing/customer_comparison_20261005/study.py prepare`,
puis `simulate` (destinations nouvelles requises). Pour reproduire sans écraser
les résultats, ajouter aux deux commandes le même `--output-dir` désignant
un nouveau dossier sous `etudecas/artifacts/testing`.

- **Demande réalisée** : les 106 lignes `Historique/Actual Demand` fournissent
  les demandes clients arrivées, pas une preuve de livraison industrielle.
  Les quantités source négatives sont changées de signe. Chaque quantité
  hebdomadaire entière est répartie du lundi au dimanche par différence des
  cumuls entiers ; les jours hors 2025 conservent leur part. Le modèle ne peut
  consulter cet historique que pour le jour d'exécution courant.
- **Prévision de planification** : les 1 352 lignes de `Projection` décrivent
  13 versions de 52 semaines pour chacun des deux produits. À la décision t,
  sélectionner la dernière version dont la date est ≤ t. Le lundi de la
  semaine de version sert de date de connaissance par convention explicite :
  l'heure et le jour exacts de publication ne sont pas documentés.
- **Consommation de prévision** : `prévision_restante_semaine = max(0,
  prévision_connue_semaine − demandes_arrivées_dans_la_semaine)`. Répartir ce
  reste entre les jours futurs de cette semaine. Le reliquat client réel
  reste distinct ; la prévision inutilisée expire en fin de semaine.
- **Période absente** : conserver une ancienne version connue contenant cette
  période. Si aucune ne la contient, utiliser la période la plus proche de la
  dernière version connue comme **estimation**, avec cellule et version
  empruntées. Le début de janvier est notamment concerné. Cette hypothèse
  peut peser fortement sur le démarrage et ne vaut pas prévision source de
  cette semaine. Aucune demande réalisée future ne sert de remplacement.
- **Année suivante** : garder les véritables valeurs prévisionnelles 2026
  présentes dans le classeur. Pas de répétition automatique ni de coefficient
  de croissance de 5 % appliqué à ces valeurs.

Les besoins de composants industriels déjà configurés restent des signaux
distincts ; ils ne sont pas remplacés par la demande client. Le stock tampon
du nœud client conserve sa logique de couverture pendant le transport avec
les prévisions connues ; il faut distinguer expédition du dépôt, réception
client et demande servie pour expliquer un déplacement de stock.

La nouvelle comparaison sépare quatre lectures : photos de stock et états
simulés ; mouvements physiques hebdomadaires et registre simulé ; versions de
plans MRP ; demande client et prévisions. Les versions successives ne sont
jamais additionnées. Les prévisions hebdomadaires complètes et les besoins
futurs effectivement utilisés sur une semaine partielle restent séparés.
Les zéros explicites restent des zéros ; une observation absente reste absente.

Limites des mouvements : à Muret, le flux source net ne distingue pas les
entrées brutes des ventes. Pour 773474/Gaillac, H présente une incohérence de
bilan : conserver la valeur source et l'avertissement, sans division arbitraire.
Une courbe de flux ne transforme pas une projection MRP en mouvement exécuté.

Les preuves et résultats de cette passe sont référencés dans
`etudecas/artifacts/testing/customer_comparison_20261005/manifest.json`.

## Correction des décisions de planification — 5 octobre 2026

Deux essais annuels isolent des incohérences du calcul, sans changer les
besoins, la BOM, les stocks initiaux, les jours de sécurité ni les délais
sources de RKG. S active la sécurité future ; M ajoute les propositions
multi-fournisseurs explicites. Les fichiers sources restent des références :
leurs réceptions et leurs stocks ne sont pas injectés dans ces deux essais.
L'essai historique O ci-dessous est distinct et n'est pas leur point de départ.

### Sécurité évoluant avec les besoins projetés

Auparavant, certains étages de la chaîne calculaient la quantité de sécurité
aujourd'hui puis la conservaient sur tout l'horizon. Le pic futur ne relevait
ce plancher qu'en entrant dans la fenêtre proche. La politique
`rolling_source_workdays_v1` conserve les jours sources et recalcule la
protection à chaque date de l'horizon de 52 semaines :

```text
fin_fenêtre(t) = t + jours_de_sécurité_source, comptés du lundi au vendredi
sécurité(t) = max(stock_de_sécurité_fixe_source,
                 somme des besoins projetés sur ]t, fin_fenêtre(t)])
besoin_de_protection(t) = max(0, besoins_cumulés(t) + sécurité(t)
                                − stock_disponible − approvisionnements_affectés)
```

La protection n'est pas consommée et ne s'ajoute pas une deuxième fois aux
besoins physiques. Les engagements en contrôle, en fabrication ou en transport
conservent leurs dates de disponibilité ; un engagement tardif déjà affecté
ne provoque pas une seconde commande automatique. Le déficit temporaire est
conservé dans le plan.

Cette règle s'applique aux étages déjà protégés par les jours sources du
calcul cohérent de chaîne : fabrications, dépôt et composants internes, sauf
ceux qui emploient déjà une anticipation datée équivalente. Les achats
anticipés ne reçoivent pas une deuxième sécurité. Les besoins proviennent du
programme simulé connu à la décision, après netting et explosion de BOM.
L'absence de besoin à une date vaut zéro dans ce programme ; elle ne prouve
pas que les prévisions Excel sont complètes. En fin d'horizon, une fenêtre
incomplète conserve le plancher calculé à la décision au lieu de devenir zéro.

Oracle de calendrier : besoin de 100 à J42, sécurité de 10 jours ouvrés,
délai de 20 jours, origine mercredi. L'ancien plan lançait 100 à J22 pour
J42 ; le nouveau lance 100 à J8 pour J28. La quantité reste 100.

### Même fournisseur, même lot et même calendrier jusqu'à la commande

Certains achats multi-fournisseurs étaient planifiés avec le délai maximal
des offres et un lot générique, puis exécutés avec le fournisseur et le
standard réellement choisis. `allocated_supplier_plan_v1` fait ces choix
dès la proposition :

```text
part_à_acheter(f) = min(besoin_net_restant, besoin_net_du_groupe × part(f))
quantité(f) = arrondi de part_à_acheter(f) au lot propre du fournisseur f
disponibilité(f) = commande(f) + délai_fournisseur(f) + traitement_ouvré(f)
```

Le calcul inverse le calendrier propre de chaque offre pour trouver la
dernière date de commande compatible avec le besoin protégé. Le surplus
d'arrondi couvre les besoins suivants une seule fois. Le besoin net de masse
est arrondi au kg avant répartition ; les contraintes physiques et les UN
entières sont ensuite appliquées par offre. Le délai maximal éventuellement
exporté en résumé n'est plus le calendrier utilisé par ces propositions.

Conditions : achats datés et déterministes, plusieurs offres actives,
aucune politique explicite de fournisseur principal/secours, de fournisseur
sélectionné ou de regroupement spécifique. Sur RKG, cela concerne 001893 à
Avène et 021081 à Gaillac. L'ordre et les parts historiques du modèle sont
conservés : **ce correctif ne démontre pas des quotas industriels** et ne
généralise pas la règle principal/secours confirmée pour 001848.

Exemple de cohérence : pour un besoin de 740 kg et une première part de 70 %,
518 kg arrondis au standard de 23 920 kg couvrent tout le besoin. Le plan
représente ces 23 920 kg et le surplus de 23 180 kg dès le départ. Il ne
prévoit plus 740 kg avec 90 jours pour acheter ensuite 23 920 kg avec 62 jours.
Les 62 jours de cet exemple incluent le traitement à réception ; ils ne
remplacent pas le délai fournisseur source de 28 jours.

### Résultats vérifiés sur 2025

Comparaison et preuves : `artifacts/testing/mrp_decisions_20261005/` ; vue
interactive : `resultats/mrp_decisions_20261005/comparaison.html`.
La référence RKG et les deux essais restent disponibles séparément.

S rapproche 18 couples article-site des stocks réels et en éloigne 10.
M en rapproche 19 et en éloigne 9. Un autre couple, 001848 à Gien, reste
inchangé mais ne représente qu'un stock d'ouverture sans circuit courant.
Ces décomptes ne pondèrent ni les articles ni les unités et ne suffisent pas
à identifier une politique industrielle universelle.

| Écart absolu moyen aux photos | RKG | M |
| --- | ---: | ---: |
| 001893 Avène | 30 477 kg | 18 966 kg |
| 773474 Gaillac | 7 015 kg | 5 477 kg |
| 773474 Gien | 4 253 kg | 4 013 kg |
| 693055 Gaillac | 919 kg | 886 kg |
| 693055 Avène | 545 kg | 603 kg |
| 268091 Muret | 253 625 UN | 192 811 UN |
| 268967 Muret | 169 917 UN | 140 215 UN |

Les photos sont rapprochées de la clôture simulée de la veille ; l'ouverture
est exclue. Les références qui régressent avec M sont 734545, 344135, 708073
et 042342 à Gien, ainsi que 693055, 016332, 039668, 029313 et 002612 à Avène.
Le détail figure dans `validation/comparison.json` et dans la vue interactive.
M est une variante corrigée à poursuivre, sans remplacement automatique du
nominal ni exceptions par article ajoutées pour améliorer les scores.

L'amélioration de 773474 à Gien est essentiellement un changement de calendrier :
sur l'intervalle couvert par les photos, les entrées simulées restent de
76 800 kg et la consommation d'environ 77 602 kg. Pour 001893, les entrées
simulées passent de 451 460 à 430 560 kg sur ce même type d'intervalle ;
l'estimation des autres consommations reste très différente de I industriel.
Une courbe plus proche ne résout donc pas toutes les différences de flux.

Contrôles exécutés : deux simulations de 365 jours, 42 cas de calcul ciblés,
bilans physiques indépendants (1 430 intervalles par scénario), 67 612 points
de protection recalculés par candidat et 94 commandes multi-fournisseurs
contrôlées. Pour 64 de ces commandes, une proposition du même jour permet
une jointure exacte ; les 30 autres n'ont pas de snapshot hebdomadaire de ce
jour et ne sont pas présentées comme vérifiées par une ancienne proposition.
Les derniers contrôles natifs utilisent le code stabilisé. Après les deux
simulations, seules cinq gardes d'export ont été élargies pour autoriser
le mode multi-fournisseurs sans politique principal/secours ; leur résultat
booléen reste identique dans S et M, qui contiennent déjà cette dernière.

## Passe transversale après les mouvements 2025 — 5 octobre 2026

**Confirmation historique du 5 octobre, remise en question le 7 octobre :
`Sorties_article_scan3` concerne uniquement 268091 et 268967.** Elle avait remplacé
l'incertitude de périmètre signalée dans l'audit précédent ; cette incertitude
est désormais rouverte. Elle ne résout pas automatiquement les différences entre
les équivalents de production calculés depuis les matières et les emballages.

### Correction commune : séparer prévision et consommation physique

La référence RKG utilise deux calculs différents : la planification future
rapproche les besoins industriels totaux de la BOM des fabrications proposées,
mais la consommation complémentaire physique reste estimée avec une part
calculée dans le premier plan MRP. Ce dernier calcul est une hypothèse de
scénario ; il ne constitue pas une observation de consommation.

L'essai O conserve les règles de commande, les stocks initiaux, les lots, les
BOM, les sécurités, les prix, les délais et les prévisions de RKG. Pour les
autres usages des composants, il remplace les estimations physiques par les
sorties I du nouveau fichier lorsque leur interprétation est exploitable :

```text
besoin physique autres usages(j) = répartition de −I de la semaine documentée
consommation autres usages(j) = min(disponible après fabrication,
                                    retard autres usages + besoin du jour)
retard fin(j) = retard début(j) + besoin du jour − consommation du jour
```

Conditions communes, sans coefficient ajusté pour une référence : couple
présent dans le graphe, composant de BOM ou stock de matière première,
aucune valeur I positive pour ce couple dans l'extraction, absence de
fabrication locale de cet article et de départ de transfert interne déjà
représenté. Dix-huit couples satisfont ces conditions. Les sorties J restent
une référence pour contrôler la BOM exécutée : elles ne sont jamais ajoutées
comme seconde consommation des mêmes produits.

Les 774 semaines renseignées donnent 5 396 jours couverts, dont 2 798 zéros
explicites. Un zéro remplace l'estimation du jour ; une semaine absente conserve
le repli estimé, clairement indiqué dans le CSV. Un retard déjà constitué
n'est pas effacé. Les semaines sont réparties uniformément du lundi au
dimanche suivant le repère source, convention de calcul et non dates
industrielles journalières. Les UN utilisent les différences de parties
entières cumulées ; les jours hors 2025 ne sont pas reportés sur les autres.

Le nouveau calendrier est **réservé à l'exécution historique**. Chaque ligne
devient visible le jour où elle est exécutée. La planification future continue
de lire ses calendriers prévisionnels originaux, identiques octet pour octet
dans les métadonnées comparées. Les réceptions industrielles H et les stocks
photographiés ne sont jamais injectés pour commander ou ajuster le stock.
Cette correction permet un test conditionné par les autres consommations
réalisées ; elle ne démontre pas une nouvelle règle d'ERP ni une prévision
autonome de ces consommations pour une autre année.

### Cinq règles communes et leurs conditions

1. **Former les besoins sans les compter deux fois.** Pour une semaine future
   documentée, `complément prévu = max(0, besoin industriel total − BOM propre
   planifiée)` et `besoin total planifié = BOM propre + complément prévu`.
   Une BOM supérieure au total industriel est conservée et signalée. Les
   prévisions sont celles connues à la décision sur l'horizon glissant de
   52 semaines ; les semaines absentes ne deviennent pas des zéros. Aux
   clients, la demande physique de RKG reste une estimation issue d'une
   version MRP antérieure, pas une vente nouvellement mesurée.
2. **Calculer la position projetée par date.** `position(t) = disponible
   initial + engagements devenus disponibles avant t − besoins cumulés avant
   t`. Les stocks retenus en contrôle et les transports restent distincts,
   avec leur date de disponibilité. Un engagement tardif déjà affecté au
   besoin reste conservé pour éviter une commande en double ; le manque
   temporaire reste visible. Le stock physique peut donc être positif alors
   que le disponible ne couvre pas encore un besoin.
3. **Protéger le stock avec les paramètres sources.** `besoin net(t) =
   max(0, besoin à couvrir + protection − stock et engagements affectés)`.
   La sécurité est une protection, jamais une consommation. Les achats
   utilisent l'anticipation par jours de sécurité source ; les dépôts et
   transferts protégés utilisent le plancher de couverture prévu par la
   politique sélectionnée. À Gaillac, la protection actuelle se fonde sur les
   transferts nets proposés : ce point reste à confronter à une éventuelle
   réserve de réseau, et n'est pas déclaré identifié par les mouvements.
4. **Arrondir et dater les nouveaux ordres.** Le besoin net de masse est
   arrondi au kg, puis les minima, multiples et maxima de lots sont appliqués.
   Pour un standard S sans autre contrainte, `Q = S × ceil(besoin net / S)`.
   L'achat remonte de la date de besoin à la disponibilité protégée, à l'arrivée
   physique, puis à la commande en retirant respectivement sécurité,
   traitement à réception et délai fournisseur. Les jours ouvrés sont du
   lundi au vendredi ; les calendriers de transport restent distincts.
   Les offres utilisables tiennent compte des prix et de la possibilité de
   livrer à temps, avec secours plus rapide lorsque cette option existe.
5. **Exécuter selon la fonction du nœud.** Un fournisseur approvisionne ; une
   usine fabrique par lots en prélevant la BOM ; un site de stockage transfère.
   Gaillac peut combiner ces fonctions selon l'article, sans fabriquer à
   nouveau ce qui est seulement transféré. Les PF libérés sont poussés vers
   Muret ; les besoins remontent vers l'amont. Les commandes et fabrications
   restent limitées par les stocks et capacités représentés. Les contrôles
   PF restent à l'usine avant expédition ; `tau_process` conserve sa convention
   de planification actuelle.

Les 20 jours de sécurité de 268091 et les 25 jours de 268967 à Muret,
choisis par l'utilisateur pour 2025, sont conservés. Aucun taux de sécurité
n'est ajusté aux courbes. La consigne globale d'environ un an de couverture
de la chaîne médicament reste distincte des politiques locales : les
mouvements seuls ne précisent pas son allocation entre les étages.

### Essai séparé de cadence à Gaillac

L'essai OC reprend O et teste un seul changement supplémentaire : un
lancement de lot au plus par processus de Gaillac et par période de sept
jours du calendrier existant. Les mouvements rapprochés des photos montrent
29 semaines avec 3 200 kg de 773474 et 19 avec 600 kg de 693055 ; cela motive
l'essai, sans prouver une limite industrielle. Pour 773474, la déduction
repose encore sur l'anomalie H/2 identifiée dans la source.

**Limites explicites :** la limite porte sur les lancements physiques,
indépendamment pour les deux processus ; le plan futur ne réserve pas cette
capacité. Les périodes existantes sont alignées sur J0, soit mercredi–mardi
en 2025, et non sur les semaines source. OC est donc une sensibilité à la
cadence, pas un MRP à capacité finie validé. Les plans industriels prévoient
parfois plusieurs lots dans une semaine. L'essai a maintenant été exécuté :
il aggrave l'écart de stock de 773474 à Gaillac et n'améliore ni Gien ni les
PF. Cette limite de cadence n'est donc pas retenue dans la référence.

### Résultats annuels et décision

Deux nouvelles simulations de **365 jours** ont été exécutées, O et OC, dans
des dossiers distincts. La référence RKG est conservée. L'erreur absolue
moyenne aux dates des photos compare les stocks physiques, dans l'unité de
chaque article ; les unités ne sont pas additionnées entre articles.

| Article / site | Référence RKG | Essai O | Essai OC | Unité |
|---|---:|---:|---:|---|
| 002612 / Avène | 31 464 | 16 894 | 16 894 | kg |
| 007923 / Avène | 12 750 | 8 979 | 8 979 | kg |
| 055703 / Avène | 156 | 119 | 119 | kg |
| 001848 / Avène | 2 201 | 6 043 | 6 043 | kg |
| 693055 / Avène | 545 | 1 375 | 1 375 | kg |
| 693055 / Gaillac | 919 | 728 | 728 | kg |
| 773474 / Gaillac | 7 015 | 5 169 | 8 554 | kg |
| 773474 / Gien | 4 253 | 5 100 | 5 100 | kg |
| 268091 / Muret | 253 625 | 252 518 | 252 518 | UN |
| 268967 / Muret | 169 917 | 169 917 | 169 917 | UN |

Sur les 29 séries comparables, O améliore 13 erreurs moyennes, en aggrave 8
et en laisse 8 inchangées. Ce compte inclut 001848/Gien, dont le périmètre
incomplet est explicité plus bas. **O reste un diagnostic conditionnel,
pas une nouvelle référence industrielle validée.** OC est une sensibilité
non retenue. La capacité d'utiliser des sorties historiques documentées est
disponible sur option ; elle n'active aucune observation dans le nominal.

Le changement révèle un défaut précédemment masqué : certaines estimations
d'autres usages compensaient une consommation propre simulée insuffisante.
Pour 773474/Gien, sur les seules semaines documentées, J représente
**56 027 kg**, contre **23 919 kg** prélevés par les fabrications simulées.
Les autres usages I représentent **10 641 kg** et sont servis exactement
dans O sur ces semaines. Pour 693055/Avène, J vaut **9 840 kg**, contre
**731 kg** de consommation propre simulée ; I vaut **2 160 kg**. Rapprocher
uniquement le niveau de stock pouvait donc dissimuler une mauvaise
répartition des consommations. Ces chiffres ne justifient aucun changement
arbitraire de coefficient de BOM.

### Vérification des consommations propres contre les sources

Dans cet essai historique, Scan3 était exclusivement affecté aux deux PF selon
la confirmation d'alors ; cette affectation est remise en question le 7 octobre.
La contrelecture n'a trouvé ni doublon article/site/semaine, ni erreur de
conversion G/KG, ni coefficient de rendement expliquant le rapprochement.
Le produit 268091, son tube et son étui sont tous explicitement en **40 ML**.
Les trois copies de nomenclature donnent pour 001848 **1 218 G pour
1 000 UN**. Les tailles de lots ne changent pas cette base de nomenclature.

Exemple source, repère du 4 mai :

- `Flow_Data_Inventory_movements.xlsx/Feuille1!J117` : 900 000 G de 001848.
- Photos `Stocks!E824 − E460` : `7 900 020 − 8 809 620 = −909 600 G`,
  exactement expliqués par `G117 + J117 = −9 600 − 900 000 G`.
- Le plan MRP antérieur du 27 avril prévoit déjà 900 000 G en `I16139`.
- L'étui 338929, `J948`, représente 151 400 UN sur le même repère.

Diviser la consommation annuelle de 001848 par la BOM donne **24 234 034
équivalents BOM**, contre **5 016 700 étuis consommés**. Ce calcul ne mesure
pas la production réellement conditionnée. Les sorties matières peuvent
précéder le conditionnement ; toutefois, attribuer tout l'écart annuel à
ce décalage exigerait une accumulation d'encours qui n'est pas documentée.
L'origine du désaccord reste donc indéterminée. Il faut conserver les
prélèvements, la fabrication du vrac, les encours et le conditionnement
comme objets distincts dans le diagnostic, sans inventer un facteur ×5 ni
reclasser J comme consommation d'autres PF.

Preuves : [contrelecture des cellules et unités](../../artifacts/testing/mrp_movements_20261005/consumption/bom_diagnostic/recheck.json),
[diagnostic BOM](../../artifacts/testing/mrp_movements_20261005/consumption/bom_diagnostic/manifest.json).

Un contrôle supplémentaire rapproche les emballages et les flux PF sur la
même fenêtre, **du 6 janvier inclus au 29 décembre exclu**. Les trois
simulations ont les mêmes totaux PF, avec des différences possibles de dates.

| Flux de la fenêtre | 268091 | 268967 |
|---|---:|---:|
| Étuis consommés dans Scan3, BOM à 1 par PF | 5 016 700 | 1 263 850 |
| Nouveaux PF produits en simulation | 2 188 800 | 2 802 800 |
| OF d'ouverture achevés en simulation | 1 945 715 | 0 |
| Production simulée totale | 4 134 515 | 2 802 800 |
| Réceptions simulées à Muret | 3 731 315 | 2 587 200 |
| Variation simulée du stock de Muret | +235 726 | −599 689 |
| Variation des photos de Muret | +586 889 | −599 654 |

Les étuis constituent un indicateur du conditionnement, pas un registre de
fabrications terminées. Leur rapprochement suggère une production simulée
insuffisante pour 268091, mais excessive pour 268967 : **il n'existe pas de
sous-production générale démontrée**. Pour 268967, une variation de stock
final presque identique peut ainsi masquer des volumes produits et
expédiés différents. Les dates et les stocks intermédiaires restent à
réconcilier avant d'en déduire une correction de demande commerciale.

`Ventes = production conditionnée − variation stock PF usine − variation
transit − variation stock DC + ajustements` demande plusieurs termes
industriels encore non isolés dans ce rapprochement. Les résultats obtenus
en remplaçant la production conditionnée par les étuis et en omettant les
stocks intermédiaires **ne sont pas des ventes observées**. Le bilan source
PF de 268967 garde également un résidu de −13 608 UN sur cette fenêtre.
[Preuve des flux PF et limites](../../artifacts/testing/mrp_movements_20261005/consumption/bom_diagnostic/pack_reconciliation.json).

### Vérifications de cette livraison

Les quinze cas de calcul sélectionnés passent en mémoire, dont cinq
contre-exemples du vérificateur indépendant. Les exports RKG, O et OC
passent chacun la qualification native. Pour O et OC, le contrôle séparé
rapproche 8 760 lignes journalières d'autres usages et 1 430 bilans de stock
par calcul ; les 5 396 jours d'observations correspondent aux cellules
source, sans exposition anticipée aux projections futures.

Le moteur et les entrées sont restés identiques pendant les simulations.
L'adaptation du vérificateur a été intégrée ensuite, puis les tests et
qualifications ont été exécutés sur ce nouvel état stabilisé. Elle relit le
graphe exact et son empreinte pour reconstruire les observations attendues ;
elle ne prend pas les quantités des CSV comme leur propre référence.

La comparaison HTML est rapprochée numériquement des CSV et auditée dans un
navigateur local hors ligne. Le parcours autonome est distinct du parcours
natif réservé à la carte complète. Le premier lancement du navigateur a
échoué dans la sandbox Windows avant l'ouverture de Chromium ; les essais
réussis utilisent l'autorisation de l'outil, sans changement des protections
système. Les manifestes distinguent ces tentatives. Aucun essai d'altération
de fichiers, de dates ou de disparition simulée n'a été exécuté.

Ces vérifications prouvent les bilans et les rapprochements annoncés,
**pas l'identification complète du MRP industriel**. Le manifeste regroupe
les qualifications, les contre-calculs, les contrôles HTML et leurs limites.

### Périmètre restant incomplet

Le banc de comparaison trouve 29 séries de stocks dans les CSV, mais seulement
28 couples correspondants dans la structure du graphe. **001848 à Gien** est
créé par une commande initiale de 7 000 kg, sans stock défini, BOM ni circuit
d'achat dans le graphe : son absence de consommation est un défaut de
périmètre, pas un problème de stock de sécurité. Trois autres couples sources
ne figurent pas dans les résultats : 001893/Gaillac, 002612/Gaillac et
007923/Gien. Ils ne sont pas assimilés à des stocks simulés nuls.

Preuves et résultats de la passe :
[comparaison interactive 2025](../../resultats/mrp_movements_20261005/comparaison.html),
[manifeste de livraison](../../artifacts/testing/mrp_movements_20261005/manifest.json),
[dossier d'essai](../../artifacts/testing/mrp_movements_20261005/),
[contrôle indépendant des observations](../../artifacts/testing/mrp_movements_20261005/validation/observed_payload.json),
[périmètre du graphe](../../artifacts/testing/mrp_movements_20261005/validation/scope_baseline.json).

## Nouveau fichier de mouvements de stocks — 5 octobre 2026

Analyse de `Flow_Data_Inventory_movements.xlsx`, feuille `Feuille1` :
1 319 lignes, 26 articles, 32 couples article/site, 53 repères hebdomadaires
du 29 décembre 2024 au 28 décembre 2025. Aucun doublon article/site/semaine
ni quantité manquante ou non numérique. Les unités sont G, KG, ZUN et M :
conversion G/1 000 en KG et ZUN en UN, sans mélanger les articles ou unités.
Les quatre colonnes quantitatives sont G `Divers`, H `Entrées`, I `Sorties`
et J `Sorties_article_scan3`. Leurs signes sont conservés.

**Ce travail analyse les données et les résultats RKG existants. Aucun
mouvement observé n'a été injecté dans le moteur ; aucune source, règle de
simulation ou carte n'a été modifiée.** L'audit indépendant est un
rapprochement partiel, pas une certification de toutes les lignes.

### Rapprochement avec les photos de stocks

Le rapprochement exhaustif couvre 1 646 photos et 1 614 intervalles. Le
meilleur alignement observé associe, par exemple, le repère dimanche
5 janvier à la variation entre les photos lundi 6 et lundi 13 janvier.
Cette convention est démontrée pour ce fichier ; elle ne doit pas être
étendue automatiquement aux dates des autres extractions.

```text
variation de stock = Divers + Entrées + Sorties + Sorties_article_scan3
                     (valeurs signées, dans la même unité)
```

Avec cette formule, 1 177 des 1 315 intervalles renseignés ferment ;
138 présentent un écart. Les 299 intervalles sans ligne de mouvement ont
tous une variation de photo nulle, mais restent exclus des réussites :
cela suggère un export omettant les zéros sans prouver son exhaustivité.
Sur 420 intervalles où I et J sont simultanément non nuls, 375 ferment en
les additionnant. J ne doit donc pas être soustrait de I comme s'il en
était un sous-ensemble.

Les écarts cumulés s'annulent pour 30 des 32 couples sur le périmètre des
photos du 1er janvier au 29 décembre. Quarante-cinq paires d'écarts sur
des intervalles adjacents se compensent : des différences de rattachement
hebdomadaire sont plausibles, sans cause démontrée. Les deux exceptions
cumulées sont 773474/Gaillac et 268967/Muret. Pour ce dernier, un écart de
13 608 UN persiste sur le dernier intervalle, du 22 au 29 décembre. Le
repère du 28 décembre dépasse la dernière photo et n'est pas validé par
une photo de janvier 2026 absente.

### 773474 : les mouvements expliquent maintenant le décrochage de mai

Pour Gien, la ligne 1253, repère du 11 mai, donne une entrée de
6 400 kg, une sortie Scan3 de 1 056,2 kg et Divers de +0,2 kg. Les photos
`Stocks!E292` et `Stocks!E1210` ferment exactement le bilan :

```text
stock du 12 mai + entrée − sortie + divers = stock du 19 mai
16 108 + 6 400 − 1 056,2 + 0,2 = 21 452 kg
```

Les 6 400 kg ne sont donc plus seulement une réception projetée dans le
MRP : ils figurent aussi dans les mouvements et expliquent les stocks.
Cela ne donne ni la date journalière ni l'identifiant de l'ordre. Le plan
MRP du 4 mai les annonçait déjà en `Feuille1!H18031` pour le repère du
11 mai, avec 1 048,760994 kg de besoins en I. Dans RKG, cette même semaine
ne comporte aucune réception et consomme 1 635,388 kg, dont 594,609 kg de
consommation complémentaire estimée. Le déstockage hors entrée dépasse le
déstockage net source de 579,388 kg ; l'écart entre les variations des
deux stocks vaut donc 6 979,388 kg. Cette réception et cette consommation
doivent être expliquées séparément avant d'ajuster une règle MRP.

Sur les 51 semaines communes, du 6 janvier au 28 décembre (photos du
6 janvier au 29 décembre), quantités ci-dessous arrondies au kg :

| Flux | Données sources | Simulation RKG |
|---|---:|---:|
| Sorties I + J de 773474 à Gien / consommations simulées | 66 667 | 77 602 |
| Réceptions de 773474 à Gien | 67 200 | 76 800 |
| Expéditions de 773474 depuis Gaillac | 67 200 | 80 000 |
| Sorties I + J de 693055 à Avène / consommations simulées | 12 000 | 13 238 |

À Gien, les 43 intervalles de 773474 comportant des mouvements ferment
avec les valeurs brutes. À Gaillac, les entrées H de ce même article
présentent une anomalie systématique : H brut ferme 12/41 intervalles,
alors que l'hypothèse H/2 ferme 41/41. C'est le seul couple amélioré par
cette division. Exemple ligne 1282, repère du 19 janvier : H vaut
6 400 kg, sans autre mouvement, mais le stock passe de 6 400 à 9 600 kg,
soit seulement +3 200 kg. La cause du facteur deux reste inconnue et
aucune correction de source n'est appliquée.

Sur la période commune, les photos de Gaillac et les sorties impliquent
92 800 kg d'entrées nettes, contre 185 600 kg dans H brut. RKG totalise
également 92 800 kg : 89 600 kg de nouvelles fabrications et 3 200 kg
d'OF d'ouverture. Sous ce rapprochement, le déficit de variation du stock
simulé à Gaillac vient des 12 800 kg expédiés en plus, pas d'un manque de
production totale sur l'année. Le calendrier de production reste à vérifier.

Les sorties de Gaillac et les entrées aval se correspondent au même repère
dans les 18 semaines actives de 773474 et les 19 de 693055. C'est une
correspondance comptable hebdomadaire ; elle ne prouve pas un transport
physique instantané et ne valide pas les hypothèses actuelles de 10 et
7 jours de trajet.

### Périmètre Scan3 et produits finis : limites à lever

Les 24 ratios BOM utilisés par le graphe sont conformes aux trois fichiers
de nomenclature. Cependant, rapporter les sorties Scan3 aux BOM donne, sur
les repères 2025, environ 24,23 millions d'équivalents PF pour les douze
matières d'Avène, contre 5,02 à 5,12 millions pour les trois emballages.
À Gien, les matières donnent 5,80 à 6,08 millions, les emballages 1,26 à
1,31 million. Cet écart structuré ne vient pas d'une erreur de recopie des
BOM ; le périmètre produit, les formulations et les unités de conditionnement
restent à confirmer. **Scan3 n'est pas encore assimilé automatiquement aux
deux seuls PF 268091 et 268967.** La question a été posée à l'utilisateur.

Le tableau par article/site conserve séparément I et J et compare leurs
volumes aux consommations simulées. Les écarts sur 002612, 007923, 021081
et 730384 justifient de réexaminer les compléments de consommation estimés.
Ils ne constituent pas encore de nouveaux coefficients validés : le
périmètre Scan3, les bornes temporelles et les encours initiaux comptent.

Pour les PF à Muret, H est toujours nul et I peut être positif. On dispose
donc de mouvements nets signés, pas d'une séparation exploitable entre
réceptions des usines et livraisons clients. Des matières comme 016332,
029313, 039668 et 099439 ont aussi des I positifs et H nul. Il serait faux
de traiter partout I comme une consommation brute.

Sur les 51 semaines communes, les photos de 268967/Muret varient de
−599 654 UN, contre −599 689 UN simulées : le total net est proche, ce qui
ne valide ni les niveaux intermédiaires ni les flux bruts. Pour 268091,
la variation réelle est +586 889 UN contre +235 726 UN simulées. Le
nouveau fichier seul ne permet pas d'attribuer les 351 163 UN d'écart à
la production, aux expéditions ou à la demande.

Suite proposée : clarifier les colonnes et le facteur deux de Gaillac,
rapprocher les consommations par périmètre produit, puis tester les règles
communes sur ces flux et leurs dates en plus des seuls niveaux de stock.
Les données réalisées servent de référence de validation ; les recopier
comme commandes simulées ne démontrerait pas la reproduction du MRP.

Preuves : [manifeste de l'audit](../../artifacts/testing/inventory_movements_20261005/manifest.json),
[rapprochement indépendant](../../artifacts/testing/inventory_movements_20261005/validation/manifest.json),
[détail Gaillac, Gien et PF](../../artifacts/testing/inventory_movements_20261005/gaillac/focus.json),
[tous les articles/sites](../../artifacts/testing/inventory_movements_20261005/consumption/pair_consumption.csv).

## Besoin net arrondi au kilogramme — demande utilisateur du 5 octobre 2026

La règle demandée est disponible sous
`meta.mrp_net_requirement_rounding_policy = "nearest_kg_half_up_v1"`.
Elle est activée dans l'essai RKG, construit depuis S25C en ajoutant cette
seule option. L'absence d'option conserve le calcul historique.

```text
besoin net arrondi en kg = arrondi au plus proche(besoin net cumulé en kg)
                         avec 0,5 kg arrondi vers 1 kg
quantité proposée = application du minimum, multiple et maximum de lot
                    au besoin net arrondi
```

Exemples : 0,49 kg donne zéro ; 0,50 kg donne 1 kg. Avec un lot standard
de 600 kg, 600,4 kg donne une proposition de 600 kg, tandis que 600,5 kg
est arrondi à 601 kg puis conduit à deux lots de 600 kg. Le quantum est
1 pour les KG et 1 000 pour les G ; les articles en UN restent hors de
cette politique et leurs quantités physiques restent entières.

Les stocks physiques, les consommations BOM, les engagements déjà pris et
les données sources ne sont pas arrondis. Un reliquat non commandé reste
dans le calcul : deux besoins successifs de 0,3 kg produisent un besoin
cumulé de 0,6 kg, puis une proposition arrondie à 1 kg. Cela peut différer
une petite quantité réelle de moins de 0,5 kg ; la règle demandée ne se
limite donc pas aux résidus d'erreur binaire. Aucun stock fictif ne vient
combler le manque. Un solde projeté négatif est explicite ; les contrôles
physiques continuent d'interdire une consommation supérieure au disponible.

Les champs `dated_net_rounding_quantum` et `dated_rounding_uncovered_qty`
des traces documentent cette précision et le résidu. Les achats, le secours,
les fabrications et les transferts planifiés utilisent la même précision
sur les masses, avant les règles de lots existantes. Les méthodes de
protection, d'anticipation et de recalendrage conservent cette politique.

Vérifications mémoire sur code gelé : 30 tests ciblés et trois régressions
passent ; un oracle indépendant vérifie 58 assertions. La réexécution des
104 plans sources couvre 874 variantes calculables, toutes concordantes
avec le nouvel oracle rationnel pour les quantités et dates des propositions.
Les 406 variantes à couverture incomplète restent exclues. Les 18 anciennes
anticipations numériques de 693055 sont supprimées (dix d'un jour, huit de
trois jours), sans modifier les volumes totaux ni le nombre de propositions
de ces diagnostics. Les cas 773474 restent identiques : cette correction
ne démontre pas la règle expliquant sa réception industrielle de mai.

L'essai physique RKG sur 365 jours est terminé (607,015 secondes, retour
zéro, code et sources inchangés durant le calcul). La qualification CSV
passe. L'oracle annuel confirme les quantums effectivement appliqués,
l'absence de stock physique négatif et les quantités UN entières. Les 187
résidus non nuls exportés restent tous sous le demi-kilogramme ; le maximum
relatif vaut 0,4968 kg. Les stocks aux dates des photos sont identiques à
S25C pour les 29 couples comparables, donc les écarts moyens aux sources
restent identiques. Des différences journalières existent sur 039668/Avène
(450 kg au maximum), 693055/Gaillac (600 kg) et son intrant fictif (1 UN,
effet de calendrier de fabrication, sans arrondi des UN). Leurs nombres
de jours à stock nul sont inchangés. Aucune nouvelle carte HTML n'est
générée pour cette modification ; les anciennes restent conservées.

Preuves : [manifeste de livraison](../../artifacts/testing/mrp_kg_rounding_20261005/manifest.json),
[comparaison des calculs sources](../../artifacts/testing/mrp_kg_rounding_20261005/source_replay/comparison.json),
[oracle indépendant](../../artifacts/testing/mrp_kg_rounding_20261005/validation/sources.json).

## Test du besoin net sur les états sources — 5 octobre 2026

**Périmètre : calcul en mémoire avec le helper existant
`plan_with_stock_protection`, pas une simulation physique annuelle ni une
correction du nominal.** S25C, les cartes et les sources sont conservés.
Le test couvre 52 versions pour 773474/Gien et 52 pour 693055/Avène.
Il sépare trois cas : conserver les H comme crédits prévus conditionnels,
retirer une réception cible en gardant les autres, retirer tous les H futurs.
Aucun de ces cas ne démontre le statut ferme des réceptions industrielles.

J courant initialise le disponible ; J futur conserve des libérations de
stock déjà présent. I futur est réparti sur les sept jours à partir du
repère hebdomadaire, convention diagnostique explicite. I courant est soit
déduit à la décision, soit exclu : les deux variantes encadrent un statut
inconnu, sans assimiler cet agrégat à une consommation réalisée. H et J
sont positionnés au repère comme crédits de disponibilité prévus ; leur
date physique exacte reste inconnue. Les dates de transport sont reculées
à titre indicatif seulement : le calcul ne simule ni camion ni capacité.

La protection principale couvre les 20 jours ouvrés à la date de décision,
puis reste constante dans ce plan, comme la convention S25C. Une variante
la recalcule à chaque date future. Les lots valent 3 200 kg et 600 kg.
La fenêtre de protection est intégralement renseignée dans 73 des 104 plans ;
les 31 autres ne sont pas complétés par des zéros. Parmi les 1 280 combinaisons
de variantes, 874 sont calculées et 406 sont explicitement non exécutées
faute de fenêtre complète. Les 4 227 bilans K des lignes sources ferment.

### 773474 : le même état industriel ne déclenche toujours pas les 6 400 kg de mai

Plan du 4 mai, stock J source de 16 734,2 kg, protection de 2 996,46 kg :

| Cas | Résultat |
|---|---|
| Retrait des seuls 6 400 kg du 11 mai, I courant intégralement déduit | Fin de semaine : 13 587,92 kg ; marge de 10 591,46 kg au-dessus de la protection |
| Même retrait, autres H conservés | Aucun déficit de protection ni proposition supplémentaire jusqu'au 2 août, limite des semaines consécutives renseignées |
| Aucun H futur, protection fixe | Premier besoin le 3 juillet si I courant est déduit ; le 13 juillet sinon |
| Aucun H futur, protection glissante | Premier besoin le 18 juin si I courant est déduit ; le 30 juin sinon |

Ainsi l'écart de mai ne disparaît pas en remplaçant l'état simulé par
l'état industriel disponible dans ce plan. Ces résultats ne prouvent pas
que la réception prévue de 6 400 kg était inutile : elle peut correspondre
à un programme ou engagement antérieur, ou à une politique de positionnement
du stock que le calcul local de protection ne représente pas. La règle
industrielle de maintien reste non identifiée.

### 693055 : montant retrouvé sous condition, calendrier physique non validé

Le 4 mai, J vaut 940 kg et la protection 874,29 kg. En retirant les H futurs
et en excluant I courant, le calcul propose 600 kg disponibles le 12 mai,
proches du repère source H de 600 kg au 11 mai. Si les 630 kg de I courant
restent intégralement à servir, le besoin apparaît dès le 5 mai. La variante
glissante avance aussi l'échéance. Ce résultat conditionnel ne valide donc
ni le statut de I courant ni la date physique de réception : H pourrait
porter une autre étape que la disponibilité utilisée dans ce test.

La nécessité chronologique et la nouvelle proposition sont distinctes :
en retirant seulement H du 11 mai et en conservant les H ultérieurs, le
plancher peut être franchi le 12 mai sans nouvelle proposition à cette date.
Le helper affecte les crédits plus tardifs avant de recommander. Le champ
`firm_late_qty` porte sur les besoins physiques, pas sur la protection ;
sa valeur nulle ne prouve pas que cette protection est respectée.

Preuves et réserves de contre-vérification :
[manifeste du test](../../artifacts/testing/gaillac_netting_20261005/manifest.json),
[résumé des calculs](../../artifacts/testing/gaillac_netting_20261005/calculation/summary.json)
et [tableau des 104 plans](../../artifacts/testing/gaillac_netting_20261005/calculation/comparison_104_vintages.csv).
Les invariants et contre-calculs restent distincts de la calibration.

**Contre-vérification finale : partielle, avec anomalies numériques explicites.**
L'oracle indépendant contrôle 23 621 valeurs et dates : 23 603 concordent,
18 dates de première proposition sur 693055 sont avancées de un ou trois
jours par rapport à l'arithmétique rationnelle exacte. Au jour du déclenchement,
le déficit exact vaut zéro ; la répartition flottante de I sur sept jours et
le calcul d'enveloppe produisent un franchissement numérique du seuil. Les
quantités, niveaux et domaines comparés concordent. Sur 874 scénarios
calculés, 856 ne présentent pas de différence ; les 406 non calculés restent
exclus. Tous les cas 773474 et les cas du 4 mai pour les deux articles sont
concordants. Le contrôle global reste en échec sur ces 18 dates, avec preuve
conservée ; aucun seuil de tolérance n'est ajusté pour le faire passer.
L'effet sur le nominal exprimé en G n'a pas été démontré par ce diagnostic
en KG. Aucun correctif du moteur ni nouvelle simulation physique n'est
livré ; ce point doit être reproduit dans les unités natives avant correction.

## Gaillac : rapprochement des programmes source et simulation — 5 octobre 2026

**État : diagnostic en lecture seule sur S25C conservé ; aucune nouvelle
simulation ni règle activée.** Les essais C/C3 restent rejetés. Les sources
sont les 52 versions du MRP 2025, les photos de stock et les CSV S25C.

### Le besoin futur à Gien est bien présent, mais le programme de transfert diffère

Dans le calcul daté du 4 mai pour 773474/Gien :

| Grandeur | kg |
|---|---:|
| Disponible simulé au début du calcul | 15 508,560 |
| Besoins futurs sources jusqu'à fin mai | 3 146,283 |
| Besoins futurs représentés par le simulateur | 3 146,283 |
| Solde sans nouvelle réception après ces besoins | 12 362,277 |
| Protection courante du calcul | 2 996,460 |
| Réception H source au repère du 11 mai | 6 400 |

Le plan simulé du 4 mai ne propose donc aucun transfert futur en mai ; sa
première nouvelle proposition part le 11 juin et devient disponible le
30 juin. Ce sont les propositions de cette version, pas les dates exécutées
finales : les révisions ultérieures conduisent à un départ le 28 mai.
I courant contient aussi 2 097,522 kg. Le comparer aux seuls besoins futurs
créerait un faux diagnostic d'oubli ; même son ajout ponctuel ne suffirait
pas à franchir la protection courante. Ce compartiment peut contenir des
besoins reportés et ne doit pas être consommé à nouveau sans rapprochement.

Sur une fenêtre identique (semaines des 11 et 18 mai), I source passe de
5 243,805 kg dans le plan du 16 mars à 2 097,522 kg dans celui du 4 mai.
Les besoins simulés reproduisent exactement ces deux montants. Cette baisse
est une révision réelle du programme, pas l'effet d'une fenêtre qui se
raccourcit : I10969/I10970 puis I18031/I18032 donnent le rapprochement direct.

À Gaillac, le même plan source prévoit 6 400 kg de sortie au repère courant
du 4 mai et 6 400 kg futurs au 25 mai ; le plan simulé ne porte aucun besoin
de transfert futur en mai. Il dispose déjà de 19 200 kg, avec 3 200 kg
retenus qui deviennent disponibles le 6 mai. L'absence de matière à Gaillac
n'explique donc pas la décision du 4 mai. Les besoins amont sur la fenêtre
commune jusqu'au 19 avril 2026 valent 89 298 kg côté source contre 86 040 kg
simulés (courant inclus côté source) : une proximité du total ne valide
pas son calendrier. Ces volumes sont ceux d'un plan, pas des flux exécutés
sur une année ni une somme des 52 versions.

### Des positions planifiées persistent ; leur identité reste inconnue

Les positions H de 6 400 kg à Gien sont les suivantes :

| Version | Repères avril–mai portant H = 6 400 kg |
|---|---|
| 5 janvier | 6 avril, 27 avril, 18 mai |
| 13 avril | 20 avril, 27 avril, 18 mai |
| 20 avril | 27 avril, 11 mai, 18 mai |
| 27 avril | 11 mai |
| 4 mai | 11 mai |

La position du 18 mai existe dans 16 versions consécutives, mais celle du
11 mai apparaît alors que le 18 mai reste présent. **Il serait donc faux
de conclure à une simple anticipation du 18 au 11 mai.** Un report depuis
avril est compatible avec les agrégats ; aucune identité d'ordre ne le prouve.
Les cellules H14964/H14965/H14967 puis H15996/H15997/H15998 permettent
de vérifier cette distinction. Le nouvel essai ne doit pas rendre ferme
automatiquement chaque H industriel ni toute fabrication démarrée.

Sur les 971 positions futures H positives de Gien, 566 ont une quantité
identique à I Gaillac à la semaine précédente, contre 291 à la même semaine.
Les positions sans ligne amont correspondante restent manquantes, pas nulles.
Les lots répétés et les agrégats hebdomadaires empêchent d'en déduire une
identité de commande ou sept jours de transport physique.

### 693055 et le total des deux sites écartent une explication unique

Dans le plan du 4 mai, Gaillac/693055 porte 14 400 kg de sorties et Avène
12 000 kg d'entrées sur les semaines communes jusqu'au 19 avril 2026.
Les 2 400 kg d'écart sont intégralement dans I courant à Gaillac : les
programmes futurs valent chacun 12 000 kg. Ce cas ne prouve donc pas une
consommation supplémentaire de 2 400 kg. Le rapprochement par décalage
d'une semaine est également beaucoup moins discriminant que pour 773474.

Le rapprochement des photos des deux sites montre aussi que tout l'écart
n'est pas un excédent amont compensant un manque aval. Pour 773474 en
juillet, les écarts moyens signés sont −12 000 kg à Gaillac et −7 450 kg
à Gien, soit −19 450 kg sur les deux stocks physiques. Pour 693055 en
novembre, les deux sites sont au contraire au-dessus des photos, de 2 810 kg
au total. Ce sont des sommes de stocks sur sites : le transit industriel
est inconnu. Elles ne prouvent pas seules une erreur de production ou de
consommation, mais ne se résument pas à une permutation du stock entre sites.

### Conclusion et prochain contrôle discriminant

La propagation informatique aval→amont est cohérente sur 14 522 lignes ;
elle ne reproduit pas pour autant le programme industriel daté. La condition
qui maintient une réception source malgré une couverture locale suffisante
reste non identifiée : engagement antérieur, affectation de stock, règle
de protection ou programme de fabrication distinct doivent être discriminés.
Il faut comparer le netting sur un même état daté source (J, besoins futurs,
engagements identifiables), puis séparer quantité et replanification.
Ce contrôle de calcul doit rester distinct d'un scénario qui rejouerait H
comme des réceptions réalisées. Les consommations complémentaires estimées
et la localisation des délais qualité restent des limites séparées.

Preuves regroupées dans
[le manifeste du diagnostic](../../artifacts/testing/gaillac_bridge_20261005/manifest.json) :
rapprochements sources, programmes simulés, stocks cumulés sur deux sites,
7 289 bilans K, contre-vérification directe de huit instantanés et
qualification CSV ciblée S25C. Aucun test d'altération de fichiers, aucune
suite globale et aucune nouvelle simulation n'ont été exécutés.

## Essai du 4 octobre 2026 : engagement lié au lancement amont

**Statut : règle non retenue pour le nominal. C et C3 dégradent la comparaison ;
C2 a été interrompu par un contrôle d'intégrité et est exclu des résultats.
La référence S25C est conservée.**
Option candidate : `internal_transfer_commitment_policy=upstream_launch_pegged_v1`.
Calcul physique sur 365 jours, avec la projection glissante existante.

Constat architectural : une proposition de transfert crée un besoin daté
en amont. Une fabrication démarrée pour ce besoin est conservée comme
campagne, alors que la proposition de transfert peut être recalculée.
Le candidat conserve le lien entre ces deux décisions.

Conditions communes, sans sélection par numéro d'article : composant
consommé par une usine, une origine interne unique et réellement fabriquée,
et début effectif du travail d'une nouvelle campagne amont. Les produits
finis déjà expédiés suivant la politique de poussée existante sont exclus.
Une quantité ne devient promise que si son allocation est entièrement
couverte ; la même allocation ne peut pas servir deux engagements.

L'engagement est une promesse **non physique**, créditée dans la projection
aval et débitée comme besoin amont. Il ne crée ni stock ni transit. Au départ,
la quantité expédiée sort de cette promesse et entre dans le registre de
transport existant ; un reliquat éventuel reste identifié. Les délais de
libération, les créneaux de départ, les stocks réellement disponibles et les
capacités restent contraignants. Aucune réception H industrielle n'est
importée comme ordre exécuté. Les propositions non engagées restent révisables.

Critères de lecture : évolution de 773474 à Gien en mai et sur l'année,
conséquences à Gaillac et sur 268967 à Muret, et comparaison avec 693055
à Avène/Gaillac. Les stocks, les quantités reçues et le service doivent être
présentés séparément. Une conservation correcte des quantités ne démontre
pas que la règle reproduit les décisions industrielles.

Le premier essai C a rétabli une réception de 6 400 kg le 17 mai, mais aussi
ajouté 3 200 kg les 3 et 10 mai. L'écart absolu moyen annuel de 773474 à Gien
est passé de 4 252,72 à 11 051,78 kg : **ce résultat n'est pas retenu**.
Le contrôle indépendant a identifié un défaut dans ce nouveau mécanisme :
une expédition arrondie ne soldait que les promesses échues, laissant des
promesses futures couvertes par son excédent provoquer d'autres départs.
Ce n'était pas une création de masse dans le bilan physique, mais un
réapprovisionnement supplémentaire injustifié.

C2 corrige ce seul rapprochement : les quantités effectivement expédiées
soldent les promesses **déjà créées**, de la même liaison, par échéance,
y compris les échéances futures. Le champ `early_handoff_days` trace les
livraisons anticipées ; la date initiale reste conservée. Les besoins,
les stocks de sécurité, les tailles de lot et le déclenchement des départs
ne changent pas. Cas mémoire vérifiés : promesses 3 + 7, départ de 10 donnant
un reste nul, ou départ de 8 donnant un reste de 2 sans nouveau besoin en
double. Le nouveau comportement est expérimental et désactivé par défaut.

C2 s'est arrêté sur `Physical UN firm receipts must be integer` ; ses
sorties partielles ne sont pas utilisées comme résultat annuel. Un défaut
de transmission du total entier d'une campagne est reproductible en mémoire :
`remaining=107800.00000000003`, `WIP=0` donnent un total normalisé de 107800,
mais le couple `(remaining, max(total-remaining, 0))` réintroduit le résidu.
C3 normalise le seul crédit de campagne UN dans la tolérance numérique
déjà admise et refuse toujours les fractions réelles. Les besoins BOM
prévisionnels et les quantités physiques produites ne sont pas arrondis par
ce correctif. Le journal doit identifier les cas effectivement rencontrés
dans le calcul, séparément de cette reproduction mémoire.

### Résultat annuel C3 et décision

C3 s'est achevé sur 365 jours en 921,016 secondes, code et sources inchangés
durant l'exécution. Le cas réel journalisé concerne la campagne
`CMP-00000060-M-1430-item:268967-D254` : 107800,00000000001 UN normalisés
en 107800, soit un résidu de 1,4552e-11 UN. Le calcul C2 interrompu n'est
pas assimilé à un résultat annuel.

| Écart absolu moyen aux 52 photos | S25C conservé | C rejeté | C3 corrigé, non retenu |
|---|---:|---:|---:|
| 773474 Gien, kg | 4 252,72 | 11 051,78 | 9 121,53 |
| 773474 Gaillac, kg | 7 015,38 | 14 584,62 | 10 215,38 |
| 693055 Avène, kg | 545,07 | 523,78 | 509,58 |
| 693055 Gaillac, kg | 918,65 | 1 252,50 | 1 229,04 |
| 268967 Muret, UN | 169 916,85 | 169 916,85 | 246 264,33 |
| 268091 Muret, UN | 253 625,44 | 260 271,60 | 260 271,60 |

Sur les 29 couples comparables : C3 améliore 9 écarts, en dégrade 18 et en
laisse 2 identiques. C3 reçoit à Gien 3 200 kg les 10, 17 et 24 mai : les
6 400 kg du repère MRP du 11 mai ne sont donc pas reproduits comme tels.
Au rapprochement du 19 mai : 10 588,228 kg physiques simulés, contre
21 452 kg dans la photo et 13 788,228 kg dans S25C. La disponibilité à Gien
est nulle 66 jours en C3, contre zéro dans S25C. Le stock de 268967 au dépôt
est nul neuf jours, contre zéro dans S25C, même si les volumes annuels
produits et servis sont identiques : le rattrapage annuel ne prouve pas
l'absence de retard.

**Conclusion limitée à cet essai :** l'affectation d'un transfert au premier
travail de fabrication ne suffit pas comme règle commune de calibration.
Le rapprochement FIFO des livraisons anticipées corrige le défaut de C,
mais ne valide pas la condition d'engagement. La règle reste optionnelle,
désactivée par défaut ; aucune quantité source n'est imposée au nominal.
Le calendrier des engagements mérite un examen distinct : cet essai conserve
la date initiale comme borne de départ et peut la reporter, sans mécanisme
d'avancement selon une urgence aval révisée. Les quantités et dates de
commande industrielles ne sont pas identifiées par ces seuls résultats.

Preuves : `mrp_commitment_20261004/source_audit/comparison_C3.json` (260
rapprochements directs de photos pour les cinq couples principaux), registres
`validation/` indépendants, tests mémoire ciblés et manifestes natifs sous
`mrp_commitment_20261004/native`. Les échecs de C et C2 sont conservés.

Comparaison consultable : [référence et essais 2025](../../resultats/mrp_commitment_20261004/comparaison_reconciliee.html).
Les 16 tests ciblés passent. Le HTML a été rapproché des CSV par 660 096
comparaisons numériques, puis contrôlé dans le navigateur hors ligne
(98 896 vérifications). Ces contrôles certifient les calculs et l'affichage
contrôlés, pas l'adéquation de la règle aux décisions industrielles.
Le manifeste de livraison regroupe les preuves dans
`artifacts/testing/mrp_commitment_20261004/delivery.json`.

## Recherche de la règle manquante de mai — besoins ouverts et programme amont

État : **hypothèses testées sur des plans existants, pas de nouvelle règle
activée dans le nominal**. Preuves sous
`etudecas/artifacts/testing/mrp_safety_20261003/rule_search/`.

Le retrait de la seule réception H de 6 400 kg du 11 mai dans le plan du
4 mai, en conservant tous les autres H, I et J, laisse un stock K minimum
de **11 490,395 kg jusqu'à fin juin**. Ce test exclut la rupture imminente
comme explication suffisante ; il ne prouve pas que l'ordre est inutile.
Les autres réceptions sont maintenues dans ce contre-factuel.

Le test du besoin courant au **20 avril** apporte une distinction utile :
6 292,566 kg moins 169,888 kg consommés ce jour et 1 797,876 kg déjà
représentés dans les besoins restants donne **4 324,802 kg de complément
hypothétique de planification**. En conservant la protection de 20 jours
ouvrés (6 742,035 kg), le premier manque apparaît le 16 mai : 240,204 kg.
Il conduit à **un seul lot de 3 200 kg**, même en regroupant les besoins
jusqu'au créneau suivant (manque maximal 540,990 kg). Le créneau calculé
est départ le 23 avril, arrivée physique le 3 mai, disponibilité le 12 mai.
Ce calcul ne reproduit donc **ni les 6 400 kg ni le calendrier de la hausse
de stock observée entre les photos du 12 et du 19 mai**. Il explique une possibilité
d'anticipation, pas l'épisode complet. Le scénario qui ajoute aussi ce
complément à la sécurité peut produire 6 400 kg, mais cette double pression
n'a pas de justification métier établie et n'est pas retenue.

Deux mécanismes doivent être distingués :

1. **Hypothèse : besoins courants encore ouverts.** Le 20 avril, I courant vaut
   6 292,566 kg (`Feuille1!I15995`). Le moteur conserve pour cette semaine
   l'ancienne prévision future, et n'utilise pas cet agrégat comme retard
   industriel. Les besoins futurs fournis sont en revanche présents.
   Cet agrégat ne peut pas être ajouté chaque semaine aux consommations :
   il peut reporter des besoins déjà vus ou déjà servis dans le scénario.
2. **Continuité d'un approvisionnement affecté.** Les plans peuvent déplacer
   une quantité plutôt que la recréer selon le seul stock courant.
   Trois exemples arithmétiques : 773474 Gien, 6 400 kg du 20 avril au
   11 mai ; 693055 Avène, 600 kg du 16 mars au 6 avril ; 001848 Avène,
   6 000 kg du 8 juin au 29 juin. Les montants et les bilans sont
   compatibles avec des reports, sans prouver l'identité des commandes.

Le lien avec Gaillac est plus précis qu'une simple égalité de lots : dans
le plan du 13 avril, J Gaillac du 4 mai vaut déjà 6 400 kg mais I vaut zéro
(`J15005`, `I15005`), et H Gien du 11 mai vaut zéro (`H14966`). Dans le
plan du 20 avril, J Gaillac reste 6 400 kg, I devient 6 400 kg le 4 mai
(`J16036`, `I16036`) et H Gien devient 6 400 kg le 11 mai (`H15997`).
Cela soutient une **affectation datée du stock amont à un transfert**.
Cela ne démontre ni une identité de lot, ni un transport de sept jours,
ni une règle « tout expédier dès libération » : le plan précédent
présentait déjà cette disponibilité sans sortie immédiate correspondante.

### Contrat candidat commun, à tester avant activation

Pour des ordres identifiés dans le scénario, et non pour tous les H sources :

```text
reste à recevoir = quantité engagée − quantité déjà reçue − quantité annulée
besoin ouvert = quantité encore due, après rapprochement des besoins déjà servis
stock projeté(t) = disponible + libérations futures(t)
                  + restes à recevoir datés(t) − besoins ouverts et futurs(t)
nouveau besoin net(t) = max(0, protection(t) − stock projeté(t))
```

Une quantité déjà engagée est conservée et replanifiée si nécessaire ; une
simple proposition reste révisable. Une libération de stock J déjà physique
ne crée pas une seconde réception. Les libérations futures et les restes à
recevoir désignent des quantités disjointes : un lot déjà reçu mais retenu
en contrôle sort du reste à recevoir et n'est crédité qu'à sa libération.
Le retard ne doit pas être à la fois
soustrait comme besoin et ajouté automatiquement au stock de sécurité.
Pour un lot affecté à une destination, la disponibilité amont et le calendrier
de transport bornent la date réalisable ; le stock local positif n'est pas,
à lui seul, une preuve qu'il faut annuler cet engagement.

**Limites :** le moteur conserve déjà ses propres ordres fermes. L'écart peut
porter sur les besoins ouverts, le moment de l'engagement et l'affectation
amont ; il n'est pas démontré que le moteur supprime des ordres industriels.
Les sources ne déterminent pas encore une frontière universelle entre
proposition et engagement, ni la règle initiale produisant exactement
6 400 kg. Aucun gel automatique des 52 semaines de H n'est justifié.

## 773474 à Gien : décrochage de mai dans S25C — diagnostic du 3 octobre 2026

Le changement déterminant se situe entre les photos du **12 et du 19 mai** :

| Bilan en kg | Sources industrielles | Simulation S25C |
|---|---:|---:|
| Stock au premier rapprochement | 16 108 | 15 423,615 |
| Stock au second rapprochement | 21 452 | 13 788,228 |
| Variation nette | +5 344 | −1 635,388 |

L'écart augmente donc de 6 979,388 kg sur cette semaine. La simulation ne
reçoit aucun 773474 à Gien durant mai. Ses sorties entre ces deux points
sont 1 040,779 kg pour une fabrication de 268967 et 594,609 kg d'autres
usages **estimés**. Sur tout mai : 3 122,336 kg de BOM et 1 783,827 kg d'autres
usages, soit 4 906,163 kg sans réception. Le dernier arrivage est celui du
12 avril (3 200 kg) ; le suivant part le 28 mai, arrive physiquement le 7 juin
et devient utilisable le 16 juin, après les six jours ouvrés de réception.

Les plans sources annoncent en revanche 6 400 kg au repère hebdomadaire du
11 mai dès la version du 20 avril. La quantité reste présente dans quatre
versions : `Flow_Data_MRP_results.xlsx!Feuille1!H15997`, `H17022`, `H18031`,
`H19020`. La reconstruction `6 400 reçus − 1 056 sortis = +5 344 de stock`
est compatible avec les photos, mais ces dernières ne prouvent pas les deux
flux bruts ni leurs dates exactes.

La comparaison des versions du 13 et du 20 avril montre une révision précise :
le J courant reste à 14 597,2 kg ; le nouveau I courant de 6 292,566 kg égale
l'ancien I courant augmenté du besoin déjà prévu au 20 avril. L'entrée de
6 400 kg anciennement attendue au 20 avril n'est plus présente dans le nouveau
cumul H, puis apparaît au 11 mai. Le K du 11 mai reste exactement à
22 207,112 kg dans les deux versions. Cela soutient un report/rééchelonnement
de réception ; aucun identifiant ou statut ne prouve qu'il s'agit du même
ordre ferme. Aucun engagement initial Gien/mai correspondant n'a été trouvé
dans `Extract_En_cours`.

Dans le simulateur, l'absence d'arrivée ne vient pas d'un manque disponible
à Gaillac : son stock disponible atteint 22,4 tonnes dès le 7 mai. Le MRP
considère Gien suffisamment couvert. Au 4 mai, il projette encore environ
12,362 tonnes en fin mai à partir des besoins alors connus, pour une réserve
d'environ 2,996 tonnes ; il ne déclenche donc pas de transfert proche. Les
20 jours de sécurité du composant à Gien sont inchangés. Le retour du PF à
25 jours a aussi déplacé ses fabrications : trois consommations de 773474
ont lieu les 1er, 13 et 27 mai, alors que TF les avait réalisées à d'autres
dates. Le correctif calendrier avance un arrivage au 12 avril et réduit le
creux par rapport à S25 sans calendrier ; il ne le crée pas.

Un oracle en lecture seule a également recalculé la couverture des vingt jours
ouvrés à chaque date future, au lieu de garder la réserve du jour constante.
Avec le plan connu au 4 mai, le premier franchissement apparaît le 19 juin
(8 025,392 kg projetés contre 8 987,099 kg protégés) ; avec celui du 18 mai,
il apparaît le 17 juin (9 443,361 contre 9 584,111 kg). Dans les deux cas,
le départ admissible est le 28 mai, l'arrivée physique le 7 juin et la
disponibilité le 16 juin. Cette variante de protection avance le transfert
projeté, mais ne reconstitue toujours pas l'entrée de mai des sources.

Le point à élucider reste la règle qui maintient et reporte l'approvisionnement
industriel malgré une couverture proche jugée suffisante par notre calcul,
ainsi que le périmètre des besoins/engagements comparés. Les « autres usages »
hypothétiques accentuent la baisse simulée ; ils ne sont pas établis par ce
seul épisode. Ce diagnostic ne modifie ni moteur, ni sécurité, ni résultat.

Preuves en lecture seule : [bilan physique](../../artifacts/testing/mrp_safety_20261003/may_773474/report.json),
[cellules et replanifications sources](../../artifacts/testing/mrp_safety_20261003/may_773474/sources/report.json),
[décisions et oracle prospectif](../../artifacts/testing/mrp_safety_20261003/may_773474/engine/report.json).

## Retour à la sécurité historique pour 2025 — décision du 3 octobre 2026

L'utilisateur demande de revenir à la sécurité antérieure pour la comparaison
2025. L'ancien fichier `Extract_Données_Complémentaires.xlsx`, onglet
`Politique de Stock MRP`, fournit **25 jours ouvrés pour 268967 à Muret en
E26**, et **20 jours pour 268091 en E25**. Le scénario S25 reprend TF en
remplaçant uniquement les 60 jours de 268967 par 25 ; 268091 reste à 20.
Le choix de validité pour 2025 vient de cette décision utilisateur : l'ancien
fichier, pris seul, n'indique pas sa date d'effet. Le fichier récent à 60 jours
et les résultats TF sont conservés.

Les quinze jours ouvrés de contrôle de 268967 restent à Gien avant expédition.
Les stocks initiaux, commandes engagées, besoins, nomenclatures, tailles de lots
et temps de transport restent inchangés. Les autres usages estimés de 773474
ne deviennent ni nuls ni certains ; la demande physique reconstruite depuis
les plans MRP reste une estimation distincte des ventes observées.

Un second scénario S25C isole le calendrier exact des propositions, via
`dated_supply_calendar_policy = exact_release_calendar_v1` : pour un besoin
à la date B, choisir le dernier lancement autorisé L dont la disponibilité
est au plus tard B ; si aucun lancement causal ne respecte B, choisir le
premier encore possible et exposer le retard. La disponibilité se calcule
depuis chaque L, avec le transport ou la marge de planification existante,
puis les jours ouvrés de contrôle. Le calendrier ne déplace aucune réception
déjà engagée et ne crée pas de consommation de sécurité supplémentaire.
`tau_process` reste une marge de planification, pas une durée physique prouvée.

Les créneaux de départ respectent simultanément la revue de la paire et
celle de la liaison, comme l'exécuteur : lorsque ces grilles sont ancrées
au jour zéro, le pas commun est leur PPCM. Deux revues de 4 et 6 jours
donnent ainsi des départs J12, J24, etc. Les lancements de fabrication et
leur marge existante évitent la fermeture ; le contrôle qualité peut finir
pendant cette fermeture de fabrication. Les capacités et matières restent
des contraintes d'exécution, pas une garantie donnée par ce calendrier.

Les deux simulations de 365 jours sont terminées : S25 en 411,031 secondes,
S25C en 418,079 secondes, avec entrées et code stables pendant chaque calcul.
Les corrections intermédiaires entre ces calculs concernent l'oracle d'un
test, un libellé conditionnel et l'intersection des grilles dans la seule
option calendrier ; le chemin scalaire de S25 n'a pas été modifié.

Écart absolu moyen aux 52 photos hebdomadaires de 2025, comparées à la
clôture de la veille ; les unités des différents articles ne sont pas sommées :

| Article / site | Unité | TF, 60 jours | S25, 25 jours | S25C, 25 jours et calendrier |
|---|---|---:|---:|---:|
| 268967 / Muret | UN | 281 227 | 167 844 | 169 917 |
| 268091 / Muret | UN | 253 625 | 253 625 | 253 625 |
| 773474 / Gien | KG | 4 954 | 5 001 | 4 253 |
| 773474 / Gaillac | KG | 7 077 | 7 385 | 7 015 |
| 693055 / Avène | KG | 448 | 448 | 545 |
| 693055 / Gaillac | KG | 989 | 989 | 919 |

S25 améliore 3 couples article/site, en dégrade 8 et en laisse 18 identiques
par rapport à TF. S25C améliore 11 couples par rapport à S25, en dégrade 8
et en laisse 10 identiques ; par rapport à TF, le bilan est 10/10/9.
L'amélioration principale est la réduction du surstock PF de fin d'année,
pas une amélioration uniforme. Avec S25, l'écart moyen de 268967 au deuxième
trimestre passe de 116 058 à 335 792 UN, alors qu'au quatrième trimestre il
baisse de 505 688 à 66 201 UN. Le calendrier corrigé ne résout donc pas à lui
seul le sous-stock simulé du printemps, ni la divergence inchangée de 268091.

La comparaison conserve les trois courbes et les données sources. La variante
calendrier est proposée pour sa cohérence des dates ; ses dégradations locales,
notamment 693055 à Avène, restent visibles. Aucun changement de nomenclature,
de ventes ou de partage de consommation n'a été ajouté pour absorber ces écarts.

Contrôles exécutés : 22 cas mémoire ciblés réussis, qualification CSV de TF,
S25 et S25C, 660 114 rapprochements numériques du contenu affiché et 98 896
vérifications navigateur hors ligne. L'oracle indépendant vérifie également
98 380 propositions sur les dix paires concernées par le calendrier, ainsi
que 12 775 bilans article/site quotidiens par calcul. Les 131 propositions
explicitement tardives restent des décisions projetées, pas des retards de
livraisons industrielles observés. Les demandes et services clients annuels
restent identiques ; 268967 fabrique 2 802 800 UN dans S25 et S25C, contre
3 341 800 dans TF, soit cinq lots de moins. Au rapprochement de la photo du
29 décembre, les deux variantes donnent 483 906 UN pour 492 888 observées,
contre 1 022 906 dans TF. Le premier passage des tests conservait
une attente erronée (zéro au lieu de cinq unités de réception engagée restant
non allouées après réemploi d'un surplus) ; l'oracle manuel indépendant a
confirmé le moteur, puis le test a été corrigé et réexécuté. Le premier
lancement navigateur, bloqué sur son canal de communication, reste enregistré
comme échec ; la relance locale autorisée est réussie. Aucun test de fichiers
factices, de modification de dates ou de suppression simulée n'a été exécuté.

Recette de l'essai : `artifacts/testing/mrp_safety_20261003/study.py` ;
[comparaison interactive](../../resultats/mrp_safety_20261003/comparaison.html),
[preuve des valeurs historiques](../../artifacts/testing/mrp_safety_20261003/sources/report.json),
[contre-vérification S25C](../../artifacts/testing/mrp_safety_20261003/validation/postrun_S25C.json),
[manifeste de livraison](../../artifacts/testing/mrp_safety_20261003/delivery.json).

## Audit complet de la divergence — 3 octobre 2026, après TF

Cette passe repart des sources et des décisions, sans modifier le moteur ni
recalculer une autre variante. Elle couvre la chaîne 773474 Gaillac → Gien →
268967 Muret, les décisions de fabrication, stocks retenus et transports,
avec 268091 et 693055 comme contrôles. Les sources, calculs et bilans ont été
analysés par trois agents distincts ; le parent a vérifié les prévisions et
la demande du scénario. **L'arithmétique est vérifiable ; plusieurs
interprétations industrielles restent des hypothèses.**

### Le mécanisme principal du surstock est reconstitué

Notre moteur transforme les 60 jours ouvrés de sécurité de 268967 en une
quantité de réserve au dépôt. Cette réserve est recalculée chaque jour,
mais reste constante à toutes les dates futures d'une même projection de
364 jours. Elle passe notamment de **539 330 UN le 1er juin à 711 392 le
8 juin**, puis à 1 011 460 le 3 août. La fabrication cherche à préserver ce
plancher, même avec une réserve PF nulle à Gien.

La hausse des prévisions existe dans le fichier industriel : entre les
versions du 1er et du 8 juin, la somme des besoins futurs de 268967 passe
de **2 303 905 à 4 243 446 UN**. Sur exactement les mêmes dates, la hausse
reste de 1 924 951 UN, dont 966 665 en 2025 et 958 286 en 2026. Il ne s'agit
donc pas d'un simple décalage de l'horizon. Les sommes de fenêtres calendaires
glissantes du rapport parent diffèrent légèrement de ces sommes de périodes
entières ; leurs bornes sont explicites et ne doivent pas être mélangées.

| Lancement TF | Besoin net reconstitué | Fabrication engagée |
|---|---:|---:|
| 9 juin | 136 697 UN à couvrir à l'usine | 215 600 UN, deux lots |
| 4 août | 274 144 requis − 107 800 déjà retenus = 166 344 UN | 215 600 UN, deux lots |
| 30 décembre | 856 717 de réserve + 271 377 de sorties datées − 1 013 401 au dépôt − 107 800 retenus = 6 893 UN | 107 800 UN, un lot pour janvier |

Les dates et phases de chaque calcul sont détaillées dans le rapport moteur.
Les quinze jours ouvrés augmentent l'anticipation des lancements. La réserve
peut ensuite redescendre : du 21 au 22 juin, 815 197 → 650 579 UN, alors que
431 200 UN sont déjà fabriquées et retenues. Des propositions futures peuvent
être révisées ; un lot physique ne disparaît pas quand la prévision baisse.
C'est un effet de la dépendance à l'état, et non une identité matière fausse.

**Ce qui reste non établi est l'équivalence de ce plancher avec la règle
industrielle.** Dans les seules périodes futures, K est inférieur aux besoins
des douze semaines suivantes dans 2 018 des 2 078 fenêtres complètes de
268967. Cela ne valide pas notre plancher permanent. Cela ne prouve pas non
plus une absence de sécurité : I et K peuvent déjà refléter un décalage ou
un autre traitement de protection. L'ancien paramètre de 25 jours n'a pas de
date de validité connue ; aucune baisse de 60 à 25 n'est justifiée ici.

La documentation SAP distingue l'anticipation des dates par un délai de
sécurité des méthodes de couverture/stock cible. Ces mécanismes servent à
construire des hypothèses testables, sans identifier le logiciel du client :
[Safety Time](https://help.sap.com/docs/SAP_ERP_SPV/85d3fce10e264972a0155c8b46ecf93b/8aaace5314894208e10000000a174cb4.html),
[Time-Dependent Days of Supply](https://help.sap.com/docs/SAP_S4HANA_CLOUD/2bba750d1e124e1ea2a039bb1cd9b6c5/93ce499f81a14233a986e0fd1e9e60a9.html).

### Deux frontières de données doivent être clarifiées

**Demande prévue et sorties physiques.** Pour 268967, le scénario D/TF
exécute 3 214 333 UN estimées à partir d'une version MRP antérieure à chaque
semaine. `demand_PF.xlsx!Demande`, colonne « real demand », contient
1 575 986 UN ; les colonnes prévision et réel y sont égales pour chaque
semaine, sans année explicite dans les en-têtes. Pour 268091, ces totaux sont
respectivement 3 522 364 et 3 576 442. La portée de l'ancien fichier fait
l'objet d'une question utilisateur ; aucune des deux demandes ne doit être
présentée arbitrairement comme les ventes exécutées de 2025. Les 5 178 valeurs
I normalisées et leurs dates correspondent exactement aux cellules Excel,
et aucune addition des versions successives n'a été trouvée.

**Stock physique, disponibilité et division de gestion.** Du 16 au 23 juin,
la photo 268967 baisse de 165 803 UN. Les plans du 15 et du 22 juin montrent :

`−165 803 = −57 483 de J courant −107 756 de J futur −564 de résidu photo/J`.

La tranche de 107 756 UN, attendue disponible le 6 juillet dans `J23634`, est
explicitement nulle dans le plan suivant (`J24648`). Cette révision d'une
tranche de stock est prouvée ; sa cause physique et son identité de lot ne
le sont pas. Elle ne démontre pas 107 756 ventes supplémentaires, une perte
ou une libération précise. Le J futur est enregistré sous la division Muret,
alors que les quinze jours de libération sont confirmés à Gien. Les photos PF
n'existent également que sous Muret. Cela oblige à distinguer lieu physique
et division de gestion ; cela ne prouve pas que les photos incluent Gien.

### Le cas 773474 contient une autre hypothèse importante

Dans TF à Gien, la consommation comprend **32 264,14 kg de BOM** et
**50 541,77 kg d'autres usages estimés**, soit 61,03 % du total pour cette
seconde catégorie. Son origine est une fraction de 56,696 % calculée sur le
premier plan, et appliquée ensuite aux besoins révisés. Le graphe marque
explicitement le partage de 773474 comme hypothétique, à la différence des
articles dont le partage a été confirmé. Les données ne prouvent pas cette
fraction d'usage physique par d'autres produits.

Un simple décalage de dates ne ferme toutefois pas l'écart entre I773474 et
les réceptions H268967 converties par la BOM : dans une fenêtre alignée du
plan du 29 juin, 80,755 t contre 34,105 t équivalentes. H au dépôt n'est pas
une fabrication usine ; cette différence ne suffit donc pas à prouver un
partage ou un double compte. Autre signature précise : les 1 775 positions
futures positives I773474 sont toutes multiples de 1 048,760994 kg, contre
1 040,7786004 kg par lot PF dans la BOM, soit +0,767 %. L'origine de cet
écart reste à expliquer ; la BOM n'a pas été corrigée pour l'absorber.

**773474 ne bloque aucune fabrication de 268967 dans TF.** Les contraintes
actives portent sur 344135 et 042342. Modifier seulement le niveau de stock
773474 ne rapprochera donc pas automatiquement le stock PF. Cette distinction
explique pourquoi une meilleure courbe amont n'entraîne pas la même amélioration
à Muret dans cet essai.

### Ce que les contrôles écartent, et leurs limites

- Aucun deuxième stock de sécurité PF à Gien ; sa protection vaut zéro sur 365 jours.
- Aucun oubli démontré des lots retenus : l'exemple du 4 août déduit bien 107 800 UN.
- Aucun double engagement dans les 394 identités contrôlées, ni double remontée
  DC → usine dans les 52 instantanés de chacun des deux calculs.
- Aucun cumul « prévision source + profil nominal » ; le moteur sélectionne
  une source ou un repli. Les propositions à long terme ne sont pas toutes exécutées.
- Le décalage photo J/J−1 ne suffit pas : l'écart moyen 268967 passe de 281 227
  à 275 736 UN, sans résoudre le surstock. Les essais de phase hebdomadaire sur
  50 photos communes conservent un écart entre 259 371 et 293 084 UN.
- Les 318 photos, 624 intervalles TF/D, 7 300 bilans de sites et 2 920 bilans
  réseau sont vérifiés ; les contrôles portent sur les conventions et registres,
  pas sur une identification de l'ERP ou des ventes.

Les deux lots supplémentaires fabriqués dans TF restent retenus fin 2025 :
TF fabrique 31 lots et en libère 29, D en fabrique et libère 29. L'écart de
107 800 UN au dépôt au 31 décembre vient aussi d'un lot D encore en transit.
Comparer seulement fabrication annuelle et stock dépôt sans les états
intermédiaires donne donc une explication incomplète.

Limites techniques déjà démontrées : propositions de transfert non recalées
sur les créneaux hebdomadaires, délais ouvrés futurs convertis en une durée
scalaire à la décision (écart possible de quelques jours), et valeurs de
transport partiellement estimées. Elles doivent être corrigées séparément ;
elles ne démontrent pas à elles seules le surstock d'environ 500 000 UN.
Pour 268091, l'essai conserve l'exception de 20 jours demandée précédemment,
alors que la politique source la plus récente indique zéro. Pour 773474 à
Gaillac, placer les 33 jours après fabrication reste une hypothèse de calendrier.

### Priorité de correction issue de cet audit

1. Fixer le contrat de chaque donnée : demande commerciale, I prévisionnel,
   J par disponibilité, photo physique et division de gestion. Conserver
   séparément les éléments non identifiés et les paramètres utilisateur.
2. Confronter, sur les mêmes versions MRP, les règles de protection datée et
   de couverture aux H/K sources, avec les 60 jours inchangés. Vérifier
   notamment si I contient déjà un effet de protection avant de l'appliquer
   une seconde fois. Tester les mêmes règles sur les autres références.
3. Revoir les autres usages estimés de 773474 et les contraintes physiques
   réellement actives, sans attribuer automatiquement tout résidu à un partage.
4. Une fois ces conventions discriminées, corriger le calendrier commun des
   transferts et comparer une année complète. Les réceptions H ne deviennent
   pas des mouvements physiques rejoués pour faire correspondre les courbes.

Preuves : [prévisions et demande](../../artifacts/testing/mrp_full_audit_20261003/report.json),
[sources et cellules](../../artifacts/testing/mrp_full_audit_20261003/sources/report.json),
[décisions du moteur](../../artifacts/testing/mrp_full_audit_20261003/engine/report.json),
[bilans indépendants](../../artifacts/testing/mrp_full_audit_20261003/validation/report.json),
[contre-vérification des décisions](../../artifacts/testing/mrp_full_audit_20261003/validation/crosscheck.json),
[manifeste de cette passe](../../artifacts/testing/mrp_full_audit_20261003/manifest.json).

## Libération à Gien et transports internes — confirmation du 3 octobre 2026

L'utilisateur a confirmé que les **15 jours ouvrés de contrôle de 268967 se
passent à Gien, avant expédition**. L'essai T reprend intégralement le graphe D
et ajoute ce seul paramètre à la politique générique de libération des PF.
Le moteur n'a pas besoin d'une nouvelle règle propre à cet article : la même
politique assure déjà les dix jours à Avène pour 268091.

Pour chaque nouveau lot achevé à la date `G` :

1. Le lot physique existe à l'usine, mais reste indisponible pendant le contrôle.
2. `I = ajouter_jours_ouvrés(G, délai_de_libération)` ; le jour G est exclu,
   les samedis et dimanches ne comptent pas, aucun férié n'est inventé.
3. L'expédition utilise uniquement les quantités libérées, au premier départ
   autorisé et physiquement réalisable. La réception ajoute le temps de transport.
4. Le lot retenu constitue déjà un engagement daté dans le MRP : il ne déclenche
   pas une seconde fabrication. Les OF initiaux gardent leurs dates source.

Pendant le contrôle, ce stock appartient donc à Gien ; après départ il est en
transit ; après réception il appartient à Muret. **Aucun second traitement de
quinze jours n'est ajouté à Muret.** `tau_process = 3` reste une convention de
planification, pas une nouvelle durée physique de fabrication. La planification
inclut le délai de libération, mais convertit encore les jours ouvrés en une
durée calculée à la décision puis réutilisée pour ses propositions futures ;
leurs dates peuvent ainsi différer de quelques jours du calendrier exact.
L'exécution physique calcule chaque libération avec le calendrier exact.

| Liaison | Transport appliqué | Traitement séparé | Niveau de preuve du transport |
|---|---:|---|---|
| 773474, Gaillac → Gien | 10 jours calendaires | 6 jours ouvrés après arrivée à Gien | Référence FIA ; durée de camion seule non établie |
| 693055, Gaillac → Avène | 7 jours calendaires | 7 jours ouvrés après arrivée à Avène | Hypothèse de transport ; les 70 jours FIA restent une référence d'approvisionnement distincte |
| 268967, Gien → Muret | 2 jours calendaires | **15 jours ouvrés avant départ de Gien** | Estimation du modèle, pas un délai observé |
| 268091, Avène → Muret | 2 jours calendaires | 10 jours ouvrés avant départ d'Avène | Estimation du modèle, pas un délai observé |

Les deux trajets PF utilisent la convention déterministe existante : moyenne
estimée de 2,5 jours arrondie à 2. T conserve ce choix. Les traitements amont
des semi-finis à Gaillac restent ceux de D : 33 jours ouvrés pour 773474 et
28 pour 693055. La localisation de ces traitements ne doit pas être déduite
du seul paramètre de réception ; leurs conventions antérieures restent explicites.

Un défaut distinct est confirmé dans D : l'exécution des transferts depuis
Gaillac autorise un départ tous les sept jours, mais les propositions MRP ne
sont pas recalées sur ces créneaux. **208 décisions quotidiennes** demandent
une quantité positive hors créneau, avec zéro transfert exécuté ce jour-là.
Ce sont des décisions de planification répétées, pas 208 commandes industrielles
perdues. Les 12 760 propositions futures hors créneau ne sont pas non plus des
ordres exécutés. Le jour hebdomadaire du modèle n'est pas prouvé par les sources.
Ce défaut est documenté séparément et n'est pas mélangé à l'essai T.

Recette isolée : [study.py](../../artifacts/testing/mrp_transport_20261003/study.py).
Audits conservés : [provenance des délais](../../artifacts/testing/mrp_transport_20261003/sources/report.json),
[application dans le moteur D](../../artifacts/testing/mrp_transport_20261003/engine/report.json),
[écart de calendrier des départs](../../artifacts/testing/mrp_transport_20261003/engine/cadence.json).
Le diagnostic D ci-dessous décrit l'état antérieur à la confirmation et reste
conservé comme référence ; son interrogation sur le lieu des quinze jours est
désormais levée par la réponse utilisateur.

### Résultat de l'essai T sur les stocks 2025

La correction du parcours physique ne résout pas le surstock. Avec la même
demande client estimée, la fabrication nouvelle de 268967 passe de 29 à
31 lots de 107 800 UN, soit de 3 126 200 à 3 341 800 UN. Les sorties clients
restent identiques. Le délai supplémentaire modifie l'anticipation et les
lancements MRP ; il ne décale donc pas seulement les réceptions historiques.

Écart absolu moyen aux photos, comparées à la clôture simulée de la veille :

| Article/site | Unité | D, avant correction | T, quinze jours à Gien |
|---|---|---:|---:|
| 268967 / Muret | UN | 274 815 | 281 227 |
| 773474 / Gien | kg | 5 272 | 4 954 |
| 773474 / Gaillac | kg | 6 892 | 7 077 |
| 268091 / Muret | UN | 253 625 | 253 625 |
| 693055 / Avène | kg | 448 | 448 |
| 693055 / Gaillac | kg | 989 | 989 |

Sur les 29 couples comparables : six s'améliorent, cinq se dégradent et
dix-huit restent identiques. Pour 268967, le troisième trimestre s'améliore,
mais pas le quatrième. Les trimestres sans photo restent non observés,
jamais remplacés par un écart nul.

Au **28 décembre**, T contient 1 022 906 UN à Muret, contre 915 106 dans D ;
la photo source du 29 décembre vaut 492 888 UN. T conserve en plus 107 800 UN
retenues à Gien. Avec les 19 010 UN en transit vers le client, le total PF du
réseau passe de 934 116 à 1 149 716 UN. Il s'agit donc aussi d'une hausse du
stock total, pas uniquement d'un déplacement entre sites. Ces valeurs ne
justifient pas de réduire arbitrairement les 60 jours de sécurité source.

### Anomalie détectée puis corrigée dans le contrôleur de généalogie

La première qualification de T a refusé 63 rapprochements. Le contrôleur
reconnaissait le marqueur texte historique d'une fabrication sur plusieurs
jours, mais pas le même contrat au format JSON des lots retenus en contrôle.
Il comparait alors les composants liés au lot fini avec la seule consommation
du jour d'achèvement, au lieu de la consommation de sa campagne.

Exemple : pour le lot parent `LOT-00000100`, campagne
`CMP-00000016-M-1430-item:268967-D86`, les 640,469842 consommés à J86 et les
1 245,941331 consommés à J87 donnent bien les 1 886,411173 attribués au lot
fini à J87 (unité KG du registre). Deux rapprochements indépendants confirment
les **1 109 groupes campagne/parent/site/article** ; le second vérifie aussi
1 220 étapes chronologiques sans allocation antérieure à la consommation.

Le correctif reconnaît la clé JSON `semantics` exacte, en préservant les
contrôles quantitatifs existants. Un simple commentaire, le statut « retenu »,
une autre version ou un JSON invalide ne suffisent pas. Les dix nouveaux cas
de contrat s'exécutent entièrement en mémoire ; avec les douze cas de
libération et d'expédition, **22 tests ciblés passent**. Aucun fichier factice,
changement de date ou essai d'altération n'est utilisé.

Le calcul T et son refus initial restent conservés. Le calcul TF utilise les
mêmes paramètres pour régénérer les diagnostics avec le contrôleur corrigé ;
aucun CSV physique de T n'est retouché. Preuves :
[qualification initiale refusée](../../artifacts/testing/mrp_transport_20261003/native/qualify-3980a63332a243df8218795fe1948c52/manifest.json),
[diagnostic du contrôleur](../../artifacts/testing/mrp_transport_20261003/engine/quality_wip_audit_fix.json),
[contre-vérification matière](../../artifacts/testing/mrp_transport_20261003/validation/lot_attribution_T.json).

La nouvelle qualification de TF passe, ainsi que celle de D conservé. Le HTML
reprend exactement les résultats métier de T : les **40 CSV métier sont
identiques octet par octet**. Seul le diagnostic change : les 63 erreurs de
lecture disparaissent, les quatre informations de traçabilité sont conservées.
La [contre-vérification indépendante TF](../../artifacts/testing/mrp_transport_20261003/validation/postrun_TF.json)
confirme les bilans, les calendriers, les unités physiques entières et les
22 OF initiaux. Le HTML
est rapproché numériquement des CSV et des sources sur 511 826 comparaisons,
plus 4 380 valeurs de demande et service. Le parcours navigateur hors ligne
effectue 78 407 contrôles sans erreur JavaScript ni requête réseau ; les
captures de 268967/Muret et de 773474/Gien ont aussi été relues visuellement.
Ces contrôles prouvent les conventions programmées et l'affichage couvert,
**pas la reproduction satisfaisante du stock industriel de 268967**.

[Ouvrir la comparaison D/T 2025](../../resultats/mrp_transport_20261003/comparaison.html)
— [gate de vérification](../../artifacts/testing/mrp_transport_20261003/native/gate-436181d627454a36ab4bcbb9e56421a3/manifest.json).
La prochaine correction distincte concerne le calendrier des propositions de
transfert ; l'explication du niveau de stock nécessite toujours de rapprocher
la protection source et les engagements datés, sans abaisser arbitrairement
les jours de sécurité pour faire rejoindre les courbes.

## Pourquoi le surstock de 268967 persiste — diagnostic du 3 octobre 2026

Cette passe analyse les calculs UQ et D conservés. Elle ne modifie pas le moteur
et ne constitue pas une nouvelle simulation. Les analyses du code, des sources
et des bilans ont été réalisées séparément, puis contre-vérifiées.

### Le mécanisme qui maintient le stock élevé est identifié

Dans D, les 60 jours ouvrés de sécurité du dépôt sont transformés en une
quantité de protection :

`R(d) = max(F, somme des besoins datés entre d et d + 60 jours ouvrés)`.

Pour 268967, F vaut zéro. La conversion donne 82 à 84 jours calendaires selon
la date. Cette quantité est maintenue comme plancher dans chaque projection de
364 jours, puis recalculée le lendemain. Le moteur propose de produire pour
couvrir les besoins tout en conservant ce plancher. Les besoins clients plus
élevés de D conduisent donc aussi à davantage de fabrication : 29 lots de
107 800 UN, contre 14 dans UQ. La hausse des sorties ne vide pas durablement
une réserve que le moteur cherche à reconstituer.

Exemple complet, clôture du **3 août** :

| Terme | UN |
|---|---:|
| Protection calculée | 1 011 460 |
| Stock disponible à Muret | 979 303 |
| Manque avant les consommations suivantes | 32 157 |
| Lot PF demandé puis fabriqué le 4 août | 107 800 |

Le **28 décembre**, le stock physique de D se décompose exactement ainsi :

`915 106 = 831 952 de protection + 83 154 au-dessus de cette protection`.

La photo du 29 décembre vaut 492 888 UN. L'écart de 422 218 UN représente
3,917 lots, mais ne permet pas d'identifier « quatre ordres inutiles » :
dates, besoins et engagements interviennent dans chaque décision. Le
dépassement du plancher à cette date est inférieur à un lot ; le niveau élevé
du plancher constitue donc le principal mécanisme du stock élevé simulé.

Les bilans quotidiens du dépôt et du réseau se ferment. La cible de sécurité
du PF à Gien reste nulle sur les 365 jours : aucun deuxième plancher usine
n'est démontré. Aucun double crédit de fabrication ou de réception n'est
détecté dans les contrôles réalisés. Les besoins arrivés de D consomment la
prévision hebdomadaire entièrement ; cela découle de la construction de cet
essai et ne prouve pas les ventes industrielles.

### Un paramètre source est présent mais non appliqué : 15 jours de réception

`Flow_Data_MRP_results.xlsx!Feuille1!E593` indique **15 jours de traitement**
pour 268967 à la division 1920. Le graphe D conserve cette donnée dans les
métadonnées de réception fournisseurs, mais le moteur ignore cette paire dans
ce parcours, réservé aux achats externes. Aucune politique active de retenue
du PF ne la reprend. Sur toute l'année, le délai de planification fabrication
reste trois jours (`tau_process`, convention de planification), le trajet
Gien–Muret deux jours et le stock PF retenu zéro aux deux sites.

Cas réel du calcul D : le lot `LOT-00000916`, de 107 800 UN, est fabriqué et
expédié le 4 août (`SHIP-00000498`), puis reçu et disponible à Muret le 6 août.
Avec quinze jours ouvrés, à fabrication inchangée et sans jours fériés ajoutés :

- Traitement à Gien : libération le 25 août, arrivée Muret le 27 août.
- Traitement à Muret : présence physique le 6 août, disponibilité le 27 août.

Le fichier identifie la division du paramètre, mais ne suffit pas à prouver
l'emplacement physique du traitement. La convention donnée pour 268091 à
Avène ne démontre pas à elle seule celle de 268967 à Gien. Le raccordement
de ces 15 jours manque ; son emplacement doit être explicite avant un essai.

Un simple contre-calcul de localisation, sans refaire les décisions, laisse
deux lots reçus à Muret en décembre en attente à Gien au 28 décembre :
215 600 UN. La soustraction donnerait 699 506 UN à Muret, encore 206 618
au-dessus de la photo. **Ce n'est pas une simulation corrigée** : intégrer le
délai à la planification peut avancer les fabrications, et les expéditions et
le service doivent aussi être recalculés. Une retenue au dépôt ne retire
rien de son stock physique. Aucun déplacement de courbe n'est donc présenté
comme solution validée.

### Ce que les sources permettent de conclure sur la sécurité

Les 60 jours sont bien affectés à Muret, pas à Gien. L'ancien fichier indique
25 jours, sans date de validité. Ni le passage à 25 ni une autre diminution
n'est justifié par cet audit. Les politiques actuelles et le comportement de
2025 doivent être distingués tant que cette date reste inconnue.

Le stock projeté K ne doit pas être assimilé à une photo physique. Le plan
du 7 septembre et la photo du 8 septembre donnent précisément :

`458 998 = K 130 324 + (I courant − H courant) 111 253 + J futur 215 696 + écart photo 1 725`.

Le J futur représente du stock déjà présent mais disponible plus tard. Par
ailleurs, les réceptions H de 268967 vont jusqu'à la dernière ou l'avant-
dernière semaine dans les 52 versions : un export limité aux premiers mois
n'explique pas l'écart. Aucun K futur de cet article n'est négatif. H reste
une réception projetée, dont le statut ferme ou modifiable n'est pas identifié.

Le K courant est inférieur aux douze semaines suivantes de besoins dans
39 versions sur 52, et aux cinq semaines suivantes dans 19 versions. Cela
ne démontre ni l'absence de sécurité ni l'algorithme ERP. Les paramètres,
contraintes, engagements et états doivent être rapprochés ensemble.

La documentation SAP distingue le délai de sécurité, qui anticipe les besoins
sur l'axe des dates, des méthodes de stock de sécurité. C'est une référence
de fonctionnement possible, pas une identification du logiciel industriel :
[Safety Time / Actual Range of Coverage](https://help.sap.com/docs/SAP_ERP_SPV/85d3fce10e264972a0155c8b46ecf93b/8aaace5314894208e10000000a174cb4.html).
Avancer les mêmes besoins de 60 jours ne supprimerait d'ailleurs pas
automatiquement le manque immédiat de 32 157 UN du 3 août. Une autre formule
ne doit pas être annoncée comme solution sans comparaison datée.

La prochaine correction vérifiable concerne le raccordement des quinze
jours à la planification et à la disponibilité physique, avec lieu déclaré.
La recherche de la règle de sécurité doit ensuite comparer, sur une même
version connue, quel besoin chaque réception projetée protège. Elle doit
préserver les 60 jours, distinguer engagements et propositions et être
contre-testée sur 268091 et les matières déjà étudiées. L'objectif d'un an
de couverture de la chaîne médicament reste global ; il ne devient pas un
an de stock au dépôt ni une attribution de tout l'amont partagé à ce PF.

Preuves : [chronologie et bilans](../../artifacts/testing/mrp_surstock_20261003/chronology.json),
[calculs du moteur](../../artifacts/testing/mrp_surstock_20261003/engine/report.json),
[paramètre des 15 jours](../../artifacts/testing/mrp_surstock_20261003/engine/reception15.json),
[cellules sources et 52 plans](../../artifacts/testing/mrp_surstock_20261003/sources/report.json),
[oracle indépendant](../../artifacts/testing/mrp_surstock_20261003/validation/report.json).

## Cohérence des besoins clients 2025 — essai du 3 octobre 2026

### Pourquoi cet essai est nécessaire

La référence UQ utilise les prévisions industrielles glissantes pour planifier,
mais conserve le profil commercial de `demand_PF.xlsx` pour les demandes clients
exécutées. Pour 268967, ce dernier représente 1 575 986 UN sur l'année, alors
que certains horizons industriels de 52 semaines dépassent quatre millions.
Cette combinaison peut conduire à produire et protéger davantage que ce que
le scénario client écoule. Il ne s'agit pas d'une addition des deux demandes,
mais d'une incohérence possible entre leurs volumes et calendriers.

Il serait tout aussi incorrect d'assimiler la colonne I de chaque semaine
courante à des ventes : la somme des 52 positions courantes atteint 7 561 861 UN
pour 268967 et 26 427 566 UN pour 268091. Les besoins agrégés et échus ne sont
pas un registre d'expéditions. Les photos de stock ne suffisent pas davantage
à isoler des sorties brutes, puisqu'elles combinent entrées et sorties.

### Règle commune testée, avec ses conditions

Le mode optionnel `customer_demand_policy = source_prior_week_need_v1` construit
un **scénario de besoins clients estimés**, identique dans son principe pour
268967 et 268091. Il ne prétend pas reconstituer les ventes industrielles ni
démontrer une règle propre à l'ERP.

Pour la semaine `w` et une date de décision `d` :

1. Choisir la version `v` la plus récente donnant I pour cette même semaine,
   avec `v <= d` et `v < début(w)`. Une seule version contribue.
2. Figer `Q_w = I(v,w)` pour toute la semaine. Les révisions publiées pendant
   cette semaine ne réécrivent pas ses demandes exécutées. Un zéro explicite
   reste un zéro ; ce n'est pas une donnée manquante.
3. Répartir la quantité entière en sept jours :
   `demande_j = floor(Q_w × (j+1)/7) − floor(Q_w × j/7)`, pour `j = 0...6`.
   Les jours hors 2025 ne sont pas reportés sur les autres jours de l'année.
4. Sans version antérieure pour la période exacte, conserver le profil
   commercial avec arrondi cumulatif entier et marquer le repli. Cela concerne
   les onze premiers jours de 2025 pour les deux PF. Le calendrier de semaine
   commençant le dimanche reste la convention de cet essai, pas une nouvelle
   conclusion sur la datation industrielle.
5. La couverture client à deux jours utilise uniquement les versions connues
   à la date de décision. Les demandes effectivement arrivées consomment la
   prévision une seule fois ; les reliquats restent séparés. La planification
   à 52 semaines garde son propre profil prévisionnel et son repli commercial
   d'origine, sans lire les futures réalisations du scénario.

Les quantités annuelles de ce scénario sont **3 214 333 UN pour 268967** et
**3 522 364 UN pour 268091**. Le registre `customer_demand_daily.csv` rend
chaque jour vérifiable : version connue, ligne source, période, quantité
hebdomadaire, arrondi et éventuel repli. La carte distingue besoins du scénario,
service exécuté et prévisions d'une seule version source sélectionnée. Sa
courbe hebdomadaire clients exclut la position I courante agrégée ; celle-ci
reste consultable dans l'onglet MRP.

L'essai D reprend exactement le graphe UQ, avec ce seul indicateur optionnel.
Il conserve stocks initiaux, OF en cours, sécurité, prix, lots, nomenclatures,
délais, calendriers et hypothèses de disponibilité. Il couvre 365 jours
physiques avec projection glissante de 52 semaines. Le mode est limité au
périmètre déterministe validé ; il n'est pas activé dans les autres scénarios.

### Limites à conserver dans l'interprétation

Même avec cette estimation des besoins, huit intervalles de photos pour
268967 et seize pour 268091 impliqueraient des entrées négatives si toutes les
variations étaient attribuées à ces seules sorties. La demande estimée ne
reconstitue donc pas tous les mouvements réels. Les entrées H restent des
prévisions, et un stock J différé peut être déjà présent physiquement.

La signification du plancher de sécurité reste une autre question : les
projections K sources passent parfois sous la couverture des jours de sécurité
affichés dans la politique actuelle. Cela ne permet pas de modifier ces jours
ni d'imposer une règle alternative sans preuve. Une amélioration de l'essai D
ne suffirait pas à valider tous les calculs de sécurité et de replanification.

Sources et contre-calculs :
[audit des profils](../../artifacts/testing/mrp_customer_2025_20261003/sources/report.json),
[contexte de sécurité](../../artifacts/testing/mrp_customer_2025_20261003/sources/safety_context.json),
[oracle des demandes et anticipations](../../artifacts/testing/mrp_customer_2025_20261003/validation/implementation_oracle.json).

### Résultats : une amélioration partielle, pas un remplacement validé

L'essai D de 365 jours termine en **664 s**, code retour nul et empreintes
des données/code inchangées pendant le calcul. La
[comparaison interactive UQ/D](../../resultats/mrp_customer_2025_20261003/comparaison.html)
s'ouvre sur 268967 à Muret ; l'onglet Fabrications présente aussi les besoins
clients, le service et les prévisions hebdomadaires.

| Article/site | Unité | Écart absolu moyen UQ | Écart absolu moyen D |
|---|---:|---:|---:|
| 268967 / Muret | UN | 345 951,62 | 274 814,96 |
| 268091 / Muret | UN | 203 369,77 | 253 625,44 |
| 773474 / Gaillac | kg | 7 076,92 | 6 892,31 |
| 773474 / Gien | kg | 5 159,94 | 5 272,43 |
| 693055 / Gaillac | kg | 976,73 | 988,65 |
| 693055 / Avène | kg | 471,47 | 448,13 |

Sur 29 couples comparables, 19 écarts diminuent, neuf augmentent et un reste
identique. L'amélioration annuelle de 268967 est de **20,6 %** ; son premier
trimestre se dégrade toutefois de 20 100 à 51 571 UN de MAE. Pour 268091,
l'erreur annuelle augmente de **24,7 %**, malgré une amélioration du dernier
trimestre. Il ne faut donc pas remplacer automatiquement la référence par D.

Pour 268967, les nouvelles fabrications passent de **1 509 200 à 3 126 200 UN**,
soit quinze lots supplémentaires de 107 800 UN. Les départs du dépôt passent
de **1 581 112 à 3 233 343 UN**. La majeure partie des sorties supplémentaires
est donc compensée par de nouvelles productions. Le service client vaut
respectivement 1 575 985 et 3 214 333 UN ; il reste distinct des départs du
dépôt à cause des deux jours de transport.

Au rapprochement du 29 décembre, la clôture simulée du 28 décembre vaut
**915 106 UN dans D**, contre **1 034 748 dans UQ**, pour une photo source de
**492 888 UN**. Le surplus diminue de 541 860 à **422 218 UN**, mais reste très
élevé. La seule incohérence de profil client n'explique donc pas tout le
surstock : le dimensionnement et les déclenchements de production, dont la
protection projetée, restent à rapprocher des plans source. Aucun jour de
sécurité n'a été abaissé pour obtenir ces résultats.

L'indépendance de cet essai a une limite métier : les autres usages estimés
des composants partagés restent ceux de UQ. Pour 773474, la consommation pour
268967 augmente de 14 570,90 à 30 182,58 kg, tandis que les autres usages
restent à 50 541,77 kg. Ce maintien isole le changement client ; il ne prouve
pas la consommation industrielle totale de toutes les formulations.

L'[oracle indépendant](../../artifacts/testing/mrp_customer_2025_20261003/validation/customer_profile_D.json)
confirme 730 demandes journalières et leurs provenances, 708 consommations de
prévisions et les libérations des lots. Les
[bilans du réseau](../../artifacts/testing/mrp_customer_2025_20261003/validation/summary_D.json)
contrôlent notamment 48 bilans mensuels, 726 couvertures client, 1 456
rapprochements du plan précédent et 24 455 traces de paramètres de sécurité.
Aucune quantité physique fractionnaire en UN ni double consommation n'est
détectée dans ce périmètre. Ces contrôles ne certifient pas la calibration.

Les **17 tests ciblés en mémoire**, les qualifications CSV des deux scénarios
et la revue navigateur hors ligne réussissent sur l'état final du code.
La carte est rapprochée de 511 803 valeurs des sources/CSV, complétées par
4 380 valeurs de demande et service. Le navigateur vérifie 78 407 points et
interactions numériques, sans erreur JavaScript ni requête réseau ; les
captures des deux PF et de la nouvelle courbe hebdomadaire ont été examinées.
[Gate final](../../artifacts/testing/mrp_customer_2025_20261003/native/gate-c787d1acd1ea4f008da5791f5422632f/manifest.json).

Une correction purement descriptive a suivi le calcul : deux anciens libellés
de `summary.demand_execution_contract` ont été rendus conditionnels pour les
prochaines régénérations. Les résultats D conservés n'ont pas été réécrits ;
leur politique effective est déjà correctement identifiée dans
`policy.customer_demand_policy`, les CSV et le texte affiché dans la carte.
La [contre-vérification de cette correction](../../artifacts/testing/mrp_customer_2025_20261003/validation/metadata_fix_review.json)
reconstitue exactement le moteur exécuté et confirme que seuls ces deux
libellés diffèrent : aucun calcul ni CSV ne change. Les tests et qualifications
ont ensuite été renouvelés. Le
[manifeste de livraison](../../artifacts/testing/mrp_customer_2025_20261003/delivery.json)
distingue ces deux états de code et conserve les chemins de reproduction.

## Règles communes par relation — correction du 3 octobre 2026

### Résultats 2025 et statut des essais

Deux nouvelles simulations de **365 jours**, U puis UQ, ont terminé avec code
retour nul et empreintes des sources/code inchangées. Les références W7 et M
restent intactes. La [comparaison interactive](../../resultats/mrp_chain_uniform_20261003/comparaison.html)
affiche W7 et UQ au départ, avec M et U sélectionnables. UQ est un candidat
comparatif, pas une nouvelle calibration industrielle validée.

Écart absolu moyen aux 52 photos de stock, rapprochées de la clôture simulée
précédente ; les unités sont conservées séparément :

| Article/site | Unité | W7 | U, calcul corrigé | UQ, avec hypothèse 33 jours |
|---|---:|---:|---:|---:|
| 773474 / Gaillac | kg | 14 769,23 | 14 584,62 | 7 076,92 |
| 773474 / Gien | kg | 5 344,76 | 5 111,61 | 5 159,94 |
| 268967 / Muret | UN | 681 790,08 | 345 951,62 | 345 951,62 |
| 268091 / Muret | UN | 189 662,17 | 203 369,77 | 203 369,77 |
| 693055 / Gaillac | kg | 953,27 | 976,73 | 976,73 |
| 693055 / Avène | kg | 467,66 | 471,47 | 471,47 |

Sur les **29 couples avec photos**, UQ améliore 12 écarts, en dégrade 16 et en
laisse un inchangé par rapport à W7. Par rapport à M, les comptes sont 14, 14
et 1. L'ajout des 33 jours seul, UQ contre U, améliore Gaillac/773474 et
Gaillac/021081, dégrade légèrement Gien/773474 et laisse 26 couples identiques.
Les deux PF et le service client sont identiques entre U et UQ. Ces résultats
justifient les corrections de calcul prouvées, pas une adoption globale des
hypothèses de calibration.

À Gaillac, l'hypothèse des 33 jours améliore surtout la fin d'année : écart
du quatrième trimestre de 22 153,85 kg dans U à 4 676,92 kg dans UQ. Elle
dégrade toutefois le premier trimestre, de 2 215,38 à 8 123,08 kg. Au 28 décembre,
la source distingue **16 t courantes + 19,2 t disponibles ultérieurement**,
contre **28,8 t entièrement disponibles** dans UQ. Le niveau physique plus
proche ne valide donc pas la répartition des états ni toutes les dates.

Contrôles indépendants : 48 bilans mensuels par essai, 1 456 rapprochements
entre cible de fabrication exécutée et plan précédent, 24 455 comparaisons de
paramètres de sécurité, lots 693055 et 773474 rapprochés de leurs consommations
et libérations. Dans UQ, 25 nouveaux lots de 3,2 t respectent chacun les 33
jours ouvrés, sans deuxième fabrication ni deuxième consommation BOM ; les
22 OF initiaux conservent leurs dates et quantités explicites.
Les 27 tests ciblés en mémoire réussissent. Ces contrôles certifient les
conventions programmées, pas la calibration.

La réconciliation complète de fin de journée coûte une seconde passe de
planification : U a pris **607 s**, UQ **617 s**, contre **349 s** pour M lors
de son exécution antérieure. Cette comparaison de durées n'est pas un benchmark
contrôlé ; elle signale un coût de calcul à optimiser, sans supprimer la
réconciliation qui évite le double lancement.

Preuves numériques : [U](../../artifacts/testing/mrp_chain_uniform_20261003/validation/summary_U.json),
[UQ](../../artifacts/testing/mrp_chain_uniform_20261003/validation/summary_UQ.json),
[libérations 773474](../../artifacts/testing/mrp_chain_uniform_20261003/validation/release773_UQ.json).
Le [gate final](../../artifacts/testing/mrp_chain_uniform_20261003/native/gate-65c94d3b75684818b4694c6fdf75a891/manifest.json)
réussit : doctor, 27 tests ciblés, quatre qualifications CSV et navigateur hors
ligne. La comparaison vérifie 807 931 valeurs contre les CSV et sources, puis
65 596 contrôles numériques dans le navigateur, sans erreur JavaScript ni
requête réseau. Les six sélections de stock, filtres temporels, onglets et
fabrications des quatre scénarios sont couverts ; ce n'est pas une preuve de
toutes les interactions possibles. Les deux suivis de lots historiques restent
accessibles et n'ont pas été modifiés par cette livraison.

### Contrat commun et conditions d'application

La configuration `chain_planning_policy = dated_relation_consistent_v1`
réconcilie le calcul daté sur toute la topologie. Le rôle est déterminé par
**article, site et liaison** : un même site peut fabriquer un article, acheter
une matière pour sa production et redistribuer une autre matière. Le nom du
site ne choisit pas une formule spéciale. Les besoins remontent de l'aval vers
l'amont ; les livraisons physiques suivent le sens inverse.

| Relation de besoins | Déclenchement et quantité | Exécution physique |
|---|---|---|
| Client → centre de distribution | Demandes clients du scénario et prévision résiduelle connue, sans compter deux fois les commandes qui consomment la prévision | Le dépôt sert sur stock disponible ; le non-servi reste un retard, jamais un stock négatif ; les demandes du scénario ne prouvent pas les ventes industrielles exécutées |
| Dépôt → usine PF | Besoin net du dépôt après déduction de son stock et des engagements en transit ; propagation du complément à l'usine | Fabrication en lots admissibles, puis expédition des PF libérés vers le dépôt |
| Usine PF → usine de semi-finis | Nomenclature des fabrications prévues, complétée des autres besoins industriels réconciliés ; stock et transferts engagés déjà déduits | Transfert interne sur stock utilisable, réception puis disponibilité ; le site amont fabrique son seul complément net |
| Usine PF → fournisseurs de matières ou emballages | Même calcul d'achat daté, avec délai fournisseur, réception, sécurité et règle de quantité de l'article | Engagement d'achat, livraison physique, puis disponibilité ; consommation BOM lors de la fabrication exécutée |
| Usine de semi-finis → fournisseurs de matières | Même calcul d'achat que pour l'usine PF ; besoins issus de la nomenclature des semi-finis et autres usages explicitement représentés | Mêmes états d'achat, réception et consommation ; aucun régime spécial lié au nom Gaillac |
| Site de stockage-distribution de matières → fournisseurs | Consommations propres + besoins de redistribution aval, réconciliés une fois ; fabrication seulement si un processus produit cet article sur ce site | Une redistribution déplace une matière existante ; elle ne crée pas une production ni une consommation supplémentaire |

Pour chaque article/site, à une date de décision `d`, le plan avance sur les
**364 jours de l'horizon glissant de 52 semaines**, même si l'exécution et la
comparaison des photos s'arrêtent au 31 décembre 2025. Seules les informations
connues à `d` servent à décider. Les versions MRP successives ne sont jamais
additionnées. Une prévision future n'est pas une commande exécutée.

Les cinq règles de calcul sont les suivantes. `B_t` désigne les besoins datés
réconciliés ; `E_t`, les engagements qui deviennent utilisables à `t` ; `P_t`,
le solde **projeté** ; `R_t`, la protection de stock ; `Q_t`, la proposition.
Le stock physique, le stock indisponible et le transit restent séparés.

1. **Besoins, sans double compte.** Au client :
   `Prévision restante = max(0, prévision connue − commandes déjà arrivées dans la période)`.
   En amont : `B = besoins BOM propres + transferts aval + complément des autres usages`.
   Le complément industriel exclut ce que les besoins propres représentent
   déjà ; les estimations d'autres usages ne deviennent pas des observations.
2. **Sécurité selon la convention déclarée.** En mode plancher :
   `R(d) = max(stock fixe source, somme B_t pour d < t ≤ d + S_calendaires(d))`.
   `S_calendaires(d)` traduit les jours source du lundi au vendredi, à la date
   du calcul. Un retard déjà échu reste dans les besoins, sans être ajouté une
   seconde fois à la réserve. Un lot de fabrication ponctuel n'est jamais
   multiplié comme une consommation quotidienne. Cette protection est calculée
   à la date de décision, conservée dans ce plan puis réévaluée au calcul
   suivant ; son profil futur ne constitue pas une règle ERP démontrée.
   Pour les achats en mode
   anticipation, les besoins sont avancés des jours de sécurité ; on ne rajoute
   pas un second plancher issu des mêmes jours.
3. **Besoin net et lot admissible.** Lorsque les engagements affectés au besoin
   sont disponibles à temps, la récurrence s'écrit :
   `N_t = max(0, R_t − (P_(t−1) + E_t − B_t))` ;
   `Q_t = arrondir_selon_la_règle_de_lot(N_t)` ;
   `P_t = P_(t−1) + E_t + Q_t − B_t`.
   Une quantité standard, un minimum, un multiple et un maximum sont des
   paramètres distincts. Une campagne peut contenir plusieurs lots physiques.
   Les quantités physiques en UN restent entières. Le solde projeté peut
   révéler un manque ; il ne donne pas l'autorisation de consommer un stock
   physique négatif. **Avant de créer une proposition, le moteur affecte aussi
   les engagements tardifs déjà conservés.** La part qu'ils couvrent n'est
   pas achetée une seconde fois ; le retard reste visible dans la chronologie
   et les manques projetés. Ainsi, besoin de 100 à J5 et engagement de 100 à J10
   donnent zéro nouvel achat et 100 unités en retard de cinq jours. Il ne faut
   pas appliquer la seule récurrence ci-dessus en ignorant cette affectation,
   ni déplacer fictivement la disponibilité de J10 vers J5.
4. **Dates et type d'approvisionnement.** En achat avec anticipation :
   `disponibilité protégée = date besoin − sécurité ouvrée` ;
   `livraison visée = disponibilité protégée − traitement réception ouvré` ;
   `commande visée = livraison visée − délai fournisseur`.
   Le délai fournisseur n'est compté qu'une fois. Le choix principal/secours
   utilise les offres et règles de sourcing configurées ; un prix ou une
   quantité différents ne sont pas inventés. En fabrication, le moteur utilise
   ses lots, capacités connues et convention de planification existante ; une
   capacité absente ne devient pas une division par un débit quasi nul.
5. **Réconciliation après exécution.**
   `P_physique_fin = P_physique_début + réceptions + fabrications − expéditions − consommations`.
   Le transfert retire à l'origine et crédite le transit ou la destination.
   Après ces mouvements, le plan de fabrication est reconstruit sur toute la
   topologie avant la prochaine décision. Les anciens besoins amont couverts
   par un transfert ne doivent pas provoquer un nouvel ordre. Cette seconde
   passe recalcule des propositions ; elle n'exécute aucun achat, transport ou OF.

Les délais et stocks de sécurité sources, le calendrier lundi–vendredi, les
lots, les prix, les stocks initiaux et les nomenclatures sont conservés.
La fabrication de 693055 à Gaillac reste représentée avec l'intrant virtuel
explicitement autorisé. Les règles commerciales ne transforment pas cet intrant
en une matière industrielle identifiée. `tau_process` reste une convention de
planification ; aucune durée physique nouvelle n'en est déduite.

L'essai U ne localise pas les 33 jours source de 773474/Gaillac. L'essai UQ
ajoute **uniquement l'hypothèse de leur application après chaque nouvelle
fabrication**, par le même mécanisme de disponibilité que pour 693055 :
création physique du lot, retenue, puis libération une fois. Les 33 jours sont
confirmés par `Flow_Data_MRP_results.xlsx!Feuille1!E968` ; leur affectation
intégrale à cette phase reste une hypothèse. Les dates explicites des OF
initiaux sont conservées, sans leur ajouter ces jours une seconde fois.
Les 15 jours de 268967/Muret restent documentés sans emplacement physique
inventé. Les six jours ouvrés de réception 773474/Gien sont déjà appliqués.
Les transferts internes initiaux non identifiés ne sont pas
créés à partir de toutes les entrées H projetées. La cible d'environ un an
concerne la chaîne entière et doit tenir compte du périmètre partagé des matières.

Recette de l'essai isolé :
`etudecas/artifacts/testing/mrp_chain_uniform_20261003/prepared_U.json`.
Elle conserve intégralement le graphe M précédent et ajoute seulement la
politique commune. La référence W7 et l'essai M antérieur restent disponibles
pour distinguer correction du calcul et représentation de la fabrication 693055.
La recette `prepared_UQ.json` du même dossier reprend U et ajoute uniquement
la ligne de libération 773474/33 jours ouvrés décrite ci-dessus.

Les achats externes conservent leur calcul daté commun existant : le contrôle
des 8 030 lignes quotidiennes des 22 couples achetés ne démontre pas le défaut
« lot de fabrication multiplié comme débit quotidien » sur ces achats.
Leurs choix de fournisseurs configurés restent distincts des règles de calcul :
uniformiser ne signifie pas remplacer les politiques de sourcing documentées
par un choix systématique du fournisseur le moins cher.

Le champ `summary.policy.chain_planning_policy` décrit les règles effectivement
activées et alimente la notice de la comparaison. Certains libellés historiques
des autres blocs de métadonnées décrivent encore l'ancien calcul ; ils ne
prévalent pas sur ce contrat explicite. Le tableau prévisionnel hebdomadaire
MRP précède les mouvements physiques du jour ; le CSV
`production_execution_snapshot_daily.csv` décrit la réconciliation de fin de
journée utilisée par la fabrication suivante. Ce CSV expose les totaux, pas
tous les besoins individuels : l'oracle manuel vérifie donc séparément la
fenêtre de sécurité et les bilans des exécutions complètes.

## 773474 : Gaillac → Gien → 268967 à Muret — audit complet du 3 octobre 2026

**Section historique :** les constats ci-dessous décrivent W7 avant les
corrections U/UQ présentées plus haut. Les mentions « reste à corriger »
reflètent l'état de cet audit, et non celui des essais actuels.

**La chaîne présente plusieurs défauts de pilotage distincts.** Cet audit
porte sur W7 conservé, première année 2025, dont les CSV ont été requalifiés.
Il ne remplace pas cette référence et ne relance aucune simulation. Les
changements expérimentaux de fabrication de 693055 ne sont pas utilisés ici.
Trois lectures séparées couvrent sources, règles exécutées et bilans physiques.

| Stock, aux 52 photos comparables | Source moyenne | Physique W7 moyen | Écart absolu moyen |
|---|---:|---:|---:|
| 773474 / Gaillac | 25 169,23 kg | 39 938,46 kg | 14 769,23 kg |
| 773474 / Gien | 17 251,34 kg | 14 515,34 kg | 5 344,76 kg |
| 268967 / Muret | 670 474,56 UN | 1 348 285,44 UN | 681 790,08 UN |

Les photos sont rapprochées de la clôture simulée précédente. Aucun stock
source de **268967 à Gien** n'est fourni : son absence ne signifie pas un
stock réel nul. La fabrication et les transferts simulés y sont vérifiables.

**Défaut supplémentaire de date de campagne, reproduit exactement.** Le
5 janvier, le plan de Gaillac place les 6 400 kg restants de la campagne au
jour `6 400 000 000 000 004`. La capacité absente est remplacée par zéro,
puis la formule divise les 6 400 000 G restants par `max(0, 1e-9)`.
L'exécution physique termine pourtant les deux lots les 6 et 7 janvier.
La date erronée entre dans le planificateur et faisait aussi planter l'onglet
MRP. La vue signale désormais l'anomalie sans modifier les séries ni inventer
une date de remplacement. **Le calcul moteur reste à corriger ; son impact
quantitatif n'a pas été mesuré par une nouvelle simulation.** Une capacité
inconnue ne doit pas devenir une capacité quasi nulle. La correction devra
respecter la cadence d'exécution existante sans inventer une capacité source.
[Preuve de la date et des lots exécutés](../../artifacts/testing/mrp_773474_chain_20261003/engine/invalid_campaign_date_addendum.json).

**1. Gaillac fabrique trop tôt sous l'effet d'une sécurité mal dimensionnée.**
Au 1er janvier, la quantité de besoins datés de transfert est nulle, mais le
signal virtuel MPS représente un lot PF de 107 800 UN chaque jour. La BOM
correspondante vaut 1 040,7786004 kg de 773474 par jour, contre 24,74366299 kg/j
pour la prévision BOM moyenne. Le moteur utilise le premier taux dans sa
protection de 20 jours ouvrés, soit 28 jours calendaires à cette date :

`Cible = 1 040,7786004 × 28 = 29 141,8008112 kg`

`Complément = max(0, 29 141,8008112 − 9 600 − 3 200) = 16 341,8008112 kg`

`Lancement arrondi = ceil(16 341,8008112 / 3 200) × 3 200 = 19 200 kg`

La campagne produit six lots du 2 au 7 janvier ; la production du PF ne
commence que le 20 mars. **Le défaut est l'assiette de la sécurité, pas les
20 jours source.** Un besoin ponctuel de lot n'est pas un rythme quotidien
à prolonger sur toute la fenêtre de protection.

**2. Gien reçoit trop tard au début, malgré la matière disponible à Gaillac.**
W7 ne reçoit aucun 773474 en janvier, sa première réception étant le
5 février. Le plan du 5 janvier prévoit 6 400 kg au repère du 12 janvier
(`Feuille1!H942`). Les photos du 13 et du 20 janvier passent de 13 566,4 à
16 773,2 kg : +3 206,8 kg nets, sans pouvoir en déduire une réception brute
isolée. Le carnet initial comporte un OF Gaillac, pas les transferts internes
identifiés. Le délai prévisionnel FIA de 10 jours est traité comme un trajet
physique, puis six jours ouvrés sont ajoutés à Gien ; sa décomposition réelle
reste à établir. Rejouer tous les H comme des commandes fermes ne serait pas
une correction justifiée.

**3. Le surplus du PF vient de ses lancements, pas d'une pénurie de 773474.**
Les 365 jours de registres ne montrent aucun blocage de fabrication imputable
à 773474. Les 56 journées de contraintes matière portent sur 344135, 333362,
042342 et 730384 ; elles concernent des campagnes actives, y compris les jours
sans nouveau lancement. Elles ne représentent pas 56 nouveaux OF bloqués.
La consommation propre au PF est de 23 937,91 kg de 773474, à laquelle
s'ajoutent 50 541,77 kg d'autres usages **estimés**, non confirmés comme une
ventilation industrielle. Le partage ne doit pas être confondu avec une BOM
mesurée pour d'autres formulations.

Le 12 septembre, une prévision de 77 965 UN moins 10 751,57 UN de demandes
déjà arrivées laisse 67 213,43 UN sur le dernier jour futur de la semaine.
La moyenne courte, mêlée à la prévision suivante, atteint 19 642,94 UN/j.
Le maximum de cette moyenne et de la moyenne de couverture est extrapolé
sur 84 jours calendaires, correspondant aux 60 jours ouvrés de sécurité :
la cible monte à **1 650 006,86 UN**. Avec seulement la moyenne de couverture,
le contre-calcul vaudrait 1 199 080,41 UN ; ce n'est pas une correction simulée.
Le lendemain, une campagne de cinq lots, **539 000 UN**, démarre sur le plan
de la veille alors que la cible recalculée descend à 1 131 123,59 UN.
Les cinq lots sont achevés les jours 255, 256, 258, 260 et 265. Le résidu
de prévision non réalisé ne constitue pas une commande client ferme.

**4. Après transfert, un ancien besoin de fabrication peut être recompté.**
Le moteur conserve son plan avant les expéditions. Le lendemain, il reprend
les besoins usine conservés, avec le stock usine maintenant diminué, sans
réconcilier les transferts qui ont déjà couvert ces besoins au dépôt.
Contre-exemple exécuté en mémoire : 100 UN à l'usine couvrent un besoin
de transfert de 100, donc aucune fabrication. Après leur expédition, conserver
le besoin usine de 100 avec un stock usine nul conduit le helper à proposer
100 nouvelles UN ; ramener le besoin déjà satisfait à zéro redonne zéro.
La matière totale est conservée : c'est un défaut de cohérence des besoins.
L'épisode du 12–13 septembre montre aussi 107 800 UN expédiées après le plan
et un lancement passant de 431 200 à 539 000 UN. **L'effet exact de ce seul
mécanisme n'est pas isolé**, car le jour de planification avance également.

**5. Les disponibilités physiques restent incomplètes.** Les colonnes sources
prévoient 33 jours de réception à Gaillac, six à Gien et 15 à Muret pour le PF.
À Gaillac, J courant et J futur valent chacun 12 615,38 kg en moyenne ; J futur
est positif dans 51 versions sur 52. À Gien, J futur vaut seulement 61,54 kg
en moyenne, avec une seule version positive. À Muret, J futur moyen vaut
143 974,58 UN, positif dans 46 versions. Ce sont des compartiments hebdomadaires,
pas un relevé journalier de statut qualité. Dans W7, seuls les 3 200 kg de l'OF
initial Gaillac sont retenus entre G du 24 janvier et I du 3 mars ; les nouvelles
productions 773474 et 268967 sont immédiatement disponibles à leur achèvement.
La politique de disponibilité initiale ne couvre que 693055. Pour 773474,
le plan du 5 janvier indique bien J968 = 6 400 kg et J970 = 3 200 kg au 26 janvier,
soit les 9 600 kg de la photo du 6 janvier. Leur rétroprojection au 1er janvier
resterait une hypothèse. Les 15 jours au dépôt ne prouvent pas à eux seuls où
se situe physiquement le PF pendant ce traitement.

Les bilans annuels indépendants ferment :

- Gaillac, kg : `9 600 + 99 200 fabriqués + 3 200 OF initial − 73 600 expédiés = 38 400`.
- Gien, kg : `14 593 + 73 600 reçus − 23 937,91 BOM − 50 541,77 autres usages = 13 713,32`.
- PF Gien, UN : `0 + 2 479 400 fabriquées − 2 479 400 expédiées = 0` en fin d'année.
- PF Muret, UN : `1 101 534 + 2 479 400 reçues − 1 581 112 expédiées = 1 999 822`.

Les expéditions du dépôt ne sont pas les ventes servies le même jour : le
registre client sert 1 575 985 UN, le reliquat expédié reste au niveau client.
Une meilleure disponibilité de 773474 ne réduit pas mécaniquement ce surplus
de PF. La cible utilisateur d'environ un an porte sur la **chaîne entière** ;
elle ne se rajoute pas à chaque site. Sa vérification exige une allocation des
matières partagées et un périmètre de demande cohérent, pas une somme KG + UN.

Priorités de correction commune : réconcilier les besoins après transfert ;
calculer les sécurités sur les besoins datés cohérents avec les fabrications ;
éviter l'extrapolation d'un reliquat hebdomadaire sur toute la sécurité ;
qualifier les états et engagements initiaux. Conserver les jours source, les
lots source et les prévisions connues ; mesurer ensuite l'effet par un essai
2025 séparé, sans prétendre ici avoir déjà corrigé ou calibré ces règles.

[Vue interactive de la chaîne](../../resultats/mrp_773474_chain_20261003/comparaison.html) ·
[Synthèse et preuves](../../artifacts/testing/mrp_773474_chain_20261003/analysis.json) ·
[Sources, version corrigée du tri des photos](../../artifacts/testing/mrp_773474_chain_20261003/sources/report_v2.json) ·
[Bilans indépendants](../../artifacts/testing/mrp_773474_chain_20261003/validation/report.json) ·
[Vérification des deux mécanismes](../../artifacts/testing/mrp_773474_chain_20261003/validation/episodes.json) ·
[Contre-calcul indépendant de la date invalide](../../artifacts/testing/mrp_773474_chain_20261003/validation/invalid_date_check.json).

La qualification CSV et le navigateur hors ligne passent sur le code stabilisé.
Le navigateur vérifie 12 587 comparaisons numériques, les trois stocks, les
deux productions, les filtres et le signalement de la date invalide ; aucune
erreur JavaScript ne subsiste dans ce parcours. Les 48 bilans mensuels ont été
recalculés séparément. Ces contrôles prouvent la cohérence des données affichées
et des bilans, **pas la calibration des règles industrielles**.
[Manifeste de qualification](../../artifacts/testing/mrp_773474_chain_20261003/native/gate-da73141bb63a445185506bb365d5c032/manifest.json) ·
[Livraison de l'audit](../../artifacts/testing/mrp_773474_chain_20261003/delivery.json).

## 693055 à Gaillac — fabrication confirmée et intrant virtuel, 3 octobre 2026

L'utilisateur confirme que **693055 est fabriqué à Gaillac**, mais que les
matières amont ne sont pas fournies. Il autorise leur représentation fictive.
Gaillac cumule donc ici fabrication, stockage et redistribution vers Avène.
L'essai **M**, isolé sur 365 jours en 2025, remplace l'apport amont simplifié
de W7 par un processus de fabrication ; il ne cumule pas les deux apports.
La comparaison antérieure W7 reste conservée.

| Règle de l'essai | Statut et condition |
|---|---|
| Fabriquer 693055 à Gaillac | Fonction du site confirmée par l'utilisateur. Le MRP produit des propositions puis des lancements ; une proposition seule ne crée aucun stock. |
| Produire des lots complets de 600 kg | Taille provenant de `Flow_Data_Inventory_and_Replenishment_rules.xlsx`, onglet `Taile de Lot`, E5. Une campagne peut comprendre plusieurs lots. |
| Consommer un intrant virtuel par lot | `VIRTUAL_693055_INPUT`, un jeton entier UN par lot de 600 kg. C'est un marqueur technique de nomenclature manquante, pas un rendement massique ni une matière industrielle identifiée. |
| Distinguer fabrication physique et disponibilité | À la fin d'un lot, créer une seule fois ses 600 kg physiques. Les retenir, puis libérer le même lot après 28 jours lundi–vendredi. Aucune expédition ni consommation de ce lot avant sa libération. |
| Conserver les dates explicites des ordres initiaux | L'OF initial de 600 kg garde sa date physique du 27 janvier et sa disponibilité du 25 février. Ne pas lui appliquer une seconde fois les 28 jours ni prélever une seconde recette virtuelle. |

Le paramètre de 28 jours vient de la colonne E du MRP à Gaillac, notamment
`Feuille1!E785:E787` ; le calendrier lundi–vendredi est confirmé par
l'utilisateur. **L'appliquer après la fin de fabrication est la convention
de représentation testée ici**, pas une mesure fournie du cycle industriel.
Le bilan est `stock physique = disponible + réservé + retenu`. La libération
change le statut des 600 kg sans nouvelle entrée physique.

La recette, le rendement, le coût et la capacité industriels restent inconnus.
Les 730 jetons initiaux sont une borne technique du scénario annuel et de
son horizon de projection, pas un stock réel. Aucun fournisseur ni achat
externe n'est créé pour cet intrant. Sa valorisation et le coût de ce
processus valent techniquement zéro, **au sens « non estimé »**, pas
« fabrication gratuite ». Les coûts de fabrication totaux ne sont donc pas
industriellement complets. Le contrôle des sorties confirme l'absence d'achat
virtuel, de frais de détention du jeton et de coût de conversion inventé.
Le compteur brut `inventory_total` inclut toutefois ces jetons techniques :
il ne doit pas être interprété comme un volume de stock industriel. Les
comparaisons article/site présentées ne les additionnent pas aux matières.
L'exécution garde la convention existante d'au
plus un lot fixe par processus et par jour ; `tau_process = 3` conserve son
rôle de planification. Aucune durée physique ou capacité mesurée n'est déduite.
Le jeton entier est vérifié pour des lots complets exécutés en une journée ;
son utilisation avec des lots fractionnés par une future contrainte de
capacité nécessitera une qualification distincte.

Les paramètres W7 d'Avène, le trajet hypothétique de 7 jours, le pas
hypothétique de transfert de 600 kg et le procédé 773474 sont conservés.
La passe source trouve 519 correspondances exactes sur 699 positions
futures en décalant de 70 jours les besoins de Gaillac vers les entrées
prévues à Avène. Ce sont des positions de plans successifs, pas 699 commandes
indépendantes. Ce décalage de planification n'est ni une durée de transport
observée ni un paramètre ajouté dans cet essai.

**Résultat de l'essai M : représentation vérifiée, rapprochement industriel
insuffisant.** La simulation de 365 jours a terminé en 349,44 secondes, avec
sources et code inchangés. Les 28 tests ciblés passent. La qualification CSV
et le contrôle indépendant retrouvent 24 lots nouveaux de 600 kg, 24 jetons
consommés et 706 restants. Chaque libération intervient après 28 jours
ouvrés, sans seconde création de matière ni utilisation anticipée ; l'OF
initial reste à ses dates sources. L'erreur maximale de rapprochement du
registre physique est inférieure à 0,000001 kg.

| Écart absolu moyen aux 52 photos de 2025 | W7 conservé | Essai M |
|---|---:|---:|
| 693055 à Gaillac, année | 953,27 kg | 1 009,81 kg |
| Gaillac, premier trimestre | 884,62 kg | 547,69 kg |
| Gaillac, deuxième trimestre | 1 533,08 kg | 594,62 kg |
| Gaillac, troisième trimestre | 933,08 kg | 783,85 kg |
| Gaillac, quatrième trimestre | 462,31 kg | 2 113,08 kg |
| 693055 à Avène, année | 467,66 kg | 533,11 kg |

La comparaison utilise la clôture simulée précédant chaque photo. Les 27
autres couples comparables sont identiques, ainsi que le service client et
les trajectoires des produits finis. M améliore les trois premiers
trimestres de Gaillac mais surévalue fortement le quatrième. En fin d'année,
il porte 1 800 kg retenus à Gaillac ; leur simple présence n'est pas étayée
par les photos ni par J futur, nul dans les plans depuis le 24 août.
Au 28 décembre, les 2 400 kg simulés (600 disponibles et 1 800 retenus)
contrastent avec les 10 kg de la photo du 29 décembre.
**M reste un essai séparé, pas une meilleure référence validée.** La
fabrication est désormais représentable ; ses dates physiques et le temps
effectivement passé en libération restent à mieux identifier. Ne pas
supprimer les 28 jours à une date choisie uniquement pour ajuster la courbe.

[Recette de reproduction](../../artifacts/testing/mrp_693055_release_20261003/study.py) ·
[Paramètres de l'essai](../../artifacts/testing/mrp_693055_release_20261003/prepared_M.json) ·
[Analyse source des décalages](../../artifacts/testing/mrp_693055_release_20261003/sources/report.json) ·
[Contrôle indépendant](../../artifacts/testing/mrp_693055_release_20261003/validation/final_M.json) ·
[Analyse des épisodes et des coûts](../../artifacts/testing/mrp_693055_release_20261003/validation/episodes_M.json) ·
[Comparaison HTML](../../resultats/mrp_693055_fabrication_20261003/comparaison.html) ·
[Gate technique réussi](../../artifacts/testing/mrp_693055_release_20261003/native/gate-892b385a1791499785cb4ebb2b635fd0/manifest.json).

L'affichage a fait l'objet de 511 444 rapprochements de valeurs avec les CSV
et les sources, puis d'un parcours hors ligne des courbes et sélections,
y compris fabrication M et apport simplifié W7 affichés ensemble. Ces
contrôles certifient le périmètre vérifié de calcul et d'affichage, pas la
reproduction des règles industrielles. Les deux vues historiques de suivi
de lots restent conservées ; cette livraison est une comparaison MRP.

## 693055 à Gaillac — cible précisée par l'utilisateur, 3 octobre 2026

L'utilisateur précise que son retour concernait **Gaillac**, et qu'Avène
était satisfaisant. La comparaison W7 antérieure est donc conservée ;
l'essai D ci-dessous reste une exploration séparée, non retenue. Cette
passe est un audit des sources et un contre-calcul sur les résultats
existants : aucune nouvelle simulation ni règle applicative n'est livrée.

**La présence physique de matière avant sa disponibilité est mal représentée
à Gaillac.** Les nouveaux lots de l'approvisionnement amont simplifié de
693055 ne deviennent physiques dans W7 qu'à leur date de disponibilité,
calculée avec les 28 jours ouvrés de réception. Ce mécanisme ne représente
pas une fabrication amont ni les lots nouvellement présents en attente de
libération. L'OF initial et les 1 200 kg initialement retenus ont, eux,
déjà des états distincts et ne doivent pas être ajoutés une seconde fois.

Le rapprochement indépendant porte sur 1 451 lignes MRP, 52 versions et
53 photos de stock. J total rejoint les photos à 10 kg près dans 51 des
52 rapprochements hebdomadaires ; le 3 mars conserve un écart de 610 kg.
En moyenne sur ces rapprochements, J rattaché à la semaine courante vaut
518,65 kg et J disponible ultérieurement 565,38 kg, contre 1 105,58 kg de
stock physique source. Ces catégories ne constituent pas un relevé
journalier de statut qualité.

| Situation source | Lecture vérifiée |
|---|---|
| Plan du 25 mai, photo du 26 mai | J courant = 0 ; J futur = 1 800 kg ; photo = 1 810 kg. La matière est déjà présente, bien qu'indisponible. |
| OF initial, `Extract_En_cours`, ligne 103 | 600 kg avec G au 27 janvier et I au 25 février. Conserver ces dates explicites, sans rajouter 28 jours à I. |
| Plans à partir du 24 août | Aucun J futur pour Gaillac/693055, alors que le paramètre E reste 28 jours. |
| Plan du 28 décembre, photo du 29 décembre | J courant = J futur = 0 ; photo = 10 kg. H prévoit 600 kg le 18 janvier 2026 puis 1 200 kg le 25 : ces H ne sont pas du stock déjà présent. |

**Contre-calcul rejeté : créer le stock physique dès la commande tout en
gardant sa disponibilité inchangée.** Cela ajouterait les quantités des
24 ordres amont W7 pendant leur attente. Le 26 mai, le résultat passerait
de 600 à 1 800 kg, proche des 1 810 kg sources. Mais le 29 décembre, il
ajouterait 1 800 kg alors que la photo n'en indique que 10. L'erreur moyenne
annuelle ne diminuerait que de 953,27 à 931,35 kg, avec une dégradation du
quatrième trimestre de 462,31 à 1 928,46 kg. Les écarts initiaux de départs
de Gaillac persisteraient également. Ce contre-calcul conserve Avène et
le disponible par construction ; ce n'est pas une nouvelle exécution du
moteur ni une validation d'une date physique industrielle.

La règle de représentation reste donc `physique = disponible + réservé
+ retenu`, avec **une entrée physique datée distincte de la libération**.
Les 28 jours ouvrés source sont conservés pour la planification, mais ils
ne prouvent ni la date de fin de fabrication des nouveaux lots ni leur
présence sur place dès une décision de réapprovisionnement. Reconstituer
ces dates et le pilotage amont est nécessaire avant de généraliser une
correction. Aucune sécurité propre à 693055/Gaillac n'est fournie dans
l'onglet récent de politique de stock ; cette absence ne prouve pas une
cible industrielle de stock nul.

[Audit des sources](../../artifacts/testing/mrp_693055_gaillac_20261003/sources/report.json) ·
[Fin d'année](../../artifacts/testing/mrp_693055_gaillac_20261003/sources/late_year.json) ·
[Contre-calcul indépendant](../../artifacts/testing/mrp_693055_gaillac_20261003/validation/representation.json) ·
[Preuves et décision](../../artifacts/testing/mrp_693055_gaillac_20261003/delivery.json).

## 693055 à Avène — écarts résiduels et essai de sécurité datée, 3 octobre 2026

**La correction des calendriers ne suffit pas à reproduire Avène.** Cette
passe compare W7 conservé à un seul nouvel essai D de **365 jours en 2025**.
Le moteur applicatif n'est pas modifié ; D active une convention existante
sur les composants internes éligibles, notamment 693055/Avène et
773474/Gien. Aucun résultat antérieur n'est remplacé.

Le rapprochement des mouvements montre des réceptions simulées mal placées :

| Intervalle entre photos | Variation du stock source | Consommation simulée W7 | Réception simulée W7 | Augmentation de l'écart simulé − source |
|---|---:|---:|---:|---:|
| 13–20 janvier | −360 kg | 374,44 kg | 600 kg | +585,56 kg |
| 31 mars–7 avril | −270 kg | 274,67 kg | 600 kg | +595,33 kg |
| 5–12 mai | −320 kg | 251,19 kg | 600 kg | +668,81 kg |

Ces lignes ferment l'équation `variation de l'écart = réceptions simulées
− consommations simulées − variation du stock source`. La proximité des
sorties simulées et de la baisse du stock source en avril met en cause le
calendrier des réceptions ; elle ne prouve pas l'absence de mouvements
industriels compensés entre deux photos. En décembre, le problème s'inverse :
du 1er au 8, le stock source augmente de 820 kg tandis que W7 ne reçoit rien
et consomme 388,53 kg. Les photos du lundi sont comparées à la clôture
simulée du dimanche précédent, comme dans la carte.

**Consommations partagées : hypothèse toujours non mesurée.** W7 applique
une fraction fixe de 82,1654 % aux besoins industriels sélectionnés pour
représenter les autres usages, puis ajoute les prélèvements BOM exécutés.
Cela donne 12 349,46 + 900,35 = 13 249,81 kg sur 2025, contre 15 030 kg de
besoins projetés sélectionnés. Cet écart de périmètre ne démontre pas
1 780,19 kg de consommation réelle manquante : les besoins I sont révisés
entre plans, et les OF déjà lancés ne doivent pas consommer leurs matières
une seconde fois. Les transformer intégralement en sorties physiques
fabriquerait une observation absente des sources.

La lecture indépendante des 52 plans et des 53 photos confirme également
que H reste une entrée prévue, I un besoin projeté et J du stock déjà
physique, éventuellement disponible plus tard. Le 9 novembre, J présente
20 kg rattachés à la semaine courante et 600 kg disponibles la semaine
suivante, soit les 620 kg de la photo du 10 novembre. Ces 600 kg de J ne
sont pas à créer une seconde fois comme réception ; la même ligne comporte
aussi 600 kg en H, qui restent une entrée prévue distincte. Les semaines
absentes conservées depuis un ancien plan n'ajoutent aucun besoin dans
les fenêtres de 20, 30 ou 36 jours
entre le 1er mai et le 20 juin : elles n'expliquent pas le principal pic.

**Règle commune testée dans D** (`source_safety_additive_v2`) :

```text
date protégée = max(date du calcul, date du besoin − jours de sécurité ouvrés)
date de lancement proposée = date protégée − délai de planification de la revue
besoin net = max(0, besoins protégés + plancher fixe source
                   − stock alloué − engagements existants alloués)
```

Les 20 jours ouvrés source d'Avène restent inchangés. Le plancher fixe,
quand il existe, est compté une fois ; les stocks et engagements sont
alloués une seule fois. Une réception ferme tardive reste allouée avec
son retard explicite, sans achat automatique en double. Le délai de
planification est scalaire à chaque revue ; la date de lancement proposée
reste soumise à la cadence de transfert et à la disponibilité amont.
Ce n'est donc pas une date d'expédition physique garantie. L'ancienne
réserve proportionnelle au rythme moyen n'est pas ajoutée par-dessus.
Les besoins physiques ne sont
pas avancés. Le trajet de 7 jours et les transferts par pas de 600 kg sont
les mêmes hypothèses que W7, toujours non prouvées comme pratiques réelles.
Les traitements à réception de 7 et 28 jours ouvrés restent confirmés.

**Résultat : essai non retenu comme nouvelle référence.** L'écart absolu
moyen aux 52 photos d'Avène passe de 467,66 à 436,46 kg (−6,67 %), mais
celui d'avril–juin augmente de 612,08 à 648,74 kg. Les 23–24 juillet,
D a zéro stock disponible malgré 1 200 kg présents en attente de
libération ; le reliquat des autres usages atteint 102,21 kg avant sa
résorption le 25. À Gaillac, l'écart annuel augmente de 953,27 à 976,73 kg.
Sur les 29 couples comparables, quatre s'améliorent, un se dégrade et
24 restent identiques. Les stocks et volumes annuels des deux PF sont
inchangés par rapport à W7. Une baisse de moyenne annuelle ne suffit donc
pas à valider la règle comme explication industrielle.

La [comparaison interactive W7/D](../../resultats/mrp_693055_avene_20261003/comparaison.html)
ouvre directement 693055 à Avène. La [contre-vérification indépendante](../../artifacts/testing/mrp_693055_avene_20261003/validation/final_validation.json)
vérifie les bilans, les calendriers et les besoins anticipés. Quatorze cas
ciblés en mémoire et la qualification CSV ont réussi. Les
[preuves de livraison](../../artifacts/testing/mrp_693055_avene_20261003/delivery.json)
rattachent le calcul, les sources et l'affichage à leurs fichiers exacts.
Ces contrôles valident les calculs et leur restitution, **pas la fidélité
du modèle au fonctionnement industriel**, qui reste insuffisante ici.

## 693055 — correction des calendriers et essai de transfert interne, 3 octobre 2026

**Confirmation utilisateur : tous les traitements à réception se comptent du
lundi au vendredi**, dont 7 jours à Avène, 28 à Gaillac et 6 à Gien pour
773474. Le jour de départ du calcul est exclu ; aucun jour férié non fourni
n'est ajouté. Les résultats historiques ci-dessous gardent leurs conventions
d'origine et ne constituent pas la définition du calendrier courant.

La correction du moteur est générique et activée par une politique explicite
de transfert interne. Le cas étudié reste 693055, sur **365 jours physiques
en 2025**, avec la projection MRP glissante existante sur 52 semaines. Les
sources Excel, les stocks physiques initiaux, la sécurité d'Avène de 20 jours
ouvrés et la référence précédente H sont conservés.

Les règles ajoutées ou précisées sont les suivantes :

1. **Ne pas confondre approvisionnement et trajet.** Le délai FIA de 70 jours
   reste une donnée source. Pour une route interne dont le trajet physique
   est explicité, `arrivée physique = départ effectif + durée du trajet`.
   L'expédition ne prélève que le stock disponible au site de départ. Les
   essais de trajet de 1 et 7 jours sont des hypothèses, pas des délais
   industriels retrouvés avec certitude.
2. **Libérer après réception.** `date disponible = avancer_jours_ouvrés(arrivée
   physique, traitement à réception)`. Le lot entre une seule fois dans le
   stock physique à l'arrivée, reste indisponible pendant le traitement puis
   devient utilisable sans nouvelle entrée physique. Le MRP crédite cet
   engagement une seule fois, à sa disponibilité.
3. **Conserver le stock déjà présent mais retenu.** À tout instant,
   `stock physique = disponible + réservé + indisponible`. Dans l'essai,
   les 1 800 kg initiaux de Gaillac sont répartis en 600 disponibles et
   1 200 retenus. Le repère de libération du 12 janvier provient du premier
   plan du 5 janvier : sa reprise à l'ouverture du 1er janvier est une
   hypothèse explicite. Les 10 kg non rapprochés entre inventaire et MRP
   restent inclus dans les 600 kg, avec un statut source non expliqué.
4. **Tester les transferts par lots entiers sans fabriquer de stock.** Avec
   un pas candidat `L = 600 kg`, `besoin arrondi = L × plafond(besoin net/L)`
   et `quantité expédiable = L × plancher(stock disponible/L)` ; le départ
   est limité par ces deux quantités. La planification emploie le même pas
   et réutilise le reliquat prévu. Le lot de fabrication de 600 kg est
   documenté ; son emploi comme pas strict de transfert reste une hypothèse.
5. **Employer le calendrier confirmé dans la disponibilité amont.** Pour
   l'approvisionnement agrégé de Gaillac, `disponibilité =
   avancer_jours_ouvrés(décision, 28)`. Exemple : décision le 8 janvier,
   disponibilité le 17 février, soit 40 jours calendaires. À chaque revue,
   le moteur recalcule ce délai écoulé pour la couverture et les propositions.
   Une commande déjà engagée conserve sa date ; elle n'est pas décalée de
   nouveau à chaque calcul.

**Limite de la cinquième règle :** faute de BOM et de calendrier de
fabrication amont pour 693055, cette frontière reste un apport agrégé dont
la création physique coïncide avec la disponibilité. Les 28 jours sources
sont un traitement à réception, pas une durée de fabrication démontrée.
La correction de leur calendrier ne reconstitue donc pas le stock physique
nouvellement produit puis retenu à Gaillac. De plus, les propositions
futures utilisent le délai calendaire calculé au jour de revue ; les dates
des réceptions engagées sont, elles, calculées exactement en jours ouvrés.

Les besoins des autres formulations restent une estimation physique
inchangée. Les besoins industriels datés utilisés pour planifier ne sont
pas ajoutés une seconde fois aux besoins propres de la BOM.

Reproduction et preuves : `artifacts/testing/mrp_693055_correction_20261003/`.
`study.py` conserve chaque recette et chaque exécution ; les graphes W1/W7
diffèrent par le seul trajet de 1/7 jours. B reproduit H sous la première
version de la correction ; T1 conserve l'ancien calendrier de 28 jours
calendaires pour isoler ensuite son effet. Les essais n'activent pas
automatiquement une nouvelle référence nominale.

**Résultats des essais exécutés.** Écart absolu moyen sur les 52 photos de
chaque site, comparées à la clôture simulée précédente, hors ouverture :

| Article / site | Référence H | W1 : trajet 1 jour | W7 : trajet 7 jours |
|---|---:|---:|---:|
| 693055 / Avène | 652,39 kg | 564,50 kg | 467,66 kg |
| 693055 / Gaillac | 859,81 kg | 896,35 kg | 953,27 kg |
| 268091 / Muret | 178 599,69 UN | 189 662,17 UN | 189 662,17 UN |

W7 réduit l'écart d'Avène de 28,3 %, mais augmente celui de Gaillac de
10,9 %. Les 61 jours de stock physique nul à Avène disparaissent dans
les deux essais. À Gaillac, ils passent au contraire de 57 à 203 jours
dans W1 et 201 dans W7. Un stock nul quotidien ne se compare pas à une
absence de zéro dans des photos seulement hebdomadaires.

Pour chacun des deux essais, 10 des 29 couples article/site comparables
s'améliorent, 7 se dégradent et 12 restent identiques. Le service et les
quantités annuelles produites des PF restent identiques ; leur calendrier
peut changer. 773474 et le PF 268967 ne changent pas. Il n'y a donc **pas
de promotion automatique de W1 ou W7 comme nouvelle référence**.

La meilleure courbe d'Avène ne reconstitue pas la fabrication ni le stock
retenu amont à Gaillac. H→W modifie plusieurs conventions à la fois :
trajet, disponibilité initiale, pas de transfert et réception. W1↔W7
isole le trajet ; T1↔W1 isole le calendrier de 28 jours. Il serait incorrect
d'attribuer toute l'amélioration d'Avène à une seule de ces règles, ou de
présenter le trajet de 7 jours comme mesuré dans les sources.

Contrôles exécutés : 51 cas ciblés de calcul en mémoire réussis sur le code
final ; quatre simulations annuelles B/T1/W1/W7 terminées sans changement
de leurs entrées ou de leur code pendant le calcul ; qualification des
CSV et contre-vérification indépendante des quantités, des calendriers et
des bilans physiques. B reproduit les 39 CSV communs à H à l'identique
sous la première correction ; B/T1 ont été calculés avant l'extension du
calendrier, W1/W7 après. La compatibilité de l'ancien calendrier est aussi
couverte par les tests du code final. Ces contrôles ne certifient pas la
calibration industrielle.

La [comparaison interactive](../../resultats/mrp_693055_correction_20261003/comparaison.html)
conserve H, W1, W7 et l'étape T1. Les courbes, les sélecteurs, les dates,
le zoom et les vues de production ont été contrôlés hors ligne. Le mode
automatique a été rapproché directement du stock physique affiché ; les
échecs antérieurs du lancement et du contrôle de ce mode sont conservés
avec leur diagnostic. Les [preuves de livraison](../../artifacts/testing/mrp_693055_correction_20261003/delivery.json)
référencent le contrôle final réussi et les limites de calibration.

## 693055 à Gaillac et Avène — diagnostic du 3 octobre 2026

**Périmètre : audit des résultats H conservés, sans nouvelle simulation ni
modification du moteur.** H reprend C2 avec la fermeture de fabrication
d'Avène du 4 au 15 août. Les calculs physiques couvrent uniquement 2025.
693055 est confirmé par l'utilisateur comme partagé entre formulations.
La politique récente le classe en PFI ; son ancien classement MP dans la
BOM ne suffit pas à en faire un achat externe ordinaire.

Les quantités ci-dessous sont converties des grammes du moteur en kg.
Comme dans la carte, une photo du lundi est comparée à la clôture simulée
du dimanche précédent ; l'heure de la photo n'est pas documentée.

| Site et photo | Stock source | Stock simulé H |
|---|---:|---:|
| Gaillac, 20 janvier | 1 800 kg | 0 kg |
| Avène, 20 janvier | 570 kg | 579,218 kg |
| Avène, 27 janvier | 1 370 kg | 343,286 kg |
| Avène, 29 décembre | 2 140 kg | 510,192 kg |

Sur les 52 photos hors ouverture de chaque site, Avène présente un stock moyen de
1 143,269 kg dans la source contre 697,033 kg simulés, avec un écart absolu
moyen de 652,391 kg. À Gaillac, les valeurs sont respectivement
1 105,577 kg, 623,077 kg et 859,808 kg. Le stock physique simulé d'Avène
est nul du 7 février au 18 mars, puis du 2 au 22 avril : 61 jours au total.
Les photos hebdomadaires ne montrent aucun zéro, sans prouver l'absence
de rupture entre deux photos.

**Le premier écart majeur vient du calendrier et de la localisation de
la matière.** Le lot de 1 800 kg quitte Gaillac le 8 janvier dans H
(`SHIP-00000015`) et n'arrive à Avène que le 19 mars, soit 70 jours plus
tard. Les photos conservent pourtant 1 800 kg à Gaillac jusqu'au 20 janvier.
Entre les photos du 20 et du 27 janvier, Gaillac baisse de 1 190 kg et
Avène augmente de 800 kg nets. Ces variations sont compatibles avec un
transfert plus court et des consommations concomitantes ; elles ne
prouvent pas un identifiant commun, une quantité brute réceptionnée ni
un délai physique exact. Le MRP prévoit également une entrée de 1 190 kg
à Avène en janvier.

Le chiffre 70 provient de `268091.xlsx/FIA!F22`, intitulé « délai
prévisionnel de livraison ». Le modèle l'utilise comme une durée physique
après expédition. Les sources ne prouvent pas cette décomposition pour
un produit interne déjà stocké à Gaillac. Il ne faut donc ni transformer
automatiquement 70 en une journée de camion, ni considérer sa lecture
actuelle comme une durée de transport industrielle établie.

**Quatre autres conventions doivent rester visibles dans le diagnostic :**

- Dans le premier plan connu, daté du 5 janvier, Gaillac présente 590 kg
  disponibles immédiatement et 1 200 kg de stock déjà présent, disponible
  plus tard (`J785:J786`). Le total de 1 790 kg laisse un écart de 10 kg
  avec la photo, dont le statut n'est pas documenté. H rend les 1 800 kg
  entièrement disponibles dès l'ouverture. Reprendre les états du 5 janvier
  au 1er janvier exigerait toutefois une hypothèse d'initialisation explicite.

- Les 600 kg de `Taile de Lot!E5` sont le lot fixe de réapprovisionnement
  agrégé à Gaillac. Ils ne définissent pas le lot de transfert : celui-ci
  utilise actuellement un arrondi de 50 kg et une revue tous les 7 jours,
  conventions du modèle qui ne sont pas démontrées par cette fiche achat.
  Les entrées H d'Avène sont pourtant des multiples de 600 kg dans 845 des
  846 lignes positives des 52 plans, l'exception étant 1 190 kg. Ce sont
  des positions de plans successifs, pas 846 commandes distinctes ; elles
  soutiennent l'essai de transferts de lots entiers, sans en prouver la règle.
- Aucun processus ni BOM amont de fabrication de 693055 n'est fourni.
  La frontière simplifiée crée et rend disponibles les nouveaux lots au
  bout de 28 jours calendaires, en reprenant un champ source de traitement
  à réception. Ce n'est pas une durée de fabrication démontrée. Les
  7 jours de réception source à Avène sont importés dans la politique
  fournisseur, mais ne sont pas appliqués à cette route interne. Le calendrier
  de ces 7 et 28 jours doit être explicité : la confirmation utilisateur des
  jours de réception ouvrés portait explicitement sur 773474 à Gien.
  L'OF initial
  de 600 kg conserve bien ses dates distinctes : physique le 27 janvier,
  disponible le 25 février (`Extract_En_cours.xlsx`, ligne 103).
- Le partage est confirmé, mais sa proportion ne l'est pas. La consommation
  physique des autres formulations reste estimée par `I sélectionné ×
  0,8216542097`. Cette fraction dérive d'une fenêtre du premier plan,
  et non d'une mesure de prélèvement. Pour la planification datée, les
  besoins I connus sont en revanche pris à 100 %, en déduisant les besoins
  propres déjà représentés : ce n'est pas un cumul `I + 82 % de I`.

**Le bilan ne révèle pas de disparition de matière.** Sur les 365 jours,
`Gaillac + Avène + transit = ouverture + apports amont + OF initial
physiquement livré − consommation BOM − consommation autres usages`
se ferme à moins de 0,000001 kg. Le transit atteint 5 150 kg le 18 mars.
À la clôture du 28 décembre, H porte encore 3 450 kg en transit, en plus
des 600 kg à Gaillac et 510,192 kg à Avène. Le transit industriel n'est pas
mesuré : ce total ne peut pas être comparé directement à la somme des
deux photos sources.

La correction à instruire est donc une **règle commune aux transferts
internes** : distinguer la date de commande/réservation, la disponibilité
amont, le départ physique, l'arrivée physique et la libération à réception.
Une réservation ne doit pas retirer la matière du stock physique du site.
Le délai global d'approvisionnement doit être décomposé avant de devenir
un délai après départ. Les engagements initiaux doivent être rapprochés
des premiers plans sans convertir toutes les propositions H en commandes
fermes. Augmenter arbitrairement le stock de sécurité ne résout pas ces
problèmes de dates et de périmètre.

Preuves reproductibles : `artifacts/testing/mrp_693055_audit_20261003/`.
`analysis.py` et `report.json` rapprochent les CSV de la carte et vérifient
les bilans ; les audits `sources/`, `engine/` et `validation/` séparent
lecture des classeurs, lecture du moteur et contre-vérification indépendante.
Le succès des contrôles arithmétiques ne certifie pas la calibration.

## Horizon 2026 et fermeture d'Avène — essais vérifiés, 3 octobre 2026

La fermeture de **fabrication à Avène du 4 au 15 août 2025 inclus** est
confirmée par l'utilisateur. Elle ne ferme pas implicitement la qualité,
les transports ou les autres sites. Les essais restent limités à 365 jours
physiques en 2025, avec un horizon de planification glissant de 364 jours.

Les versions MRP de 2025 contiennent déjà des **besoins I projetés en
2026** : la version du 5 janvier atteint le 4 janvier 2026 et celle du
28 décembre atteint le 27 décembre 2026. Ces besoins ne sont pas, à eux
seuls, une preuve de prévision commerciale ni d'un taux annuel de 5 %.
La série commerciale de `demand_PF.xlsx` comporte 52 semaines par PF,
sans millésime explicite ; les colonnes `forecast_demand` et `real demand`
sont identiques dans les 104 lignes. Le rapprochement de ce profil avec
la demande exécutée porte sur 730 lignes journalières et ne trouve aucun
écart : 3 576 442 UN pour 268091 et 1 575 986 UN pour 268967. Quatre semaines
négatives de 268967 sont compensées sur des semaines positives à l'import,
en conservant le total annuel. Preuve : `mrp_forward_horizon_20261003/sources/demand_report.json`.

Le taux **+5 % demeure une hypothèse d'essai**, conformément à la précision
de l'utilisateur : l'industriel prolonge ses prévisions, mais son taux exact
n'est pas confirmé. La variante de croissance remplace les projections
2026 uniquement dans cet essai ; elle ne change pas les demandes physiques
2025 ni les classeurs sources. La référence conserve les projections sources.

Quatre variantes permettent de distinguer les mécanismes :

- **E** : référence C2 avec les besoins I de la semaine courante utilisés
  comme enveloppe de planification révocable, sans les transformer en ventes.
- **F** : E avec la fermeture de fabrication confirmée, prise en compte
  dans les propositions et l'exécution ; la capacité avant l'arrêt reste limitée.
- **G** : F avec l'hypothèse `prévision 2026 = profil commercial 2025 × 1,05`.
  Ce profil commercial importé est distinct des besoins I du MRP. Il est
  répété selon la convention annuelle actuelle de 365 jours ; les cibles
  de 2025 gardent leurs besoins MRP datés. Aucun taux de 5 % n'est présenté
  comme extrait du fichier industriel.
- **H** : C2 avec la fermeture seule, sans l'enveloppe I ni la croissance.
  Ce contre-essai sépare la règle confirmée de l'hypothèse E, rejetée après
  comparaison aux stocks.

Pour l'essai E, on suppose que la version du jour `v` est connue avant le
service de ce jour. À la clôture `d` dans cette semaine :

`I restant = max(0, I source − quantités servies depuis v)`

`Besoin déjà représenté = retard physique après service + prévision restante de la semaine`

`Complément de planification = max(0, I restant − besoin déjà représenté)`

Le complément est daté au prochain jour encore dans la semaine, recomputé
à chaque décision, puis expire à la fin de cette semaine. Le vrai retard
physique demeure. H reste une information d'audit : les stocks simulés et
les approvisionnements engagés du modèle sont déduits une seule fois.
Cette enveloppe est une convention candidate, pas un statut de commande
industrielle déduit des photos. **Elle n'est pas retenue pour le nominal.**

Les quatre calculs de 365 jours se terminent sans erreur, avec code et
sources inchangés pendant chaque simulation. Les 51 tests ciblés passent,
ainsi que les qualifications CSV et les rapprochements indépendants. Les
exécutions durent respectivement 232,3 s, 274,5 s, 263,1 s et 250,6 s ; ces
durées ne sont pas un benchmark, certains calculs ayant tourné simultanément.
La demande physique reste strictement identique à C2.

| Variante | Écart absolu moyen 268091/Muret | Écart absolu moyen 268967/Muret |
|---|---:|---:|
| Référence C2 | 178 600 UN | 681 790 UN |
| E : besoins courants | 362 760 UN | 714 774 UN |
| F : E + fermeture | 362 760 UN | 714 774 UN |
| G : F + profil commercial reconduit à +5 % | 362 760 UN | 714 774 UN |
| H : fermeture seule sur C2 | 178 600 UN | 681 790 UN |

**Pourquoi rejeter E ?** Il avance trop de fabrication en avril et mai :
259 200 puis 432 000 UN supplémentaires de 268091 par rapport à C2. Muret
reçoit 777 600 UN de plus en mai. Au 26 mai, le stock simulé E atteint
1 838 225 UN, contre une photo source à 907 766 UN et 1 060 625 UN dans C2.
Il reste supérieur aux photos dans 17 des 18 rapprochements de mai à août.
Sur les 29 couples comparables, E en améliore 12, en dégrade 16 et laisse
un résultat égal. Il ne résout pas l'absence de production en juin/juillet.

**Fermeture confirmée, mais absence de gain sur les PF.** Le contre-essai H
ne change pas les stocks des deux PF : aucune fabrication physique n'avait
lieu pendant cet arrêt dans C2. Sur les composants et PF pris ensemble,
un couple s'améliore, un se dégrade et 27 restent égaux. H conserve
86 400 UN reçues à Muret en juin et zéro en juillet pour 268091. Le
calendrier empêche bien le travail physique et le travail virtuel MPS pendant
l'arrêt ; une capacité fermée n'est plus confondue avec une capacité inconnue.
Les dates de qualité et de transport restent distinctes. L'anticipation
déplace les propositions et les besoins BOM, sans créer de capacité ni de
matière supplémentaire et sans re-dater les engagements déjà fermes.

**+5 % commercial ne signifie pas +5 % des besoins MRP.** Sur les 339 jours
2026 effectivement renseignés et comparés au 28 décembre pour 268091,
les besoins I totalisent 4 993 350 UN, contre 3 363 893 UN pour le profil
commercial reconduit à +5 %. Pour 268967, sur 361 jours communs, les valeurs
sont 4 260 148 et 1 647 243 UN. Ces comparaisons portent sur les mêmes jours,
pas sur des horizons de longueurs différentes ; elles ne prouvent pas des
ventes annuelles réalisées. G réduit ainsi les nouvelles fabrications de
268091 de 2 347 200 à 2 044 800 UN face à F. Les 302 400 UN encore retenues
à Avène fin décembre disparaissent de ce scénario ; le stock final de Muret
reste à 840 810 UN. Cela n'améliore pas le rapprochement des photos du DC.

**Conclusion de cette étape : aucune de ces pistes n'explique la hausse
industrielle de juillet.** Les nouvelles règles restent optionnelles et
aucun nouvel essai n'est promu automatiquement en nominal. La fermeture
est une donnée confirmée ; le complément I et le taux de 5 % restent des
hypothèses distinctes. Les tests prouvent leur exécution, pas leur calibration.
La [comparaison interactive](../../resultats/mrp_forward_horizon_20261003/comparaison.html)
affiche par défaut C2 et H ; E/F/G restent sélectionnables et figurent dans
le bilan de tous les couples. Le tableau Juillet distingue la variation
nette entre photos des fabrications, réceptions et expéditions simulées.

Preuves sous `etudecas/artifacts/testing/mrp_forward_horizon_20261003` :
`sources/report.json`, `sources/demand_report.json`, `report_E/F/G/H.json`,
`validation/forward_E/F/G/H.json`, `validation/E_timing_diagnosis.json`
et les manifestes de qualification `validation/native`. Aucun essai de
modification de dates, de fichiers factices ou de disparition simulée n'a
été exécuté.

## Continuité des besoins et consommation des prévisions — 3 octobre 2026

La référence de cette étape est **DQ20**, conservée dans sa comparaison
production–Muret. Les essais durent 365 jours en 2025. Les demandes physiques
du scénario, les jours de sécurité 20/60, les OF initiaux, les délais de
libération et l'envoi des PF disponibles au dépôt sont conservés.

**K — conserver l'information connue.** Pour chaque période, retenir la
dernière prévision explicitement fournie par une version déjà connue à la
date de décision. L'absence dans une version plus récente n'est pas une
annulation ; un zéro explicite remplace bien une ancienne valeur positive.
Si aucune version ne renseigne la période, le repli historique reste
identifié comme tel. La règle porte sur les deux PF et les calendriers de
besoins industriels des composants ; aucune référence n'est privilégiée.

K a été simulé : pour 268091/Muret, l'erreur moyenne annuelle passe de
204 481 à **205 904 UN** ; pour 268967, de 551 186 à **513 871 UN**.
Sur 29 couples, 14 s'améliorent, 14 se dégradent et un reste identique.
L'absence d'apports de 268091 en juin/juillet persiste. Cette continuité
évite de perdre une information connue, mais ne prouve pas une meilleure
calibration globale. Les contrôles indépendants portent notamment sur
18 861 besoins datés et 730 conversions des sécurités en jours ouvrés.

**C — consommation hebdomadaire de la prévision, essai qualifié techniquement.**
Dans la semaine courante, la prévision totale `F` est la dernière ligne
future connue avant le début de cette semaine. Les demandes `D` déjà
arrivées dans le scénario diminuent cette prévision ; les quantités déjà
livrées ne sont pas utilisées à leur place :

`Prévision restante = max(0, F − D)`

Le reste est réparti uniquement sur les jours encore futurs de la semaine.
Les commandes effectivement non servies restent dans le retard physique,
compté une seule fois. Une prévision non réalisée expire à la fin de sa
période ; elle ne devient pas une commande ferme. Les prévisions des
semaines futures restent révisables. La ligne I courante agrégée du fichier
industriel n'est pas injectée comme vente. Le traitement d'une fenêtre
incluant aujourd'hui conserve la demande du jour avant son service.

Exemple calculable : prévision 100, demandes arrivées 30, quantités servies
10. Il reste 70 de prévision et 20 de commandes non servies, soit 90 de
besoins à couvrir ; ce ne sont ni 100 + 30 ni 100 − 10 + 20.

L'exécution C initiale a été **arrêtée, non qualifiée** au jour 265 : le
stock physique de 268967/Gien valait `107799.99999999997`, contre `107800`
dans le registre des lots. Un rejeu instrumenté a confirmé un résidu de
deux pas de précision flottante à la sortie du cinquième lot d'une campagne,
et non une fraction industrielle ni une réserve MRP. La garde sur les UN
entières reste obligatoire. L'essai arrêté et son contexte sont conservés
dans `report_C.json` et `engine/C_failure_context.json` ; ils ne constituent
pas des résultats annuels utilisables.

Le correctif valide la cible physique dès la création du lot avec le
validateur UN déjà utilisé par le registre. Le WIP, le stock, le transit et
le registre partagent ainsi la même quantité entière. Il ne modifie pas la
garde MRP ni sa tolérance, et refuse toujours une vraie fraction UN. La
reprise **C2** utilise exactement le graphe C et s'achève sur 365 jours,
en 336,5 secondes, avec le code et les sources inchangés pendant le calcul.
Les 37 cas ciblés, la qualification CSV et l'oracle indépendant ont réussi.

**Résultat industriel : ne pas généraliser cette variante.** L'écart absolu
moyen est mesuré entre les photos de 2025 et le stock physique simulé à la
clôture du jour précédent, comme dans la comparaison conservée :

| Produit à Muret | Référence DQ20 | Prévision conservée K | Consommation de prévision C2 |
|---|---:|---:|---:|
| 268091 | 204 481 UN | 205 904 UN | 178 600 UN |
| 268967 | 551 186 UN | 513 871 UN | 681 790 UN |

C2 améliore 268091 de **12,7 %** face à DQ20 mais dégrade 268967 de
**23,7 %**. Sur 29 couples comparables, 15 s'améliorent, 13 se dégradent et
un reste identique. La demande physique et le service client sont inchangés.
La variante reste optionnelle ; DQ20 demeure la référence conservée.

Pour 268091, les nouveaux lancements commencent le **16 avril**, avec
28 800 UN disponibles après vérification le 30 avril. Muret reçoit
**86 400 UN en juin**, issues de fabrications de mai ; aucune nouvelle
fabrication n'est lancée en juin ou juillet et aucune réception n'a lieu en
juillet. La règle ne résout donc pas le creux de production identifié.
L'année comprend 2 217 600 UN de nouvelles fabrications, en plus des
1 945 715 UN d'OF initiaux. Le 31 décembre, 452 010 UN sont à Muret,
561 600 encore retenues à Avène, 3 800 en transit client et une chez le
client : ces emplacements ne sont pas interchangeables avec une photo du DC.

L'oracle contrôle 730 lignes quotidiennes de consommation des prévisions
(708 lignes adossées à une prévision connue et 22 replis), 18 876 besoins futurs, le retard compté
une seule fois, les 22 OF initiaux et leurs dates G/I, ainsi que les délais
de vérification. Les CSV arrondis à six décimales laissent 13 cas du calcul
de couverture client à la frontière d'un arrondi entier : l'oracle indique
explicitement une borne d'une unité, sans accepter de stock physique
fractionnaire. Les contrôles ne certifient pas une calibration industrielle.

La [comparaison interactive DQ20 / K / C2](../../resultats/mrp_requirement_continuity_20261003/comparaison.html)
conserve les courbes de stock, flux MRP et production, ainsi que les cas
dégradés. Preuves de l'exécution finale : `report_C2.json` et
`validation/native_C2` dans le dossier de cette étape.

La déduction des commandes d'une prévision pour éviter de compter deux
fois les mêmes besoins est documentée par
[SAP](https://help.sap.com/docs/SAP_SUPPLY_CHAIN_MANAGEMENT/15f45255438149fa996da194295b132b/9c0b3444-93a2-416d-8300-44e5ebea1d8e.html)
et [Microsoft Dynamics](https://learn.microsoft.com/en-us/dynamics365/supply-chain/master-planning/reduction-keys)
(consultés le 3 octobre 2026). Ces références motivent le mécanisme ; elles
ne prouvent ni le logiciel ni le paramétrage utilisés par l'industriel.
Le choix d'une période hebdomadaire et l'expiration dans cette période sont
des conventions explicites du candidat, pas des statuts de commande déduits
des photos.

**Demande physique et chiffre d'affaires.** Le fichier `CA_Perdu_Réel.csv`
contient 261 dates ouvrées par PF en 2025, mais aucune quantité physique ni
prix de vente permettant de convertir le CA en unités. Les prix PF sont
également absents des relations de `demand_PF.xlsx`. Des rapprochements de
profils hebdomadaires sont possibles, sans démontrer l'ancrage calendaire de
la demande du scénario. Aucun prix n'est ajusté aux stocks pour fabriquer
une série de ventes. Preuve : `sources/auxiliary_demand.json`.

**Pistes non appliquées après contre-vérification.** Sur les 52 versions
de chacun des deux PF, `I courant − H courant` ne se réconcilie exactement
comme un report net d'engagements dans aucune des 51 transitions contrôlées.
Ajouter ce solde au stock réservé aurait donc introduit un statut non prouvé.
Les rapprochements de calendriers sur huit couples article/site présentent
des contre-exemples : aucun décalage général de six jours n'est retenu.
Enfin, des mouvements en août empêchent de déduire la fermeture de tous les
flux des seules photos ; cela ne réfute pas la fermeture de fabrication
indiquée par l'utilisateur, dont les dates et sites précis restent à établir.

Preuves et recettes de cette étape :
`artifacts/testing/mrp_requirement_continuity_20261003` ; les preuves et
comparaisons de l'étape précédente restent figées.

## Reprise des bilans d'ouverture — 2 octobre 2026

L'utilisateur demande de reprendre les premiers flux et de sélectionner la
politique la plus récente. Les nouvelles recettes lisent les **27 lignes** de
`Flow_Data_Inventory_and_Replenishment_rules.xlsx / Politique de stock MRP`.
Après conversion des unités, une seule valeur numérique diffère de R :
268091/Muret passe de 20 à **0 jour** de sécurité (`E3`). Le zéro est une valeur
explicite, pas une donnée manquante. Les stocks initiaux ne sont pas remplacés.
Les anciennes recettes et leurs résultats restent des références historiques.

**Consigne utilisateur suivante : « prends des jours de sécurité alors ».**
Le nouvel essai S20 reprend **20 jours ouvrés lundi–vendredi pour 268091 à
Muret**, valeur de la référence R (`industrial_confirmation_2026-04-10`).
C'est une dérogation de scénario explicitement demandée après l'examen du zéro,
pas une correction du fichier Excel récent. Les autres politiques restent
celles des 27 lignes récentes. S20 conserve les corrections et le calcul
usine/dépôt de YF ; seule cette sécurité change, avec sa provenance documentée
dans `meta.user_selected_safety_override`. Le résultat est rapproché séparément
de YF et R ; les essais à zéro ci-dessous restent des diagnostics historiques.

**S20 exécuté et qualifié sur 365 jours.** La
[comparaison avec 20 jours de sécurité](../../resultats/mrp_opening_reconciliation_20261002/comparaison_securite_20j.html)
affiche par défaut R et S20, avec YF disponible pour isoler l'effet des 20 jours.
Pour 268091/Muret, l'erreur absolue moyenne passe de **450 145 UN dans YF à
326 325 UN dans S20** ; R donne 402 313 UN, soit une amélioration de **18,9 %**
par rapport à R. Toute la demande annuelle du scénario est servie :
**3 576 442 UN**, contre 3 297 853 avec zéro jour. Le stock Muret termine à
**423 210 UN**, contre zéro. Les nouvelles fabrications atteignent
1 627 200 UN, auxquelles s'ajoutent 1 945 715 UN d'OF initiaux ; le bilan avec
le stock d'ouverture, le stock final et le transit ferme exactement.

La hausse du 13 janvier reste absente : **381 518 UN simulées pour 601 026 UN
dans la photo**, sans différence avec YF à cette date. 773474/Gien et
268967/Muret restent identiques à YF. Sur les 29 couples comparables, S20
améliore 12 erreurs moyennes par rapport à YF, en dégrade 5 et en laisse
12 inchangées ; contre R, le bilan est 11 / 17 / 1. Le choix de 20 jours est
retenu pour cet essai demandé, **sans promouvoir toute la variante comme une
calibration globale réussie**.

L'oracle indépendant vérifie les **365 conversions de 20 jours ouvrés en
26, 27 ou 28 jours calendaires**, ainsi que le caractère inchangé des autres
paramètres. Le moteur et les 115 tests ciblés sont identiques à l'état déjà
qualifié ; la nouvelle simulation et ses CSV ont leur propre qualification.
Preuves : `validation/S20_graph_check.json`, `validation/comparison_S20.json`
et `validation/final_S20_validation.json`. Les sources Excel sont inchangées.

### 268091 après mai : fabrication, libération et entrées à Muret

La consigne industrielle est de **pousser vers Muret tout PF terminé et
libéré à Avène**, sous les contraintes physiques du transport. Un regroupement
hebdomadaire des départs est seulement une hypothèse : les photos hebdomadaires
ne distinguent pas un camion groupé de plusieurs départs dans la semaine.

Dans S20, les 20 OF initiaux totalisent **1 945 715 UN**. Le dernier,
**141 780 UN** (`Extract_En_cours!Sheet1`, ligne 91), existe physiquement le
12 mai et devient disponible le **26 mai**. Il part en deux fois : 129 600 UN
le 26 mai et 12 180 le 27 ; les arrivées à Muret sont les **28–29 mai**.
Il n'y a ensuite **aucune nouvelle fabrication avant le 21 août**.

| Mois S20 | Nouvelle fabrication, UN | Réceptions Muret, UN | Sorties physiques Muret, UN | Stock Muret fin de mois, UN |
|---|---:|---:|---:|---:|
| Juin | 0 | 0 | 303 419 | 659 508 |
| Juillet | 0 | 0 | 305 302 | 354 206 |

À l'usine, les stocks disponibles, retenus et les encours sont nuls fin juin
et fin juillet. Les 31 nouveaux lots S20 sont tous expédiés dès leur
achèvement ; S20 applique les dates G/I des OF initiaux, mais n'active pas
de durée qualité distincte pour les nouvelles fabrications. Ce dernier
point fait l'objet de l'essai DQ20 ci-dessous.

Deux mécanismes de calcul sont identifiés. Le retour du stock dépôt rend la
commande brute négative fin juin et fin juillet. Plus tard, une bande
d'attente égale au **lot maximum de 142 485 UN**, et non au minimum de
28 800 UN, bloque encore le lancement du 20 août : position 256 907,
cible 375 045,94, seuil cible moins maximum 232 560,94. Le 21 août, la
position 251 596 passe sous le seuil 252 109,45 et un lot de 43 200 démarre.
L'oracle indépendant reproduit ces décisions. L'utilisation du maximum
comme bande d'attente n'est pas une règle industrielle démontrée.

Le plan daté lui-même repousse ses propositions. Au 25 mai, sa position
réseau de **1 050 260 UN**, diminuée de **473 348 UN** de besoins modélisés
jusqu'au 30 juin, laisse **576 912 UN**, soit 243 129 de plus que son
plancher courant de 333 783. Cette attente est donc cohérente avec le
périmètre de besoins actuellement injecté ; ce périmètre doit être comparé
à celui du MRP industriel.

Le **besoin de la période courante du MRP source est exclu** de la prévision
injectée (`meta.mrp_forecasts.excluded_current_bucket`), sans être repris
dans le retard client simulé :

| Version du plan | Sorties courantes I source, UN | Prévision du modèle sur sa période courante, UN | Entrées courantes H source, UN | J courant + H − I = K, UN |
|---|---:|---:|---:|---:|
| 25 mai | 798 093 | 75 432 | 415 841 | 817 677 + 415 841 − 798 093 = 435 425 |
| 29 juin | 818 870 | 75 692 | 420 063 | 846 664 + 420 063 − 818 870 = 447 857 |

Cellules : `Flow_Data_MRP_results!Feuille1!H20617:K20617` et
`H25597:K25597`. Le retard physique du modèle à ces dates est inférieur à
une unité. Ces gros blocs I ne sont donc pas absorbés dans ce retard.

**Leur injection brute comme ventes physiques serait incorrecte.** Sur les
51 intervalles comparables, le solde courant H − I est toujours inférieur
à la variation de la photo suivante ; les différences vont de 2 983 à
593 582 UN. Les 52 bilans courants J + H − I = K ferment, mais ils sont
des projections, pas un journal de mouvements exécutés. Un retard de
besoins, une affectation commerciale ou une autre convention de période
restent des explications possibles ; aucun de ces statuts n'est confirmé.
Il faut rapprocher ce bloc des engagements, maintenir les engagements
encore valides et éviter de les créer à nouveau à chaque révision. En
l'absence de cette correspondance, aucun stock réservé fictif n'est ajouté.

Les photos de juin et juillet comportent respectivement deux et trois
intervalles de hausse, totalisant **155 226 et 309 730 UN de variations
positives**. Sans ajustement ni changement de périmètre, ce sont des bornes
basses des entrées sur ces intervalles, pas des réceptions brutes mensuelles
ni des fabrications mesurées. Elles suffisent à réfuter l'absence de toute
entrée de S20. L'absence de photos de 268091 à Avène empêche d'attribuer
chaque entrée à une nouvelle fabrication plutôt qu'à un stock déjà présent.

Le fichier `demand_PF.xlsx` contient 52 pas par PF et des colonnes
`forecast_demand` et `real demand` identiques sur les 104 lignes. Il ne
date pas les pas ; leur ancrage au 1er janvier est une convention existante
du scénario. Il ne constitue donc pas à lui seul une preuve indépendante
des sorties physiques de Muret en 2025.

La transition du **4 au 25 mai** montre précisément les deux représentations
de besoins non réconciliées : le plan du 4 mai prévoit **395 395 UN** pour
les 5–25 mai, tandis que le scénario physique en demande **163 631**, soit
231 764 de moins. Cette différence n'est pas un retard du scénario, dont
les clients ont demandé et reçu leurs propres quantités. Sur les mêmes
dates futures du **26 mai au 30 juin**, la révision fait simultanément
passer la prévision de **763 128 à 473 347 UN**. Les dates communes du
30 juin au 31 juillet passent ensuite de 624 213 à 243 937 UN. Les
propositions de production peuvent donc reculer : la consommation du
scénario n'a pas vidé le stock comme prévu et la projection suivante
diminue. Corriger seulement la date d'un camion ou injecter tout I courant
ne résout pas cette divergence de périmètres.

Les preuves consolidées sont dans
`artifacts/testing/mrp_opening_reconciliation_20261002/after_may` :
`engine/review.json`, `engine/planning_reconciliation.json`,
`validation/physical_flow.json`, `validation/threshold_check.json`,
`sources/report.json`, `sources/current_bucket_review.json` et
`demand_provenance.json`. Les extractions relisent les 52 versions MRP,
les 53 photos et les 20 OF, avec empreintes des sources inchangées.

**Essai DQ20 — diagnostic sur 365 jours, achevé le 3 octobre.** Le graphe
reprend S20 et ses 20 jours ouvrés. Il remplace le retour proportionnel
usine/dépôt par l'exécution des besoins datés, conserve le plancher de
sécurité dépôt et active les **10 jours ouvrés de libération des nouveaux
lots de 268091 à Avène avant l'envoi à Muret**. Cette durée vient du MRP
(`Feuille1!E545`) ; l'affectation à la vérification usine est une convention
de l'essai, cohérente avec la consigne de pousser après vérification, mais
non prouvée par la localisation du champ dans la source. Les OF initiaux
conservent leurs propres dates G/I. `tau_process` n'est pas transformé.
L'exécution datée affecte aussi 268967 et 773474 ; l'essai combine plusieurs
règles et ne mesure donc pas l'effet isolé du délai qualité.

La [comparaison production–Muret](../../resultats/mrp_opening_reconciliation_20261002/comparaison_production_muret.html)
conserve S20 et R et présente les fabrications, libérations, réceptions et
stocks. Pour 268091/Muret, l'erreur absolue moyenne annuelle aux photos
passe de **326 325 à 204 481 UN**, soit **−37,3 %** par rapport à S20.
**Le défaut de juin–juillet demeure** : aucune nouvelle fabrication ni
réception sur ces deux mois. Le gain de stock à ces dates est seulement
28 800 UN, issu d'un lot achevé le 23 avril. Le prochain nouveau lot
n'est achevé que le 12 août. Fin juillet, Muret contient 383 006 UN contre
354 206 dans S20. À la photo du 28 juillet, la clôture de la veille donne
413 756 UN dans DQ20, contre **1 050 357 UN dans la source**.

Le regroupement se déplace aussi dans le temps : **1 022 400 UN** sont
fabriquées en août, dont **849 600 UN** encore retenues à Avène en fin de
mois ; les réceptions de septembre atteignent 936 000 UN. Ce rapprochement
annuel ne démontre ni la bonne cadence de production ni le respect de la
fermeture industrielle d'août, dont les dates précises restent inconnues.
DQ20 reste un **essai de diagnostic** ; les références sont conservées et
aucun journal industriel de ventes, de réservations ou de transports n'est
inventé pour rapprocher les courbes.
L'erreur moyenne de **268967/Muret se dégrade de 381 829 à 551 186 UN**.
Il ne faut donc pas promouvoir DQ20 comme amélioration globale du modèle.
Pour 268091, le bilan physique au 31 décembre ferme sur **1 031 811 UN** :
394 410 à Muret, 547 200 retenues à Avène, 90 200 en transit et une unité
chez le client. Ce total réseau ne peut pas remplacer le stock réel Muret
dans une comparaison ; les emplacements et disponibilités restent distincts.
Les stocks retenus sont bien comptés comme futures disponibilités dans le
plan : **365 égalités quotidiennes** et 68 contrôles datés sur 36 nouveaux
lots confirment leur déduction, sans double libération d'un lot. Le pic
d'août ne vient donc pas d'une seconde fabrication des lots en vérification
(`after_may/engine/dq20_held_review.json`).

### Résultat de cette reprise : défauts isolés, calibration non résolue

La [comparaison interactive des essais d'ouverture](../../resultats/mrp_opening_reconciliation_20261002/comparaison.html)
conserve R et expose XG, Y et YF, avec un zoom janvier et une vue annuelle.
**Aucun de ces essais ne remplace globalement la référence R.** Les trois
correctifs de représentation (priorité à la politique récente, frontière
client, présence physique des OF avant leur disponibilité) sont vérifiés
séparément ; cela ne certifie pas les décisions industrielles du contrôleur.

Y envoie les PF libérés au dépôt, mais lance trop de nouvelles fabrications :
4 550 400 UN de 268091, auxquelles s'ajoutent 1 945 715 UN d'OF initiaux,
pour 3 576 442 UN servies. YF ajoute le retour existant du stock du dépôt
dans le calcul de fabrication. Il supprime cet emballement, mais produit
trop peu : 950 400 UN nouvelles ; 3 297 853 UN servies, pour 3 576 442 UN
demandées, avec un retard supérieur à une unité pendant 106 jours.

| Erreur absolue moyenne aux photos | R conservée | YF, diagnostic complet | Lecture |
|---|---:|---:|---|
| 268091/Muret, année, UN | 402 313 | 450 145 | Dégradé |
| 268091/Muret, janvier–mars, UN | 192 142 | 142 642 | Début rapproché, hausse de janvier encore absente |
| 268091/Muret, octobre–décembre, UN | 479 686 | 907 458 | Fort déficit de fin d'année |
| 773474/Gien, année, kg | 5 092 | 5 120 | Pratiquement inchangé, premier transfert trop tard |
| 268967/Muret, année, UN | 172 404 | 381 829 | Dégradé |

Sur les 29 couples disposant de photos et de stocks simulés comparables,
YF améliore neuf erreurs moyennes, en dégrade dix-neuf et en laisse une
inchangée. Les 33 couples du catalogue de comparaison restent consultables ;
ces deux compteurs n'ont pas le même périmètre.

Les recettes partent explicitement de R pour isoler les causes d'ouverture.
Elles ne constituent pas une consolidation de toutes les anciennes options :
notamment, elles n'activent ni l'exécution datée des nouvelles fabrications,
ni le traitement qualité candidat des nouvelles productions, ni l'option de
conservation de la dernière prévision connue pour une période devenue absente.
Ces choix sont consignés dans les graphes d'essai ; leur absence doit être
prise en compte pour interpréter le déficit de fin d'année. Les dates G/I des
22 OF déjà engagés, elles, sont bien appliquées dans XG/Y/YF.

Le contrôle complémentaire `engine/known_forecast_gap.json` reproduit les
365 signaux et commandes brutes YF depuis les états exportés. À états figés,
la conservation de la dernière prévision connue **réduit** la somme des signaux
moyens sur sept jours de 268091 au quatrième trimestre : 859 255 à 623 908 UN.
Ces sommes mesurent l'exposition du contrôleur, pas les volumes fabriqués.
Son absence n'explique donc pas, à elle seule, le déficit de PF ; aucune
amélioration des stocks n'est déduite de ce calcul sans réexécuter la dynamique.

Les premiers points YF de 268091/Muret sont 417 238 / 381 518 / 329 957 /
377 855 UN aux photos des 6 / 13 / 20 / 27 janvier, contre 423 434 / 601 026 /
548 722 / 534 829 UN dans la source. Le client artificiel explique donc bien
une partie du premier effondrement, mais **la remontée du 13 janvier reste
non reproduite**. Pour 773474/Gien, YF retrouve exactement les 14 593 kg du
6 janvier, mais reporte son premier transfert à 6 400 kg reçus le 15 février.
Il ne faut pas attribuer à YF la première réception du 25 janvier de R et Y.

Vérifications réalisées : **115 tests ciblés en mémoire**, doctor, qualification
CSV de XG/Y/YF, 726 décisions client rapprochées indépendamment par essai,
22 lots d'OF initiaux contrôlés de G à I, bilans physiques PF fermés aux
11 jalons examinés. Deux plafonds de commande à une unité près restent
numériquement ambigus depuis les CSV arrondis à six décimales ; ils sont bornés
dans l'oracle, et non présentés comme des égalités exactes.
Les cinq essais L/X/XG/Y/YF ont chacun achevé **365 jours**, sur des entrées
et un code inchangés pendant le calcul. Aucun calcul à cinq ans ni test
d'altération de fichiers n'a été exécuté.

Preuves actuelles : `validation/comparison_final.json`, `validation/postrun_YF.json`,
`validation/production_balance_YF.json` et les manifestes sous
`validation/final_native/`, dans `artifacts/testing/mrp_opening_reconciliation_20261002/`.
Les inconnues restantes portent en priorité sur le carnet initial de transferts,
la semaine courante des besoins MRP, la disponibilité des stocks initiaux et
le périmètre des 70 jours de 693055. La coordination du plan daté et de
l'exécution physique doit être reprise sans modifier les stocks de sécurité
pour compenser ces différences.

### Erreur de périmètre du flux client

Le client synthétique possède un stock de couverture construit avec le signal
MRP prévisionnel. Ce réglage déplace une grande quantité de Muret vers le client
alors que les sources ne documentent aucun stock industriel à cet emplacement.
La conservation de matière ferme, mais cela ne valide pas cette représentation.

Pour 268091, au soir du 5 janvier (comparé à la photo du 6 janvier), R contient :

| Poste | Quantité UN |
|---|---:|
| Stock initial Muret | 430 538 |
| Expédié depuis Muret | 224 130 |
| Stock restant Muret | 206 408 |
| Stock chez le client synthétique | 56 150 |
| Transport vers ce client | 158 480 |
| Consommation finale cumulée | 9 500 |
| Photo industrielle du 6 janvier à Muret | 423 434 |

`56 150 + 158 480 + 9 500 = 224 130` : la chute vient principalement de la
constitution d'un stock aval artificiel, pas de ventes finales équivalentes.
Du 6 au 13 janvier, R reçoit 144 000 UN au dépôt et en expédie 142 963, donc
le dépôt ne gagne que 1 037 UN, contre +177 592 dans les photos. C/CQ ne
reçoivent rien pendant cet intervalle et expédient 191 723 UN ; leur baisse
n'est pas à attribuer à la référence R. La consommation finale de cet intervalle
est de 29 313 UN pour ces essais.

La correction client en cours de qualification sépare explicitement :

- prévision industrielle sur 52 semaines pour planifier les approvisionnements ;
- demande physique exogène du scénario pour servir le client final ;
- transit client nécessaire, sans couverture supplémentaire non documentée.

Après le service du jour `d`, la commande client candidate vaut :
`max(0, retard(d) + somme_demande_physique(d+1 ... d+L)
− stock_client(d) − réceptions_client_déjà_engagées_arrivant_avant_ou_à(d+L))`.
`L` est le délai physique effectif du transport, pas une durée de sécurité.
Les UN physiques restent entières. Cette variante suppose une demande de
scénario connue et un transport déterministe ; elle ne prétend pas connaître
par avance des événements industriels ou des incidents futurs.

### Un zéro de sécurité ne supprime pas la circulation des produits finis

Les essais L et X ont mis au jour un second défaut, indépendant du client :
avec la politique source récente de 268091/Muret, la branche de transfert
tiré utilise une cible nulle et n'expédie **aucun produit d'Avène vers Muret**
sur 365 jours. Pourtant, Avène dispose de 28 800 UN nouvelles et de
1 945 715 UN provenant des ordres initiaux. À J55, le plan daté propose
177 838 UN, mais le transfert exécuté reste nul. Un bilan de conservation
réussi ne valide donc pas l'exécution de la demande du plan.

La règle industrielle confirmée par l'utilisateur est d'envoyer au dépôt
les PF disponibles. L'essai Y active donc le parcours existant
`finished_goods_dispatch_policy=push_released_available_v1`, sur les deux
liaisons usine–dépôt admissibles, avec la correction client et les dates G/I.
Il ne rétablit ni les anciens 20 jours, ni le repli générique de 7 jours.
La quantité proposée au transfert est le stock usine libéré et non réservé ;
les contraintes de transport restent appliquées. Les stocks retenus avant I
ne sont pas expédiables. Il faut contrôler aussi les nouvelles fabrications :
vider une usine peut relancer son contrôleur local et créer une surproduction.
Y reste un essai comparatif tant que ce contrôle et le rapprochement industriel
ne sont pas terminés. Le parcours historique de transfert tiré reste une
limite connue : il n'est pas corrigé par un nouveau contrôleur dans cette passe.

Le second blocage de YF est localisé dans
`should_defer_new_lot_for_stock_position` : avec cible réseau nulle, sans
campagne active et avec une commande quotidienne inférieure au lot, une
position usine + dépôt + engagements encore positive diffère la fabrication.
Au 28 septembre, le signal vaut 10 111 UN/j, la position 28 800 UN en transit
et la commande brute +2 911 UN, sans fabrication. Le 29, ces 28 800 UN sont
disponibles et le blocage persiste. Le 30, la position devient nulle et un lot
de 28 800 UN démarre. Le retard client n'est pas remonté dans ce retour du
dépôt : le contrôleur lit le retard dépôt, nul, alors que le client est en retard.
Les OF initiaux ne sont pas crédités au-delà de leur date : tous sont
disponibles au plus tard à J145 et les engagements sont nuls de juin à août.
Ce défaut conditionnel n'est donc pas un double comptage des OF G/I. En
décembre, sept journées de contrainte sur 029313 contribuent aussi au déficit.
Preuve : `engine/yf_controller_review.json`. Reprendre 20 jours de sécurité
dans S20 rétablit une réserve cible positive ; cela ne constitue pas, à soi
seul, une validation de ce contrôleur pour toutes les politiques à zéro.

### Lecture du carnet initial et des stocks sources

Les cinq stocks au 1er janvier (268091/Muret, 773474/Gien et Gaillac,
693055/Avène et Gaillac) concordent exactement entre les deux fichiers
d'inventaire. Aucune photo de 268091 à Avène n'est fournie : on ne peut donc pas
déduire son stock initial usine par comparaison directe.

Le carnet `Extract_En_cours` contient 20 O.Proc de 268091 à Avène, un de 773474
à Gaillac et un de 693055 à Gaillac, **sans les transferts internes**. Un
ordre prévu ne doit pas être créé une deuxième fois à partir d'une autre vue.

- **268091** : la première hausse du dépôt est de 177 592 UN (6–13 janvier).
  Le seul O.Proc du carnet dont la livraison G précède le 13 janvier vaut
  139 660 UN (ligne 75, G = 10 janvier, I = 24 janvier). Même en supposant
  tout ce lot déjà à Muret, il reste au moins 37 932 UN d'autres entrées ou
  ajustements à expliquer. Déplacer son lieu de retenue ne suffit pas.
- **773474/Gien** : le plan du 5 janvier contient 6 400 kg d'entrée au repère
  du 12 janvier (`H942`). La photo augmente de 3 206,8 kg du 13 au 20 janvier.
  Un départ après le 1er janvier avec dix jours de délai reste possible :
  l'absence de transit initial ne démontre pas, à elle seule, un transfert perdu.
- **693055/Avène** : une entrée prévue de 1 190 kg et la baisse de 1 190 kg
  à Gaillac accompagnent une hausse nette de 800 kg à Avène du 20 au 27 janvier.
  Un transfert court est plausible, mais aucun identifiant d'expédition ne
  permet d'affirmer ce rapprochement. Le délai FIA de 70 jours est intitulé
  délai prévisionnel d'approvisionnement, sans durée de trajet physique fournie.
  Avec 70 jours appliqués à tout transfert, une arrivée dans cette fenêtre
  impliquerait un départ en novembre 2024 ; repartir sans transit ni commande
  initiale ne peut pas reproduire cette remontée.
- **Gaillac** : le premier MRP distingue déjà 3 200 kg de 773474 disponibles
  plus tard et 1 200 kg de 693055 disponibles plus tard. R/C/CQ rendent pourtant
  tout le stock initial utilisable. Les valeurs sont connues au 5 janvier,
  pas au 1er : une reconstruction rétroactive doit être signalée comme telle.

Dans XG, le registre de transport confirme exactement la cause initiale pour
693055 : les **1 800 kg** de Gaillac partent à J7 (8 janvier), avec une arrivée
à J77 (19 mars). Les photos maintiennent pourtant 1 800 kg à Gaillac jusqu'au
20 janvier. Le stock total a donc été rendu expédiable trop tôt ; les 70 jours
de délai prévisionnel ont aussi été utilisés comme durée après départ. Ces deux
choix expliquent simultanément le creux de Gaillac et l'absence de remontée
d'Avène. Les 70 jours n'ont pas été remplacés arbitrairement par un temps de
camion : leur périmètre métier reste à établir.

Les délais de traitement du carnet initial et du Flow MRP diffèrent également
à Gaillac : 26 contre 33 jours pour 773474, 21 contre 28 pour 693055. Les dates
G/I explicites des ordres existants restent distinctes des paramètres destinés
aux nouveaux ordres. Une égalité de quantité ne suffit pas à identifier deux
occurrences comme un même lot.

Preuves de cette reprise : `artifacts/testing/mrp_opening_reconciliation_20261002/`,
avec `sources/audit.json`, `sources/analysis.json`,
`validation/customer_transit_oracle.json` et `engine/opening_engine_review.json`.
Les tableaux sources, les bilans de simulation et les hypothèses sont séparés.

Pour **773474/Gien**, le premier décalage est déjà visible dans le plan calculé,
avant le transport. Au 5 janvier, C protège 4 894,218 kg :
`7 341,327 kg de besoins sur 39 jours / 39 × 26 jours calendaires`.
Avec 14 593 kg au départ, le premier manque projeté apparaît le 21 février et
le lancement théorique le 3 février. Le besoin de la période courante
(`I941 = 2 097,522 kg`) est exclu par la convention de préparation ; l'entrée
industrielle `H942 = 6 400 kg` n'est pas reprise comme engagement initial.
Le 2 février, les nouvelles prévisions font apparaître un besoin immédiat,
puis la revue physique du 5 février expédie 6 400 kg. Le problème n'est donc
pas seulement une date de camion ou un stock insuffisant à Gaillac.

Le début comporte aussi une consommation avancée : la photo du 6 janvier
reste à **14 593 kg**, identique au 1er janvier, alors que Y clôture la veille
à **13 552,221 kg**, soit un lot de PF ayant consommé **1 040,779 kg**.
La première baisse source de 1 026,6 kg apparaît entre les photos des 6 et
13 janvier. Puis le plan du 12 janvier prévoit H = 6 400 kg et I = 3 361,205 kg :
`13 566,4 + 6 400 − 3 361,205 = 16 605,195 kg`, contre **16 773,2 kg** dans
la photo du 20 janvier. Ce bilan prévisionnel est proche, à 168,005 kg près ;
le simulateur ne reçoit d'abord que **3 200 kg le 25 janvier**. Il faut donc
expliquer ensemble la date de fabrication, la date du transfert et son volume,
plutôt que modifier seulement le délai de réception.

R diffère de C/CQ : il expédie déjà 3 200 kg le 15 janvier, reçus physiquement
le 25 janvier et utilisables le 3 février. Au 15 janvier, R a consommé
1 040,779 kg supplémentaires pour un lot de PF : son stock vaut 12 872,668 kg,
contre 13 913,447 dans C. Avec le même plancher de 6 776,609 kg, le plan de R
trouve 46,684 kg à lancer, arrondis à 3 200, tandis que C ne lance rien.
La disparition de cette fabrication initiale dans C/CQ repousse donc aussi
l'approvisionnement interne. Leur première arrivée du 15 février ne doit pas
être attribuée à R. La preuve est `sources/planning_start_review.json`.

Inclure une fois le besoin courant avance le lancement calculé au 11 janvier
dans une sensibilité comptable, sans démontrer la réception industrielle.
Les quantités H sont des entrées prévues : le fichier agrégé ne distingue pas
ici une nouvelle proposition d'un engagement antérieur. De même, supprimer
les besoins de la période courante n'est pas une règle industrielle établie.
Ces deux choix doivent être étudiés ensemble, sans rejouer des entrées futures
comme si le contrôleur les avait retrouvées seul.

**Contrôle du calendrier sur 40 plans d'ouverture.** Pour 773474/Gien et
693055/Avène, J courant correspond exactement à la photo du lundi suivant
dans huit plans sur huit. K courant se rapproche davantage de la photo une
semaine plus tard : pour 773474, écart absolu moyen de 1 585 kg à D+8 contre
2 643 kg à D+1 ; pour 693055, 166 contre 304 kg. Un cas sans entrée est exact :
plan du 26 janvier pour 693055/Avène, J = 1 370, H = 0, I = 280,
K = 1 090 kg (`H3817:K3817`) ; les photos des 27 janvier et 3 février valent
respectivement 1 370 et 1 090 kg. Il serait donc incorrect de déclarer tous
les besoins courants déjà consommés. Un seul cas exact sans H existe dans
cette cohorte ; les prévisions ne sont pas toutes des mouvements exécutés.

La préparation élimine les lignes `period_day <= known_day` ; les calendriers
MRP industriels et usages complémentaires imposent ensuite une ancre dimanche.
Ils conservent une prévision antérieure pour une période déjà commencée si
elle existe : **exclusion de la révision courante ne signifie pas toujours
besoin nul**. Le premier plan est particulièrement exposé faute de version
antérieure. Décaler seulement les JSON au lundi serait rejeté par le contrat
du moteur ; contourner ce contrôle ou déplacer la date de connaissance serait
incorrect. Une éventuelle convention lundi suivant doit être testée ensemble
dans les trois calendriers, sans cumuler deux versions, ni ajouter une seconde
fois les besoins BOM. Aucun décalage universel n'est appliqué ici, car Gaillac
et le PF présentent encore des écarts de périmètre et de report.
Preuves : `sources/calendar_review.json` et `engine/current_bucket_review.json`
dans le dossier de cette reprise.

La documentation générale [SAP sur le calcul des besoins nets](https://help.sap.com/docs/SAP_S4HANA_ON-PREMISE/fe39e10a9a864a8f8dc9537704f0fa13/46abce5314894208e10000000a174cb4.html)
distingue les besoins et les réceptions engagées utilisées pour les couvrir.
Cela soutient cette séparation dans le modèle ; cela n'identifie ni le logiciel
de l'industriel ni le statut précis des entrées de son export (consulté le 2 octobre 2026).

## Résultat de la passe corrigée sur 2025 — 2 octobre 2026

**Les corrections ont été simulées et contrôlées ; aucune variante ne remplace
globalement la référence.** L'amélioration de 268091 ne se généralise pas à
l'autre chaîne. La [comparaison interactive](../../resultats/mrp_consistent_execution_20261002/comparaison_protection_depot.html)
conserve toutes les références au sélecteur et compare R, F, FDP, C et CQ.
Les calculs définitifs C/CQ et leurs recettes sont dans
`artifacts/testing/mrp_consistent_execution_20261002/extension/retry/`.

Erreur absolue moyenne du **stock physique**, sur les mêmes 52 photos 2025,
rapprochées de la clôture simulée de la veille :

| Article / site | Référence R | C : sécurité dépôt maintenue | CQ : idem, retenue à Avène |
|---|---:|---:|---:|
| 773474 / Gien | 5 091,70 kg | 5 144,86 kg | 5 144,86 kg |
| 268091 / Muret | 402 312,58 UN | 321 391,73 UN | 266 586,65 UN |
| 268967 / Muret | 172 403,83 UN | 476 067,90 UN | 476 067,90 UN |

C améliore 13 des 29 couples comparables, en dégrade 15 et laisse un couple
inchangé ; CQ donne respectivement 12, 16 et 1. Ces nombres ne pondèrent pas
la gravité des écarts et ne mélangent pas les unités dans une somme.
Le 29 décembre, 268091/Muret vaut 660 900 UN dans C et 372 900 dans CQ, contre
1 010 323 dans la photo source : la baisse de l'erreur annuelle ne résout pas
la fin d'année. CQ conserve 604 800 UN physiquement retenues à Avène au
31 décembre ; ce lieu reste une hypothèse. Aucun jour de stock nul au dépôt
pour 268091 dans C/CQ, mais quatre journées de backlog client supérieur à une
unité, contre deux dans R. Le total annuel servi et l'absence de reliquat
significatif final ne doivent pas masquer ces retards de décembre.

### Deux causes restantes désormais localisées

Pour 268967, C fabrique 539 000 UN de plus que FDP, soit cinq lots de
107 800 UN. À demande servie identique, les 539 000 UN se retrouvent exactement
en supplément au dépôt en fin d'année. Le plan maintient une sécurité moyenne
de 860 532 UN, avec un pic de 2 016 860 UN le 28 septembre. Ce pic vaut
`82 jours calendaires × 24 595,857 UN/jour` : le taux retient le maximum entre
le besoin de la semaine courante et la moyenne prévisionnelle de couverture.
Il extrapole ainsi un pic hebdomadaire sur les 60 jours ouvrés de sécurité.
La moyenne prévisionnelle sur 87 jours vaut alors 12 684,839 UN/jour.
**La durée source n'a pas été augmentée : c'est sa conversion en quantité,
puis le maintien de cette quantité dans le plan, qui pose question.**
Une protection fondée sur le cumul des besoins datés de la période de sécurité
est une prochaine hypothèse à tester, pas une règle ERP démontrée par ces essais.

Le rapprochement des politiques montre aussi des paramètres de millésimes
différents, à ne pas confondre avec le délai de traitement à réception :

| Article / dépôt | Ancienne politique, jours de sécurité | Nouvelle politique, jours de sécurité | Paramètre conservé dans R et les essais |
|---|---:|---:|---:|
| 268091 / Muret | 20 | 0 | 20 |
| 268967 / Muret | 25 | 60 | 60 |

Sources : `Extract_Données_Complémentaires.xlsx`, feuille
« Politique de Stock MRP », E25/E26 ;
`Flow_Data_Inventory_and_Replenishment_rules.xlsx`, feuille
« Politique de stock MRP », E3/E2. Les quantités fixes F25/F26 et F3/F2 sont
nulles. Conserver la référence pour isoler une correction ne valide donc pas
son paramétrage comme représentation de la dernière politique industrielle.

### Contrôles réellement réalisés

76 cas ciblés en mémoire et qualifications CSV de B2/C/CQ réussis. B2 conserve
les 37 CSV de R octet pour octet ; il a été recalculé avant l'ultime correction
d'en-tête, puis requalifié après celle-ci, sans prétendre à un troisième témoin.
Les recettes C/CQ ont été relancées entièrement après l'échec d'export de C.
Les 730 lignes de protection dépôt ont été rapprochées indépendamment des
jours ouvrés et des taux. Dans CQ, 58 lots (20 OF initiaux et 38 nouveaux lots)
ont été rapprochés entre création physique, retenue et libération ; les
38 nouvelles dates respectent les dix jours ouvrés et les quantités physiques
achevées concordent avec les créations de lots.

Les contrôles de bilans, unités entières et généalogie ne certifient pas la
calibration industrielle. Les preuves détaillent les anciens essais refusés,
les hypothèses de localisation, les différences de paramètres et les
régressions. Les dates exactes de fermeture d'août restent également à établir.

## Essais de correction du pilotage — 2 octobre 2026

Les variantes B/F/D/FD/FDP/Q sont des essais sur **365 jours en 2025**,
tous construits sur R ci-dessous. Elles ne remplacent pas le nominal.
Leurs recettes, résultats et contrôles sont conservés dans
`etudecas/artifacts/testing/mrp_consistent_execution_20261002/` ; une recette
préparée n'est pas un résultat vérifié. Les références antérieures restent intactes.

**Correction complémentaire C : transmettre la sécurité du dépôt au plan de
fabrication.** Les premiers essais ont démontré un défaut du plan antérieur :
à Muret pour 268091, le 29 juin, `S = 281 140,12 UN`, alors que les besoins
sur la couverture valent `286 722 UN`. Le complément
`max(0, S − besoins_sur_couverture)` devient nul. Il ne maintient donc pas S
après les sorties. La commande physique du dépôt garde pourtant sa cible :
faire exécuter ce plan par l'usine rend ce décalage pénalisant.

C conserve `S = max(quantité de sécurité source, taux prévisionnel courant ×
jours de sécurité convertis lundi–vendredi)` comme **plancher non consommable**
des soldes projetés du dépôt. Le besoin net après une sortie devient
`max(0, S − stock projeté après cette sortie et les réceptions datées)`.
Les délais de transport et de revue ne s'ajoutent pas à S ; les réceptions
fermes sont déduites une seule fois. Si stock et réceptions couvrent déjà
besoins + S, il n'y a aucune nouvelle proposition. Les jours sources de la
référence sont conservés : C ne réalise pas une nouvelle calibration.

L'option `depot_safety_protection_policy=source_stock_floor_v1` sélectionne
les dépôts de PF reliés à leur usine et disposant des paramètres MRP sources,
sans liste d'articles ajustée aux courbes. C reprend FDP et cette seule option ;
CQ reprend Q et cette seule option. B2 recalcule le témoin sur le nouveau code.
Leurs recettes et preuves sont dans le sous-dossier `extension/` de l'étude.

Le premier essai Q a également révélé un contrôle de traçabilité encore fondé
sur la disponibilité immédiate : il comparait les lots physiquement créés à G
aux sorties devenues disponibles à I. Ce contrôle doit comparer la quantité
de lots achevés physiquement (`physical_completed_qty`, issue du passage du WIP
au lot terminé) aux créations G ; l'audit indépendant continue à rapprocher
les disponibilités I des libérations effectives. Un lot toujours retenu en fin
d'horizon existe physiquement, sans compter comme disponible. Le refus de
qualification de ce premier Q reste conservé dans ses preuves.

Les règles testées sont communes aux articles concernés par chaque type de flux :

1. **Prévision connue, par période (F).** À la décision `d`, prendre pour la
   période `t` la dernière quantité publiée avant la limite de connaissance de
   cette période : `prévision(d,t) = quantité(version connue la plus récente
   contenant t)`. Une période absente n'efface pas une prévision antérieure ;
   une quantité explicitement nulle la remplace. La semaine composant en cours
   conserve sa prévision connue avant son début. Sans aucune prévision connue,
   le repli antérieur reste applicable. Cette règle concerne les prévisions PF
   et composants, pas une réécriture des consommations physiques complémentaires.
2. **Besoins nets datés (D).** `besoin_net(t) = max(0, besoins(t) + protection(t)
   − stock projeté avant besoin(t))`, avec les disponibilités fermes à leurs
   dates et les quantités standard/contraintes existantes. Un engagement tardif
   reste identifié comme tardif : il n'est ni disponible immédiatement ni
   dupliqué. Le plan garde un horizon glissant de 364 jours (52 semaines).
3. **Lancement cohérent avec ce plan (D).** Le plan établi en fin de journée
   sert à la décision du lendemain ; on recalcule le manque après les réceptions
   du jour, puis on lance les propositions devenues dues. Un ordre déjà en cours
   empêche un doublon. Matière disponible, capacité, unités entières, taille des
   campagnes et généalogie continuent à limiter l'exécution réelle. La prévision
   ne devient jamais automatiquement une fabrication physique. Le décalage
   décisionnel d'un jour est une convention explicite de cet essai ; les OF
   initiaux fermes ne sont pas automatiquement replanifiés.
4. **Envoi des PF disponibles (P).** Le stock PF libéré est poussé vers son
   dépôt par les transports existants, au lieu d'être retenu à l'usine par une
   petite cible locale. La disponibilité usine, les expéditions et les réceptions
   dépôt restent trois mouvements distincts.
5. **Production physique et disponibilité distinctes (Q).**
   `disponibilité = fin physique + traitement en jours ouvrés` ; le même lot
   existe physiquement mais reste inutilisable entre ces dates. Pour les OF
   initiaux, conserver les dates G/I de la source, sans ajouter le traitement
   une seconde fois. La campagne est physiquement achevée à G, sa disponibilité
   est suivie séparément à I. La poussée attend cette disponibilité.

Q ajoute uniquement les **10 jours ouvrés de 268091**, documentés par
`Flow_Data_MRP_results.xlsx!Feuille1!E545` et les dates G/H/I des OF Avène dans
`Extract_En_cours.xlsx` (notamment lignes 72, 75, 91). L'utilisateur pense que
la retenue se situe à Avène : c'est une **hypothèse de localisation**, pas une
preuve ERP d'un statut qualité. Les 15 jours indiqués pour l'autre PF ne sont
pas affectés arbitrairement à Gien. Les valeurs source de sécurité et la
convention `tau_process` restent inchangées.

F et D sont testés séparément, puis ensemble ; FDP ajoute la poussée, Q ajoute
la retenue avant disponibilité. B recalcule R sans nouvelle règle pour contrôler
la non-régression. On mesure séparément stock physique, stock disponible,
production, réceptions et service ; augmenter la retenue physique n'est pas
assimilé à améliorer la disponibilité. Les contrôles de conservation des lots
et de bilan matière ne certifient pas la reproduction des stocks industriels.

## Contre-analyse des écarts persistants : 773474/Gien et 268091/Muret — 2 octobre 2026

**Les derniers essais ne reproduisent pas encore les deux stocks industriels.**
Cette passe reprend les 52 versions MRP, les photos 2025, le carnet initial,
les paramètres et nomenclatures, puis les décisions et flux des calculs déjà
effectués sur 365 jours. Aucun moteur, paramètre industriel ou résultat de
simulation n'est modifié. Les sections suivantes conservent les essais antérieurs ;
la présente section précise et corrige leur interprétation.

N est la référence avant les cinq essais. R ajoute les six jours ouvrés de
réception de 773474/Gien. PF désigne ici l'essai de transfert systématique des
produits finis avec retour du stock dépôt vers la fabrication ; **PF ne cumule
pas R**. Les deux articles appartiennent à des chaînes distinctes :
773474 → 268967/Gien et 693055 → 268091/Avène.

Les moyennes ci-dessous portent sur les mêmes 52 photos, rapprochées de la
clôture simulée de la veille. Elles ne sont pas des erreurs absolues moyennes.

| Article/site | Stock total source moyen | Physique simulé N | Physique simulé R | Disponible simulé R |
|---|---:|---:|---:|---:|
| 773474/Gien | 17 251 kg | 10 587 kg | 13 295 kg | 10 834 kg |
| 268091/Muret | 806 091 UN | 405 422 UN | 405 422 UN | 405 422 UN |

### 773474 : le besoin calculé ne représente pas assez bien les fabrications exécutées

**Le stock à Gaillac n'empêche pas les transferts effectivement déclenchés.**
Ils sont intégralement servis dans N et R. Le 27 juillet, Gaillac dispose de
35 200 kg et Gien de 6 007 kg ; le moteur ne déclenche pas de transfert,
car son plancher n'est que de 3 897 kg. La photo industrielle du 28 juillet
indique pourtant 23 435 kg à Gien. R ne reçoit rien en juillet, alors qu'il
consomme 9 191 kg. La prochaine arrivée physique est le 9 août.

La projection et l'exécution de fabrication n'utilisent pas le même pilotage :
le plan MRP sur 364 jours déduit les stocks et engagements du dépôt avant de
calculer les fabrications et leurs besoins de composants ; les fabrications
effectivement lancées conservent une commande de dynamique des systèmes,
fondée sur sept jours de prévision, le stock usine, le lissage et les seuils
de déclenchement. Les OF projetés ne sont pas directement exécutés.

| Décision | Besoin BOM 773474 prévu, 39 jours suivants | BOM ensuite consommée en simulation sur ces mêmes jours |
|---|---:|---:|
| 29 juin | 923 kg | 5 793 kg |
| 20 juillet | 805 kg | 4 634 kg |

Le 20 juillet, tous usages compris, le plan prévoit 4 345 kg contre 8 117 kg
ensuite consommés par le simulateur. Le plancher calculé est
`4 344,867 / 39 × 26 = 2 896,578 kg`. Les 39 jours sont la fenêtre de moyenne
initialisée avec transport 10 + revue 1 + sécurité convertie 28, pas l'horizon
MRP, qui reste de 364 jours. Le multiplicateur 26 est la conversion datée des
jours de sécurité à cette décision. **21 des 39 jours n'ont pas de fenêtre I
source sélectionnée**, mais restent au dénominateur : l'absence de ligne ne
prouve pas une consommation industrielle nulle.

La comparaison rétrospective inclut aussi les révisions ultérieures des plans ;
elle n'attribue pas automatiquement tout l'écart à un défaut logiciel. Un
contre-calcul en mémoire, à informations identiques constantes, démontre
néanmoins que le plan peut proposer zéro fabrication quand le dépôt est couvert,
alors que le contrôleur usine lance un lot. Cette divergence est donc structurelle.

**Le gain de R est surtout un changement d'état physique représenté.** Le gain
de stock physique moyen de 2 708 kg se décompose en 2 462 kg retenus à réception
et seulement 246 kg disponibles supplémentaires : environ 91 % du gain physique
moyen est du stock retenu. Ce pourcentage ne décrit pas le gain d'erreur absolue.
Les sources ne montrent que 62 kg moyens de J futur à Gien, avec une seule
occurrence de 3 200 kg. Les six jours ouvrés sont confirmés ; leur assimilation
systématique à six jours de stock physique retenu reste une convention dont la
comparabilité industrielle n'est pas démontrée. J courant est un compartiment
hebdomadaire, pas la preuve d'une disponibilité instantanée à l'heure de la photo.

La consommation N/R est identique : 16 652 kg pour la nomenclature du PF268967
et 50 542 kg d'autres usages estimés. Ces autres usages représentent 75 % de
la consommation simulée ; leur coefficient de 56,696 % du besoin I sélectionné
est une estimation, pas une ventilation industrielle identifiée. Les achats
et transferts ne peuvent pas être calibrés indépendamment de cette hypothèse.

Il reste aussi un problème de calendrier : entrée source de janvier antérieure
à R, aucune réception R en avril–mai, puis transferts en août pendant la fermeture
annoncée. Les consommations complémentaires du 4 au 10 août sont bien nulles ;
on ne leur attribue pas une consommation fictive pendant cette semaine.
Les dates exactes de fermeture restent à définir. En novembre, R dépasse au
contraire certaines photos : +8 424 kg le 17 novembre. Augmenter uniformément
la sécurité ne résoudrait pas la trajectoire.

Le registre des contraintes confirme enfin que **773474 ne bloque aucune
fabrication du PF268967 dans N/R**. Les sorties PF sont identiques les 365 jours,
soit 1 724 800 UN ; les contraintes actives concernent 344135 (182 jours) et
042342 (7 jours). Améliorer le niveau de 773474 ne peut donc pas, à lui seul,
améliorer ce PF dans ces essais.

### 268091 : localisation au printemps, puis quantité et calendrier de fabrication

**Les données fournies ne donnent pas de photo du stock PF268091 à Avène.**
Elles documentent le stock à Muret. L'utilisateur confirme que l'industriel
pousse les PF vers le dépôt ; le maintien de stock usine parce que le dépôt
dépasse une petite cible simulée ne représente pas ce fonctionnement.

Le 30 juin, la source montre 854 402 UN à Muret. N/R y placent 305 449 UN,
mais gardent 526 365 UN à l'usine. Ce stock usine représente presque tout
l'écart local de 548 953 UN. En revanche, cela ne suffit plus ensuite :

| Photo source | Stock réel à Muret | Tout le stock simulé N/R, usine + dépôt + client + transit | Manque même en réunissant ce stock |
|---|---:|---:|---:|
| 28 juillet | 1 050 357 UN | 700 732 UN | 349 625 UN |
| 27 octobre | 1 182 787 UN | 703 664 UN | 479 123 UN |
| 29 décembre | 1 010 323 UN | 676 744 UN | 333 579 UN |

Cette réunion fictive est une borne comptable volontairement favorable au
simulateur, pas une proposition de rapatriement des stocks clients. Elle montre
que la localisation ne peut pas expliquer tout le déficit. Les besoins de
fabrication supplémentaires ainsi déduits sont conditionnels aux sorties
simulées ; ils ne constituent pas une mesure de production industrielle réelle.

**Une prévision déjà connue est perdue au changement de semaine.** Le lecteur
de prévisions PF prend uniquement la dernière version MRP. Sa semaine courante
est volontairement exclue parce que I peut contenir des reports non élucidés ;
mais le moteur ne recherche pas ensuite la prévision antérieure de cette semaine.
Il revient au profil nominal. Les 52 revues du dimanche utilisent ainsi sept
jours nominaux ; 51 disposaient pourtant d'une prévision industrielle antérieure.

| Semaine, convention du scénario | Prévision déjà connue avant la revue | Signal hebdomadaire finalement utilisé |
|---|---:|---:|
| 12 janvier | 188 520 UN, plan du 5 janvier, I546 | 44 772 UN |
| 19 janvier | 618 UN, plan du 12 janvier, I1502 | 68 784 UN |

La perte d'information est démontrée, mais son effet n'est pas toujours une
sous-estimation. Sur les semaines communes, sélectionner une seule prévision
strictement antérieure donne 3 529 078 UN, contre 3 542 731 UN du profil nominal :
le total annuel est proche, tandis que les écarts absolus hebdomadaires cumulés
atteignent 2 530 046 UN. **Le rythme compte autant que le volume annuel.**
Les I restent des besoins prévus, pas des sorties physiques observées.

Les blocages matière existent dans N/R, mais sont circonscrits : 001893 bloque
46 jours du 19 janvier au 5 mars ; 693055 bloque 13 jours du 6 au 18 mars,
puis sept jours du 9 au 15 avril. Il s'agit de **deux campagnes de 28 800 UN**,
finalement exécutées, pas de 66 lots perdus. Additionner les demandes journalières
reportées donnerait à tort 1 900 800 UN de pertes. À campagnes inchangées,
avancer ces deux lots ne déplacerait que 28 800 UN à la fois et ne changerait
pas le total annuel. Une nouvelle simulation pourrait modifier les décisions
ultérieures ; cette borne conditionnelle ne supprime pas les effets de retour.
L'essai PF n'a aucune journée de contrainte matière : son déficit persistant
ne peut donc pas être attribué à ces deux blocages. Les grands écarts tardifs
exigent d'examiner aussi le pilotage, le calendrier et les états du stock.

Le transfert systématique seul avait produit trop de PF : vider l'usine relance
sa commande de fabrication. L'essai PF évite cet emballement mais déduit
immédiatement les 1 945 715 UN des vingt OF initiaux, pourtant disponibles entre
J23 et J145. Une réception lointaine peut donc inhiber une fabrication proche.
La commande brute est négative 256 jours dans cet essai. Le seuil de report
emploie en outre le maximum de lot de 142 485 UN, pas le minimum de 28 800 UN.
Ces mécanismes expliquent pourquoi ajouter le retour du dépôt sans un calcul
des engagements par date ne suffit pas. Les tailles sources sont correctement
chargées ; il ne s'agit pas d'une simple erreur de minimum de lot.

**La présence physique avant disponibilité reste incomplète.** Les plans MRP
de Muret portent en moyenne 104 561 UN en J futur : déjà présents, disponibles
plus tard selon la clarification utilisateur. Le modèle n'a aucun stock PF retenu
à l'usine ou au dépôt. Les vingt OF initiaux gardent leurs dates G/I mais aucune
présence physique entre ces dates ; les nouvelles campagnes sont disponibles
immédiatement à leur achèvement. Le délai source de réception vaut dix jours.
Cela justifie un état physique distinct, sans ajouter aveuglément dix jours à
des OF dont le calendrier les contient déjà. Le départ vers Muret avant ou après
libération reste à confirmer. Aucun appariement exact des 43 positions J futur
à un ou deux OF initiaux n'a été trouvé ; aucune identité de lot n'est inventée.

La décomposition moyenne du déficit local N/R est exactement :
`400 668 = 263 229 (J courant − disponible simulé)`
`          + 104 561 (J futur − retenu simulé)`
`          + 32 878 (photo − total J)`.
Le dernier terme conserve les différences de date/périmètre. Cette identité
n'établit pas des causes indépendantes et ne s'ajoute pas à la décomposition
par lieux ci-dessus. Pour Gien, total J égale la photo dans 51 cas sur 52 ;
pour Muret, aucun des 52 rapprochements n'est exact.

Les bilans K des deux séries MRP se ferment. Cela ne transforme pas H et I
en flux industriels exécutés : le I courant de 268091 vaut en moyenne
508 222 UN par version, avec des reports possibles. Rejouer ces valeurs chaque
semaine comme de nouvelles sorties fabriquerait une demande répétée. Les
prévisions antérieures, les révisions, les stocks physiques J et les photos
doivent donc rester distingués dans le rapprochement.

### Corrections communes justifiées, encore à expérimenter séparément

1. Conserver, pour chaque période, la dernière prévision admissible déjà connue,
   même si une nouvelle version n'en donne pas de valeur exploitable. Distinguer
   absence, zéro explicite et report ; ne jamais utiliser une version future.
2. Faire projeter au plan MRP les mêmes décisions de fabrication que le moteur
   exécute, avec les mêmes stocks, engagements datés et campagnes. Conserver la
   dynamique des systèmes, ses capacités et dépendances à l'état ; supprimer
   la contradiction entre programme prévu et commande effectivement exécutée.
3. Calculer le besoin net par échéance : `max(0, besoins cumulés à t + protection
   à t − stock utilisable initial − réceptions utilisables au plus tard à t)`.
   Un OF disponible après t ne couvre pas un manque avant t. Ce manque daté
   n'est pas automatiquement une nouvelle commande : un engagement tardif
   reste affecté et doit être avancé, réaffecté ou annulé explicitement avant
   son éventuel remplacement. Compter chaque engagement une seule fois et
   arrondir aux lots sources le complément réellement nécessaire.
4. Représenter production, présence physique, libération et transfert sans créer
   de quantité supplémentaire ; appliquer la poussée vers Muret à l'état métier
   confirmé. Vérifier séparément les usages complémentaires, la fermeture et
   les engagements de transfert initiaux non identifiés.

Il faut comparer les décisions, réceptions, consommations, stocks disponibles
et stocks physiques, ainsi que les périodes de surstock, avant de retenir une
correction. Une meilleure courbe physique ou un bilan matière fermé ne suffit
pas à certifier le système MRP industriel.

### Preuves de cette contre-analyse

Les calculs ont été effectués avec `python -B`, en lecture des Excel et CSV
existants. Les 730 bilans journaliers N/R de 773474 ferment ; 46 fenêtres complètes
de 39 jours ont été recalculées. Un second agent a contre-vérifié directement
2 926 valeurs depuis les sources, dont les décompositions et les deux fenêtres
BOM détaillées. Le cas contrôlé de divergence entre plan et exécution ne fait
que des calculs en mémoire. Aucune simulation supplémentaire ni revue navigateur
n'a été exécutée : moteur et HTML inchangés. Le gate natif revérifie les preuves
techniques antérieures R/PF, sans nouveau certificat de calibration.

[Manifeste de l'audit](../../artifacts/testing/mrp_stock_gap_audit_20261002/delivery.json),
[773474 : flux et décisions](../../artifacts/testing/mrp_stock_gap_audit_20261002/773474/report.json),
[268091 : sources et bilans](../../artifacts/testing/mrp_stock_gap_audit_20261002/268091/report.json),
[contre-calcul indépendant](../../artifacts/testing/mrp_stock_gap_audit_20261002/268091/independent_crosscheck.json),
[chemins du moteur](../../artifacts/testing/mrp_stock_gap_audit_20261002/code/code_path_audit.json).
La [comparaison HTML existante](../../resultats/mrp_push_internal_20261002/comparaison.html)
reste accessible et conserve tous les essais ; elle n'est pas présentée comme
un nouveau résultat amélioré par cette analyse.

## Confirmation industrielle : les PF sont poussés au dépôt — 2 octobre 2026

L'utilisateur précise que l'industriel pousse les produits finis vers le centre
de distribution. Le maintien d'un stock usine uniquement parce que le dépôt
dépasse sa cible simulée ne représente donc pas cette règle métier.

Les sources examinées ne fournissent **aucune photo du stock PF 268091 à
Avène/1810** : les 53 photos d'inventaire et les 2 528 lignes Flow MRP du PF
portent sur Muret/1920. L'ancien inventaire comporte également ce PF au dépôt.
Les 20 lignes O.Proc d'Avène dans Extract_En_cours sont des ordres/réceptions
prévus, pas un inventaire de PF à l'usine. Le zéro initial usine du graphe
est explicitement une hypothèse ; l'absence de photo n'établit pas que le
stock industriel était nul. Preuve :
`artifacts/testing/mrp_push_internal_20261002/independent/source_pf_avene.json`.

Cinq essais annuels isolés exécutés à partir de N, sans changer les sources :

- **P** : demander le transfert des PF fabriqués, libérés et non déjà réservés
  vers leur dépôt unique, en conservant les contraintes de transport et les
  quantités UN entières. La règle est structurelle, applicable aux deux PF.
- **T** : anticiper les besoins des composants transférés des jours de sécurité
  source, au lieu du plancher calculé avec la moyenne sur 39 jours. Sélection
  structurelle des composants internes éligibles, dont 773474 et 693055 ;
  consommation physique, usages complémentaires et engagements conservés.
- **PF** : coupler P au retour existant du stock usine/dépôt vers la commande
  de fabrication. Ce contrôle est testé séparément, car vider l'usine ne doit
  pas déclencher automatiquement un nouveau lot si le dépôt est déjà couvert.
- **U** : arrondir les propositions de transfert au multiple physique déjà
  porté par la liaison, puis réutiliser le surplus à destination avant
  l'explosion des besoins amont. Dans ce graphe, seul 773474/Gien est éligible
  (3 200 kg). La cadence de transport ne change pas.
- **R** : appliquer les six jours ouvrés de traitement à réception de
  773474/Gien, en séparant arrivée physique et disponibilité, et en prolongeant
  le délai utilisé pour anticiper le transfert. Aucun paramètre de sécurité
  ni de quantité n'est augmenté pour rapprocher les courbes.

Chaque essai a achevé 365 jours avec code retour nul et empreintes des entrées
inchangées pendant son exécution. Erreur absolue moyenne aux 52 photos,
comparées à la clôture simulée de la veille, sans interpolation :

| Version | 773474/Gien (kg) | 268091/Muret (UN) | 268967/Muret (UN) | Décision |
|---|---:|---:|---:|---|
| N, référence conservée | 7 037 | 402 313 | 172 404 | Référence, toujours imparfaite |
| P, transfert PF seul | 7 463 | 1 214 464 | 231 261 | Non retenu : surproduction |
| T, sécurité datée interne seule | 7 690 | 402 313 | 172 404 | Non retenu : Gien se dégrade |
| U, lots de transfert dans le plan | 7 037 | 402 313 | 172 404 | Cohérence corrigée, stock Gien inchangé |
| PF, transfert PF et retour du dépôt | 6 389 | 433 765 | 399 541 | Non retenu comme nouveau nominal |
| R, traitement à réception source | 5 092 | 402 313 | 172 404 | Amélioration de Gien, calibration encore incomplète |

P lance 4 550 400 UN de nouvelles fabrications 268091, contre 1 872 000 dans N :
l'ancien contrôleur interprète l'usine vidée comme un besoin de produire. PF
supprime cet emballement (1 814 400 UN), mais ne retrouve pas les bons niveaux
de stock. Le contrôle sur les 29 couples article/site donne respectivement
P : 16 erreurs moyennes améliorées, 12 dégradées ; T : 3/2 ; U : 1/0 ;
PF : 10/18 ; R : 3/0. Les autres couples sont inchangés. Ce décompte ne remplace pas
l'examen des deux PF, des stocks nuls et du service. Le service annuel des
deux PF reste identique à N ; la conservation ne certifie pas la calibration.

Le push respecte les lots physiques de transport : pour 268091, un reliquat
inférieur à 14 400 UN peut rester temporairement à l'usine (maximum 12 200
dans P/PF). Il ne laisse plus les centaines de milliers d'unités observées
uniquement dans l'ancienne simulation. Il ne prouve pas un stock usine réel nul.

**Pourquoi U ne résout pas Gien.** Les 365 stocks et les 18 expéditions sont
exactement identiques à N : 60 800 kg transférés, première réception le
15 février. U corrige bien 1 587 propositions dans les 52 révisions du plan,
mais l'exécution arrondissait déjà ses expéditions. Gaillac dispose d'assez
de stock aux 18 décisions : aucun de ces transferts n'est rationné par l'amont.
La revue hebdomadaire reporte les demandes hors de ses jours d'exécution.
Cela peut expliquer quelques jours, pas l'entrée industrielle de janvier.

**Paramètre source manquant dans la référence N.** Les 2 111
lignes de 773474/Gien, sur les 52 versions du Flow MRP, portent toutes
`Temps de réception en jours = 6` (première occurrence : `Feuille1!E941`).
La référence N applique seulement les dix jours de transport.
Le fichier ne précise pas le calendrier, mais **l'utilisateur confirme le
2 octobre 2026 qu'il s'agit de jours ouvrés lundi–vendredi**. Le cinquième
essai R a été exécuté : transport inchangé, arrivée en stock physique retenu,
puis disponibilité après six jours ouvrés. Le contrat de réception interne
est généralisé par une nouvelle version structurelle ; l'ancien cas 693055
reste inchangé. R configure seulement 773474/Gien pour isoler son effet.
Six jours ouvrés après l'arrivée ne sont pas six jours calendaires ; les
jours de sécurité source ne sont pas augmentés de six jours.

R avance la première réception physique au **25 janvier**, contre le
15 février dans N, et libère ce lot le **3 février**. L'entrée industrielle
reste antérieure (hausse entre les photos du 13 et du 20 janvier). Le stock
physique moyen simulé à Gien passe de **10 587 à 13 295 kg**, contre
17 251 kg dans les photos ; l'erreur moyenne baisse de **27,6 %**. Le stock
disponible reste positif. Les quantités retenues sont suivies pendant 130
jours, sans seconde entrée à leur libération, et les engagements sont
comptés une seule fois. Les stocks PF et le service restent inchangés.

L'avancement final de 21 jours n'est pas une conversion de six jours ouvrés :
il résulte aussi des replanifications et de la revue hebdomadaire. Au plan
initial J4, le disponible et le plancher sont identiques à N ; la première
proposition reste disponible J48, mais son lancement est anticipé de J38
à J30. Les 6 400 kg inscrits dans H source en janvier ne sont pas identifiés
à la première réception simulée R de 3 200 kg.

La règle exécutée est : `arrivée G = départ + délai de transport` puis
`disponibilité I = ajouter_jours_ouvrés(G, traitement source)` ; le jour G
n'est pas compté dans le traitement. Pour le plan de la revue j, la règle
actuelle reste `délai_effectif(j) = ajouter_jours_ouvrés(j + transport,
traitement) − j`, appliqué comme décalage unique aux propositions de cette
revue. Ce dernier raccourci explique la limite de calendrier ci-dessous.

La validation n'efface pas les limites : à Gaillac, le minimum de 773474
descend de 6 400 à 3 200 kg, et 021081 passe de 50 à 51 jours sous son
plancher de 900 tonnes. Les dates réelles des transferts simulés et des
libérations suivent exactement le calendrier ; les **propositions futures**
emploient encore un délai scalaire recalculé à chaque décision. Sur les
11 892 propositions contrôlées, 8 505 correspondent au calendrier exact,
1 675 prévoient la disponibilité un jour trop tôt et 1 712 deux jours trop
tôt. Corriger cette approximation constitue une suite identifiée, distincte
de l'intégration du délai source désormais testée.

**Limite restante du pilotage des PF.** F utilise une position globale
`disponible usine + disponible dépôt + engagements futurs + campagne restante
+ encours`, comparée aux cibles usine/dépôt et au retard. Les engagements
lointains y comptent immédiatement. La projection sur 52 semaines n'exécute
toujours pas directement ses propositions d'OF. Il faut traiter les dates
de disponibilité et de besoin avant de présenter le push couplé comme une
reproduction du MRP industriel. Le stock client est exclu de cette position.

Comparaison interactive :
[essais 2025](../../resultats/mrp_push_internal_20261002/comparaison.html).
Rapports d'exécution : `artifacts/testing/mrp_push_internal_20261002/report_*.json`.
Contre-calculs indépendants : `independent/review_P.json`, `review_T.json`,
`review_U.json`, `review_PF.json`, `transfer_lots_U.json`,
`review_R.json`, `receipt_calendar_R.json`, `U_exact_comparison.json`,
`receipt_773474_source.json`, dans le même dossier
d'étude. La preuve agrégée et les contrôles HTML sont référencés par son
`delivery.json`.

Le calendrier exact de fermeture n'est pas modifié. Seul R étend le
traitement à réception, pour 773474/Gien. Les nouveaux
mécanismes restent opt-in ; les références annuelles antérieures sont conservées.
Aucun essai n'est promu en nouveau nominal. U reste une correction de cohérence
disponible par option, sans promesse d'amélioration du stock industriel.

## Audit approfondi 773474/Gien et 268091/Muret — 2 octobre 2026

Périmètre : lecture des sources Excel, du code et des résultats annuels **N**
(`experiment/run_industrial_internal_365`), avec **I** comme témoin. Cet audit
initial en lecture seule précède les cinq essais présentés ci-dessus. Les deux produits
appartiennent à des chaînes distinctes : 773474 → 268967 à Gien, et
693055 → 268091 à Avène. Les chiffres ci-dessous ne supposent pas que
773474 intervient dans la fabrication de 268091.

### 773474 : des transferts trop tardifs et une consommation mal identifiée

Aux 52 rapprochements dimanche simulé/lundi source, le stock moyen est de
**10 587 kg contre 17 251 kg**, soit un déficit moyen de 6 664 kg. Le bilan
quotidien se ferme ; J total correspond aux photos dans 51 cas sur 52.
L'écart est physique dans le modèle, et non créé par le tracé du graphique.

La règle effectivement appliquée aux achats externes anticipe les besoins
datés du délai de sécurité. Pour ce transfert interne, le code utilise une
autre règle : **plancher = max(stock fixe source, besoin moyen connu sur
39 jours × sécurité convertie en jours calendaires)**, avec 20 jours ouvrés
source. Le transfert se déclenche à l'approche de ce plancher, avec une
revue hebdomadaire, des multiples de 3 200 kg et dix jours de trajet. Cette
différence de traitement n'est pas une distinction industrielle démontrée.

Exemple du plan du 5 janvier : le stock disponible simulé vaut 13 552 kg,
le plancher 4 894 kg et la première insuffisance est projetée au 18 février.
La version N finit par recevoir son premier transfert le **15 février**.
Pourtant, le premier plan source comporte déjà **6 400 kg au repère du
12 janvier**, et la photo remonte de **13 566,4 kg le 13 janvier à
16 773,2 kg le 20 janvier**. La simulation ne reçoit rien en janvier.
Cette hausse réelle est une preuve de mouvement net positif, pas une preuve
que les 6 400 kg ont été réceptionnés intégralement à une date précise.
Le caractère engagé de cette entrée H n'est pas documenté par un identifiant
d'ordre ; elle ne doit pas être transformée arbitrairement en commande ferme.

Le déphasage se répète en été :

| Mois simulé | Réceptions | Consommation totale | Plancher opérant moyen |
|---|---:|---:|---:|
| Juillet | 0 kg | 9 190,6 kg | 4 014,1 kg |
| Août | 16 000 kg | 3 142,9 kg | 11 276,8 kg |

Les photos de Gien restent à **22 381,2 kg les 4, 11, 18 et 25 août**.
N reçoit les 9, 16, 23 et 30 août et fabrique du 773474 à Gaillac les
14, 15, 16, 21 et 22 août. La fermeture de deux ou trois premières semaines
d'août signalée par l'utilisateur n'est pas matérialisée par un calendrier
général de fabrication/transfert dans ce scénario. Les dates exactes et les
opérations concernées restent à fixer. Un stock stable seul n'exclut pas
des entrées et sorties qui se compensent.

La consommation complémentaire reste une hypothèse importante, mais
**l'audit ne trouve pas de double ajout de 100 % des besoins MRP** :

`consommation physique = BOM réellement exécutée + 56,696 % × I prévu`

La seconde partie utilise le dernier plan connu avant chaque semaine et
est répartie sur sept jours ; ce n'est pas une mesure de consommation.
Le pourcentage initial est constant mais les besoins sont révisés. Cela
explique pourquoi les autres usages passent de 30 920 kg dans le premier
plan à **50 542 kg exécutés**. Sur les 45 semaines renseignées et exécutées,
les prévisions I retenues totalisent 89 145 kg, contre 64 406 kg de sorties
physiques simulées sur ces mêmes périodes. Retirer les autres usages parce
que le stock est trop bas n'est donc pas justifié par cette seule comparaison.
La fraction de partage reste non identifiée ; les besoins prévus ne sont
pas des prélèvements constatés. Sous hypothèse d'absence d'ajustement
d'inventaire, les seules baisses des photos imposent au moins 42 511 kg
de sorties entre le 1er janvier et le 29 décembre, sans borne haute connue.

### 268091 : localisation, niveau visé et exécution des fabrications

Le stock moyen à Muret est **405 422 UN simulées contre 806 091 UN dans
les photos**. Mais le modèle détient aussi, aux mêmes dates, 154 100 UN à
Avène, 168 865 UN chez le client et 52 368 UN en transport. L'identité est :

`photo Muret − stock Muret simulé`
`= stock simulé hors Muret + (photo Muret − stock total simulé du réseau)`

En moyenne : **400 668 = 375 334 + 25 335 UN** (arrondis). Cette décomposition
ne permet pas de remplacer la courbe Muret par une somme de sites. Elle
montre que la répartition pèse fortement sur l'écart. La moyenne annuelle
masque aussi un surplus du réseau en première partie d'année et un déficit
en seconde partie. Avec une comparaison à la clôture du jour même de la
photo, les constats restent :

| Photo 2025 | Muret source | Muret simulé | Avène simulé | Tout le réseau simulé, transit compris |
|---|---:|---:|---:|---:|
| 30 juin | 854 402 | 305 449 | 526 365 | 969 785 |
| 28 juillet | 1 050 357 | 245 543 | 310 365 | 686 845 |
| 27 octobre | 1 182 787 | 455 643 | 0 | 692 220 |
| 29 décembre | 1 010 323 | 469 383 | 0 | 659 878 |

**Mécanisme démontré en juin :** Avène conserve 526 365 PF disponibles,
mais aucun transfert n'est ordonné pendant les trente jours. Chaque jour,
le stock et les réceptions déjà prévues couvrent la cible locale calculée
pour Muret. Le 30 juin, cette cible vaut 268 366 UN pour 305 449 UN présentes :
le besoin de transfert est nul, alors que la photo industrielle vaut
854 402 UN. Le moteur satisfait sa propre règle, mais celle-ci ne reproduit
pas le niveau industriel. Une pénurie de composants ne peut expliquer ce
stock disponible immobilisé en usine.

**Le client constitue un second décalage de périmètre.** Le scénario lui
attribue une cible de 14 jours, sans photo industrielle correspondante dans
les sources. Cette réserve provoque des sorties anticipées de Muret vers
un autre stock simulé. Elle doit être distinguée d'une sortie industrielle
constatée du dépôt ; elle ne doit pas être comptée comme stock réel Muret.

**L'horizon de 52 semaines ne pilote pas encore les lancements PF.** Les
365 calculs de projection existent, mais les propositions de fabrication
restent indicatives. La commande exécutée à Avène est toujours :

`brut = prévision moyenne 7 jours + 0,25 × (cible usine − stock usine)`
`commande = max(0, 0,20 × commande précédente + 0,80 × brut)`

La cible usine vaut zéro ici. Le stock Muret n'entre pas dans cette formule.
Avec la condition de lancement liée au stock local et l'arrondi par lots,
les **65 campagnes neuves font toutes 28 800 PF** ; la commande journalière
maximale n'atteint que 24 852 PF, sous le minimum de campagne. Cela ne prouve
pas que l'industriel produit toujours par 28 800. Les contraintes source
permettent des multiples de 14 400 jusqu'au plus grand multiple admissible
sous 142 485, soit 129 600 PF.

Les deux campagnes retardées par 001893 et 693055 finissent au printemps.
À campagnes acceptées inchangées, avancer leur exécution ne libérerait
jamais plus de 28 800 PF supplémentaires simultanément et ne changerait
pas le volume annuel. Une nouvelle simulation pourrait modifier aussi les
campagnes ultérieures : cette borne n'est pas un scénario sans contrainte.
Les 20 OF initiaux, totalisant 1 945 715 PF, sont bien repris et tous disponibles
au 26 mai. Aucun OF initial ni encours de ces campagnes ne manque en fin d'année.

Enfin, les états industriels restent à représenter : le 29 décembre,
J contient **528 318 PF immédiatement disponibles et 462 600 PF déjà
physiquement présents mais disponibles plus tard**. N n'a aucun stock bloqué
au dépôt. La comparaison au seul disponible réduit ce jour-là l'écart mais
ne le résout pas sur l'année : l'écart moyen J courant/Muret simulé reste
263 229 PF. Il ne faut ni consommer automatiquement I courant, souvent
révisé ou reporté, ni ajouter J futur comme une nouvelle réception à chaque plan.

### Ordre de correction issu de cet audit

1. Distinguer les décisions de stock local, le stock physique de chaque site
   et les engagements uniques ; revoir la réserve client non observée et
   le blocage des transferts PF malgré du stock usine disponible.
2. Faire alimenter le pilotage SD des fabrications et des transferts par
   les besoins nets datés du même plan MRP, avec une anticipation cohérente,
   les contraintes source de lot et un horizon glissant. Préserver les
   bilans physiques et les engagements, sans lancer deux fois une proposition.
3. Définir les calendriers d'ouverture applicables et les états disponible/
   indisponible, puis revoir les engagements de démarrage documentés.
4. Qualifier séparément les usages partagés. Une consommation estimée ne
   devient pas industrielle parce qu'elle améliore une courbe.

Le précédent essai F de retour du stock global vers la production a dégradé
les résultats ; il reste rejeté. L'audit ne préconise pas de simplement
additionner tous les stocks dans le correcteur ni de doubler la sécurité.

Preuves sous `artifacts/testing/mrp_finished_goods_20261002/` :
`773474_deep_audit/review.json`, `pf268091_deep_audit/report.json`,
`stock_placement_audit/report.json` et contre-vérification indépendante
`773474_deep_audit/pf_placement_crosscheck.json`. Les sources et CSV sont
empreintés avant/après ; les 365 bilans réseau PF se ferment exactement.
Qualification native CSV :
`deep_audit_native/qualify-2a7465c9aaaa41b1b0d2e45c79cf555d/manifest.json`.
Ces contrôles établissent les mécanismes exécutés ; ils ne certifient pas
la calibration industrielle. La documentation est mise à jour, le moteur
et les résultats comparés sont conservés.

## Chaîne de Gien : stock erroné et contrainte de fabrication — 2 octobre 2026

Le couple source est **773474/Gien** (773447 absent du catalogue). La chaîne
BOM est 773474 → 268967 fabriqué à Gien → 268967 à Muret. Une courbe qui
commence par une photo de 430 538 UN au dépôt concerne 268091, fabriqué à
Avène ; la photo initiale de 268967 vaut 1 101 534 UN. La carte nomme désormais
l'article et le site dans le titre de la courbe et permet de passer entre
les stocks liés par la nomenclature modélisée, sans changer les filtres.

Le mauvais niveau de 773474 n'est pas un simple artefact de périmètre :
J total MRP correspond exactement aux photos dans 51 rapprochements sur 52.
Le seul écart vaut 1 467,6 kg au 3 mars. J futur n'apparaît que dans un plan,
pour 3 200 kg ; ce stock non encore utilisable ne suffit pas à expliquer
l'écart moyen de 6 663,87 kg entre les photos et N.

Dans les deux simulations I/N, le registre de décision **avant production**
prouve toutefois que 773474 ne limite aucun des 205 jours de campagne active.
Un lot de 107 800 PF requiert 1 040,7786 kg de 773474. Le minimum disponible
avant fabrication est 1 648,809 kg dans I et 4 848,809 kg dans N. Les autres
limitations enregistrées sont 344135 pendant 182 jours et 042342 pendant
sept jours ; aucun jour n'est limité par la capacité. Il s'agit de contraintes
du simulateur, pas de ruptures industrielles démontrées. Une campagne du
18 mars ne produit que le 28 avril, après 41 jours limités par 344135.

Les 365 chronologies de production/libération, 16 campagnes, 170 expéditions
PF et 1 095 stocks quotidiens Gien/Muret/client sont identiques dans I/N.
Les deux calculs produisent 1 724 800 PF, expédient 1 617 000 PF de Gien à
Muret, et terminent avec 1 025 964 PF à Muret. Le lien causal physique existe,
mais le stock de 773474 n'est pas la contrainte active dans ces deux essais.

Un autre poste doit être confirmé :
`stock773 fin = 14 593 + 60 800 − 16 652,458 BOM − 50 541,767 autres usages
             = 8 198,775 kg`.
Les 50,54 tonnes sont une **consommation estimée** à partir de prévisions,
pas un prélèvement industriel documenté. La fraction initiale de 56,696 %
compare la demande PF brute aux besoins matière, sans déduction du stock PF
initial. Elle ne démontre ni le partage ni la quantité des autres usages.
Le partage confirmé pour 693055, 730384 et 708073 ne vaut pas confirmation
pour 773474. Une clarification spécifique a donc été demandée ; aucune
suppression de consommation ni nouvelle cible arbitraire n'est appliquée.

Preuves : `artifacts/testing/mrp_finished_goods_20261002/gien_chain_causality/report.json`
et `gien_source_scope/review.json`. Carte avec navigation des chaînes :
`resultats/mrp_finished_goods_20261002/comparaison_chaine_gien.html`.

## Confirmation métier du 2 octobre 2026 : ressources partagées

L'utilisateur confirme que **693055, 730384 et 708073 servent plusieurs
produits**. Cette confirmation porte sur l'article, pas sur une proportion
de consommation, une liste d'autres PF ou une allocation par site. Elle est
conservée dans l'estimateur sous `user_confirmed_item_shared` ; l'allocation
reste explicitement non confirmée. Les sources Excel restent inchangées.

Dans les essais I/N déjà calculés, 693055/Avène dispose d'un complément
physique estimé à 82,17 % du besoin du premier plan et 708073/Gien à 38,63 %.
Ces pourcentages sont des hypothèses de calcul, **pas des données validées
par cette confirmation utilisateur**. La projection peut reprendre le total
I tout en déduisant la BOM propre ; cela ne convertit pas tout I en une
consommation du seul PF étudié.

Pour 730384/Gien, **aucun complément physique n'était activé** : l'estimateur
avait comparé 252 062,8 M de I renseignés sur seulement 12 semaines futures
à 518 562,1 M de besoin théorique BOM sur l'horizon PF. Ce bilan incomplet
ne prouve pas que l'article soit exclusif au PF. La confirmation métier est
donc conservée même lorsqu'aucune quantité complémentaire n'est déterminée.
Ces 12 lignes sont éparses du 30 mars au 14 décembre, pas douze semaines
consécutives ; deux portent un I explicitement nul. Le calcul de BOM utilise
la demande PF brute sans déduire les PF déjà détenus. Or le plan du 5 janvier
porte 981 240 UN immédiatement disponibles et 108 017 UN disponibles plus
tard, et ne projette aucune entrée PF jusqu'au 4 mai inclus. Le stock de PF
réduit donc la fabrication nécessaire et les besoins de composants associés.
Le bilan des semaines complètes de ce plan confirme 871 992 UN de sorties
futures couvertes par la baisse nette du stock, plutôt que par de nouvelles
entrées H. H au dépôt n'identifie toutefois pas directement une fabrication
ni un prélèvement matière. Preuve indépendante :
`artifacts/testing/mrp_finished_goods_20261002/shared_scope_confirmation/review.json`.
Il faut rapprocher les périodes couvertes et les périmètres avant d'attribuer
une part aux autres produits. Le standard de commande 92 500 M demandé
par l'utilisateur reste inchangé ; aucune consommation n'est ajoutée au
hasard pour compenser l'absence de mesure.

## Fabrications, produits finis et cinq règles exécutées — 2 octobre 2026

Périmètre : première année, du 1er janvier au 31 décembre 2025. Le moteur
calcule au **jour** ; les courbes hebdomadaires additionnent les flux, jamais
les niveaux de stock. À la demande de l'utilisateur, le calcul supplémentaire
sur cinq ans a été arrêté ; ses sorties partielles ne sont pas des résultats
comparables. Les références antérieures achevées restent conservées.

### Résultats de la contre-analyse des produits finis

**État des essais annuels :** la comparaison `comparaison_production.html`
conserve le scénario I, avec sécurité fabrication et plancher de sécurité
sur les transferts internes. Face au scénario S (sécurité fabrication seule),
17 couples article–site se rapprochent des photos, 11 s'en éloignent et un
reste identique. L'erreur absolue moyenne de 773474/Gien passe de 12 303 à
8 970 kg ; celle de 268091/DC passe de 490 814 à 402 313 UN. Ces écarts
restent importants. Le nombre de jours de production bloqués par 693055
passe de 96 à 33. Le service client ne change pas.

L'essai F ajoute un retour du stock de tout le réseau PF (usine, dépôt et
engagements comptés une fois) vers le correcteur de fabrication, avec la
protection dépôt correspondante dans la projection. Il passe les invariants
physiques et 1 460 contrôles indépendants de phase, mais dégrade la
calibration : 10 couples améliorés, 18 dégradés, un inchangé. L'erreur
268091/DC monte à 487 776 UN, celle de 268967/DC à 372 591 UN. **F n'est
pas retenu comme nouvelle référence.** Le flag reste optionnel, absent du
scénario I. Preuves : `experiment/report_feedback.json`,
`pf_feedback_validation/postrun.json`, sous
`artifacts/testing/mrp_finished_goods_20261002/`.

**773474, diagnostic détaillé :** la BOM source rattache 773474 à 268967,
et 693055 à 268091. Les deux chaînes présentent des problèmes de pilotage
comparables, mais 773474 n'est pas le composant BOM de 268091.

- Le plan source du 5 janvier prévoit 6 400 kg de 773474 à Gien au repère
  du 12 janvier (`Flow_Data_MRP_results.xlsx`, Feuille1, H942). Le scénario
  I ne reçoit son premier transfert que le 22 février (3 200 kg).
- La réconciliation des besoins industriels I couvrait 22 achats externes,
  pas les composants transférés. Pour Gien, le moteur projetait la BOM
  propre et un complément d'autres usages estimé à 56,696 % du besoin
  source. La première consommation BOM propre projetée au 5 janvier était
  située à J170, alors que l'exécution fabrique déjà 107 800 PF à J0.
- À J4, le moteur voit 13 552,221 kg disponibles, une protection de
  4 278,071 kg et 9 343,856 kg de besoins cumulés à J72. Il ne propose
  donc que `4 278,071 − 13 552,221 + 9 343,856 = 69,705 kg`, à recevoir
  à J72. Le retard de proposition est reproductible : ce n'est pas une
  absence de stock à Gaillac.
- Une règle historique propre à la route impose des transferts par
  3 200 kg et une revue tous les sept jours, calée sur J0 (mercredi).
  Elle retarde encore J41 à J42, sans expliquer à elle seule janvier.
  Cette cadence est une hypothèse codée, pas une règle ERP démontrée.
- Le carnet initial fourni ne contient pas de transfert 773474 vers Gien.
  Il contient un OF Gaillac de 3 200 kg. L'absence dans cet extrait ne
  prouve pas l'absence d'un ordre industriel. Une semaine MRP ne permet
  pas non plus d'affirmer sa date exacte de lancement.

Preuves : `chain_timeline/report.json` et
`sources/intermediate_links_v2.json`, sous le même dossier. Les calculs
sources en G sont convertis en KG pour ces valeurs affichées.

**Essai N : besoins industriels des composants internes.** Le moteur applique
désormais aussi la réconciliation existante aux composants BOM transférés
entre sites internes, protégés par une politique source et sans fabrication
locale de ce même article–site. Son activation exige les séries I versionnées
et le flag de protection interne ; le scénario I antérieur est conservé.

```text
semaine source connue : complément neuf = max(0, I source − besoin BOM propre)
besoin total projeté = besoin BOM propre + complément neuf
                    = max(I source, besoin BOM propre)
```

L'ancien complément estimé est retiré sur les jours couverts. Exemple :
I=100, BOM=60, ancien complément=30 donnent un nouveau complément de 40,
donc un total de 100, pas 130. Une semaine absente reste inconnue et conserve
la prévision antérieure ; un zéro explicite n'efface pas une BOM nécessaire.
Les commandes engagées sont déduites une fois avant propagation amont.
Les consommations physiques estimées d'autres usages restent inchangées.
Les 4 123 valeurs ajoutées reproduisent directement les I sources en G,
sans injecter les H comme réceptions et sans utiliser une version future.

Résultat sur 365 jours, comparé à I : **8 couples améliorés, 11 dégradés,
10 identiques**. 773474/Gien : erreur moyenne 8 970 → 7 037 kg, minimum
1 649 → 4 849 kg, première réception 22 → 15 février ; le plan source
prévoit toujours une entrée en janvier. 693055/Avène : erreur 825 → 695 kg,
stock nul 93 → 66 jours, blocages de production associés 33 → 20 jours.
**Les stocks PF aux dates des photos et les volumes annuels produits restent
inchangés. N corrige un défaut de périmètre de planification, mais ne résout
pas les écarts de stock des PF et n'est pas promu en nominal global.**

La comparaison `resultats/mrp_finished_goods_20261002/comparaison_besoins_internes.html`
présente les trois étapes et les flux de production. Preuves du même dossier
d'audit : `experiment/report_industrial_internal.json` (RC0, 432,922 s,
sources figées), `industrial_internal_validation/source_graph.json`,
`oracle.json` et `postrun.json` (4 214 fenêtres et 730 planchers vérifiés).
Les 40 tests ciblés incluent la suppression d'un résidu de calcul infinitésimal
avant qu'il ne puisse déclencher un lot amont entier.

Le retard initial de 773474 a été recomposé : à J4, le plancher vaut
`7 341,327 / 39 × 26 = 4 894,218 kg`. Les 39 jours comprennent 11 jours
sans fenêtre I fournie et sept jours explicitement à zéro ; les bases
modélisées sont nulles sur les jours non renseignés. Gaillac dispose de
16 000 kg aux premières revues, mais aucune quantité n'est encore due selon
ce plan. La révision du 2 février augmente la cible ; la cadence hebdomadaire
repousse l'envoi au 5 février, avec réception le 15 février. Le plancher
daté n'est pas la cible historique générique également présente dans les
traces. Preuve : `industrial_internal_validation/early_773474.json`.

Appliquer en mémoire l'anticipation de 20 jours ouvrés déjà utilisée pour
les achats, avec F=0 et le même délai interne de dix jours, avance la
première proposition du plan J4 : départ J26, disponibilité J36, plutôt
que J38/J48. La cadence inchangée autoriserait au plus tôt J28/J38, avant
prise en compte des révisions suivantes. **Cela n'explique toujours pas
l'entrée source de janvier.** Ce calcul sur snapshots ne constitue ni un
nouveau pilote annuel ni une nouvelle règle activée dans le moteur.

Pour 268091, les 52 plans donnent en moyenne J courant=668 652 UN,
J futur=104 561, K courant=373 069. Le modèle I possède en moyenne
405 422 UN aux dates des photos, contre 806 091 dans l'inventaire réel.
La proximité de sa moyenne avec K ne signifie pas qu'il représente K :
la corrélation est −0,065 et l'erreur correspondante 231 838 UN.
L'identité `J total − K courant = J futur + I courant − H courant`
explique un écart de grande taille entre deux états du plan, mais ne prouve
pas que I courant soit un stock réservé ou des ventes réalisées. Il serait
incorrect de l'ajouter chaque semaine à la demande physique pour relever
artificiellement le stock ou de comparer le modèle à K à la place des photos.

L'amélioration matière I → N a un effet réel mais bref : un lot de 28 800
PF268091 devient disponible le 16 avril au lieu du 30 avril, arrive au dépôt
le 18 avril, puis l'expédition usine suivante diminue du même montant.
Les stocks dépôt se rejoignent le 20 avril. Le gain intermédiaire n'apparaît
donc pas aux photos hebdomadaires comparées. En fin d'année, le bilan PF
complet est `430 538 + 3 817 715 − 3 576 442 = 671 811 UN`, réparties
entre usine, dépôt, client et transit : il n'y a pas de perte de quantité
cachée dans le transfert. Additionner ces emplacements au stock du seul
dépôt serait un changement de périmètre injustifié. Preuves :
`pf_stock_scope/report_v2.json` et `pf_stock_scope/delta_I_N_v2.json`.

L'oracle indépendant reconstruit **730 décisions quotidiennes usine → dépôt**
des deux PF, sans écart avec les expéditions du registre. Il contrôle la
mécanique à partir des cibles exportées, pas la validité industrielle de ces
cibles. Preuve :
`artifacts/testing/mrp_finished_goods_20261002/engine/report.json`.

Le 28 décembre, pour 268091, le dépôt vise 469 588 UN, possède 37 383 UN et
demande 432 205 UN. L'usine n'a aucun PF disponible à expédier ; la campagne
est matériellement bloquée par 693055. Les événements de 2025 identifient
96 jours bloqués par 693055, 46 par 001893 et trois par 029313. Ces comptes
portent uniquement sur les jours ayant un événement de production.

La fabrication ne reçoit pas directement ce déficit dépôt : son correcteur
observe le stock **usine** et la prévision moyenne sur sept jours. Pour les
PF, sa cible locale vaut zéro, faute de politique source affectée à cette
position. Recopier la sécurité dépôt à l'usine doublerait arbitrairement la
protection. L'absence de retour du déficit dépôt vers ce correcteur reste
un mécanisme à corriger et à tester séparément.

La demande physique de 268967 est de **1 575 986 UN/an** dans `demand_PF.xlsx`.
Les besoins I des 51 semaines suivantes, chacun pris une seule fois dans
le dernier plan strictement antérieur, totalisent **3 199 882 UN**. Pour
268091, les mêmes grandeurs sont 3 576 442 et 3 529 078 UN. Les I restent
des prévisions, pas des ventes constatées : il faut rapprocher les périmètres
avant de remplacer la demande physique du médicament. Preuve et méthode :
`artifacts/testing/mrp_finished_goods_20261002/sources/source_comparison.json`.

Autre convention importante : la semaine courante du plan source est exclue
du signal, car ses reports ne sont pas résolus. Le signal de production sur
sept jours utilise donc environ **42 % de jours source et 58 % de jours du
profil nominal** en 2025. Le dépôt, avec une fenêtre plus longue, utilise
davantage le plan source. Aucune de ces proportions n'est une règle ERP.

Les plans contiennent du J futur, déjà physiquement présent mais disponible
plus tard : moyenne de 104 561 UN pour 268091 et 143 975 UN pour 268967.
Le modèle courant n'a aucun stock indisponible au dépôt pour ces PF. Cet
écart d'état n'autorise ni à créer une réception, ni à déduire une durée de
quarantaine de toutes les lignes de réception du fichier.

**Conflit ancien/récent retrouvé dans les sources :** les 20 jours de sécurité
de 268091 figurent bien dans `Extract_Données_Complémentaires.xlsx`, onglet
`Politique de Stock MRP`, E25. Le nouveau classeur porte 0 en E3. Pour 268967,
l'ancien porte 25 en E26 et le nouveau 60 en E2. L'étiquette du graphe
`industrial_confirmation_2026-04-10` n'est pas une pièce primaire retrouvée.
On conserve l'essai courant, sans transformer cette étiquette en preuve
d'une confirmation datée. Le minimum de lot 268091 passe également de
14 400 à 28 800 entre les deux sources ; le maximum reste 142 485.

### Les cinq règles, avec leurs différences réellement programmées

Notations : `t` est le jour de calcul, `d` une échéance future ; `F` est la
sécurité fixe source, `S` sa sécurité en jours ouvrés lundi–vendredi ; `A`
est le stock libre disponible, `E` les quantités engagées affectables.
Les besoins composants proviennent des fabrications projetées × coefficients
BOM, complétés par les autres usages estimés du scénario. Ils ne sont pas
automatiquement les ventes du seul PF étudié. Un retard déjà inclus dans
ces besoins n'est pas ajouté une seconde fois.

1. **Besoin net : déduire le stock et les engagements une seule fois.**

   ```text
   besoin net(d) = max(0, besoin restant à couvrir(d)
                         − stock libre affectable(d)
                         − engagements affectés(d))
   ```

   Pour les achats datés, les besoins comprennent la protection de la règle 2.
   Le plan affecte successivement les quantités aux échéances. Un engagement
   ferme tardif peut couvrir la quantité tout en signalant un retard : il
   n'est pas racheté automatiquement. Un stock J futur n'est disponible qu'à
   sa date de libération. Le dépôt PF utilise une autre écriture, à la revue :

   ```text
   besoin transfert = max(0, cible dépôt + retard dépôt
                             − disponible dépôt − transit déjà engagé)
   ```

   Ici le mode est `all_future` : tout le transit est déduit, même au-delà
   de la couverture. `bn_qty` du CSV est recalculé après les mouvements du
   jour ; il ne faut pas le confondre avec cette décision avant expédition.
   La formule « prévision + retard + sécurité − stock projeté » ne convient
   que si le stock projeté est calculé **avant** déduction de ces besoins.

2. **Protection : distinguer sécurité datée des achats et cible des stocks.**

   Pour les 22 achats externes du mode `source_safety_additive_v2` :

   ```text
   échéance protégée(besoin u) = max(t, u − S jours ouvrés)
   exigence cumulée(d) = F + somme(besoins restant dus à une échéance protégée ≤ d)
   ```

   `F` est réservé une fois. On ne rajoute pas encore `S × demande` à ces
   besoins déjà anticipés. Pour les transferts internes historiques :

   ```text
   réserve complémentaire = max(0, cible − besoins déjà dans la couverture)
   ```

   C'est précisément la protection qui pouvait s'annuler pour 693055/Avène
   et 773474/Gien. Dans le scénario I, le flag
   `internal_component_safety_policy=source_stock_floor_v1` la remplace par :

   ```text
   plancher interne = max(F, cible quotidienne issue des besoins × S calendaire)
   ```

   Le plancher protège un niveau résiduel, sans créer une consommation.
   La sélection est structurelle : composant BOM approvisionné par une route
   interne, politique source documentée, sécurité positive, mode daté actif.
   Il ne garantit pas que le stock physique atteigne la cible si les besoins,
   les délais ou l'exécution diffèrent du plan.
   Pour les deux dépôts PF dans ce scénario :

   ```text
   q = max(prévision moyenne 7 jours, prévision moyenne sur fenêtre dépôt)
   cible dépôt = S converti en jours calendaires au jour t × q
   ```

   Les planchers fixes des deux PF sont nuls ; coefficient de sécurité = 1.
   Fenêtres dépôt : 31 jours pour 268091, 87 pour 268967. Cette formule
   exécutée n'est pas la somme exacte des besoins futurs durant S jours.

3. **Dates : remonter de la disponibilité nécessaire vers la commande.**

   Pour les achats anticipés :

   ```text
   disponibilité visée = date besoin − S jours ouvrés
   arrivée physique visée = disponibilité visée − traitement à réception
   dernière date de commande = arrivée visée − délai fournisseur
   ```

   Le délai fournisseur est calendaire dans cet essai ; le calendrier de
   réception lundi–vendredi est une convention distincte de la sécurité
   confirmée. Une date déjà dépassée ne fait pas voyager la commande dans
   le passé : le calcul retient la première arrivée possible et le retard.
   Lorsqu'une politique de sourcing admissible le prévoit, le fournisseur
   principal est le moins cher parmi les offres utilisables et le secours
   plus rapide sert selon ses conditions. Ce mécanisme n'est pas appliqué
   automatiquement à toute matière sans politique explicite.

   Pour les transferts internes, le délai de la route s'applique ; le
   traitement à réception des sources n'est pas partout exécuté. Pour la
   fabrication, `tau_process=3` est une estimation de planification, pas
   trois jours supplémentaires de durée physique démontrée.

4. **Quantités : regrouper avant d'arrondir, réutiliser le surplus.**

   ```text
   quantité achetée = standard offre × plafond(besoin net regroupé / standard offre)
   surplus = quantité achetée − besoin net regroupé
   ```

   Le scénario commun groupe sur un jour ; ce regroupement n'est pas une
   période ERP déduite de toutes les sources. Le surplus couvre les besoins
   suivants. Les standards peuvent dépendre du fournisseur retenu.
   Pour la fabrication, la règle vient des paramètres du processus :
   773474 = lot fixe 3 200 kg ; 268967 = 107 800 UN ; 268091 = minimum
   28 800 UN, multiple 14 400, maximum 142 485, donc 129 600 compatibles.
   Une palette n'est pas automatiquement un ordre de fabrication.
   Un transfert ne reprend pas automatiquement le lot de fabrication.

5. **Exécution : le contrôleur de fabrication reste une dynamique des systèmes.**

   ```text
   commande brute = signal prévisionnel + 0,25 × (cible usine − stock usine)
   souhait = max(0, 0,2 × commande précédente + 0,8 × commande brute)
   exécution = min(reste du lot en cours, capacité, quantité permise par les composants)
   stock physique fin = stock physique début + entrées − sorties
   ```

   La lotification et les limites hebdomadaires transforment le souhait en
   campagne. Une campagne engagée peut rester bloquée. Les lots achevés
   deviennent disponibles ; le travail en cours peut être fractionnaire,
   mais les quantités physiques libérées en UN sont entières.
   Le flag testé `--production-mrp-safety-targets` remplace, pour les sorties
   éligibles, la cible historique par le maximum entre cette cible, `F` et
   `signal × S calendaire`. Il rétablit la protection de 773474/Gaillac,
   sans copier une politique dépôt dans les usines PF inéligibles.

Ces cinq règles décrivent donc **plusieurs branches encore différentes**.
Les achats datés n'ont pas encore remplacé le pilotage SD des fabrications
et des dépôts. Les plans datés PF/DC sont informatifs ; leur présence ne
prouve pas que leurs propositions deviennent des fabrications exécutées.

### Lecture des nouvelles comparaisons de production

`production_campaigns.started_qty` est compté une fois par `campaign_id`,
à `campaign_started_day`. Le premier événement peut être un blocage, donc
filtrer seulement `start_campaign` perdrait des lancements. `executed_qty`
mesure le travail quotidien ; les libérations du registre distinguent
`production_output` des `opening_production_order` déjà engagés à J0.

| Produit, scénario achats communs avant correction fabrication | Nouvelles campagnes | Quantité nouvellement disponible | Carnet initial devenu disponible |
|---|---:|---:|---:|
| 268091 | 49 | 1 411 200 UN | 1 945 715 UN |
| 268967 | 16 | 1 724 800 UN | 0 UN |
| 773474 | 15 | 48 000 kg | 3 200 kg |

693055 n'a pas de fabrication modélisée : 13 200 kg d'apports simplifiés et
600 kg du carnet initial. Les qualifier de nouveaux OF serait incorrect.
Les flux sources H sont affichés à leur site, avec une seule version du plan
à la fois : pour les PF au dépôt, on compare des réceptions depuis l'usine,
pas des lancements. La différence entre deux photos est un **bilan net**
entrées moins sorties, pas une livraison ou une fabrication brute observée.
Oracle indépendant :
`artifacts/testing/mrp_finished_goods_20261002/map/oracle_v2.json`.

## Audit de la chaîne interne et des produits finis — 2 octobre 2026

**Le contrôle des 22 achats externes ne couvrait pas toute la chaîne.**
Les stocks des intermédiaires, les transferts et les produits finis doivent
être vérifiés ensemble, sans attendre qu'un utilisateur cite les références.
Cette passe examine les 29 couples comparables, avec un diagnostic détaillé
de 773474, 693055 et des deux produits finis. Elle ne remplace pas le nominal.

### Écarts de la carte livrée, avant le test isolé

Moyennes de stock physique sur les 52 photos de 2025, comparées aux clôtures
simulées précédentes :

| Référence / site | Sources | Simulation livrée |
|---|---:|---:|
| 773474 / Gaillac | 25 169 kg | 5 046 kg |
| 773474 / Gien | 17 251 kg | 4 948 kg |
| 693055 / Gaillac | 1 106 kg | 499 kg |
| 693055 / Avène | 1 143 kg | 104 kg |
| 268091 / dépôt | 806 091 UN | 316 921 UN |
| 268967 / dépôt | 670 475 UN | 737 507 UN |

693055 à Avène reste à stock physique nul pendant **247 jours**. La photo
du 29 décembre contient 2 140 kg, contre zéro dans le modèle. Ce n'est pas
seulement un écart de moyenne. Pour 268091 au dépôt, la photo du 29 décembre
contient **1 010 323 UN**, contre **37 383 UN** à la clôture simulée comparée
(31 670 UN à la fin du 31 décembre). Le produit fini 268967 présente au
contraire un stock moyen simulé supérieur aux sources : une augmentation
générale de toutes les sécurités ne constitue donc pas une correction.

### Mécanismes identifiés dans le code exécuté

1. **Fabrication de 773474 : sécurité chargée mais désactivée.** La commande
   n'active pas `--production-mrp-safety-targets`. Avec `fg_target_days=0`
   et une cible de base nulle pour le snapshot, la cible de production
   reste zéro malgré les 20 jours ouvrés sources. Le signal de demande
   propagé n'est pourtant pas nul. La nouvelle projection ne pouvait
   protéger qu'une cible elle-même nulle.
2. **Transferts internes : ancienne protection encore utilisée.** Gien/773474
   et Avène/693055 déduisent les besoins de couverture de leur cible pour
   obtenir un complément consommable. Ils ne suivent pas la nouvelle
   anticipation des achats externes. À J361, 693055 affiche une cible de
   811,411 kg et une sécurité de 213,098 kg, mais une réserve datée nulle
   et un ordre de transfert de 120,452 kg. Une cible affichée positive
   ne prouve donc pas la protection réellement appliquée.
3. **Politique interne encore spécifique à un article.** Le validateur
   `resolve_internal_component_policies` n'admet actuellement que
   693055/Avène depuis Gaillac, avec 600 kg et sept jours de réception.
   Sa généralisation doit contrôler route, unité, paramètres et calendrier,
   sans conserver une condition sur l'identité de l'article.
4. **693055 à Gaillac : fabrication non représentée par une BOM.** Le
   scénario utilise une frontière d'approvisionnement simplifiée : lots
   de 600 kg, délai supposé de 28 jours, puis transfert de 70 jours vers
   Avène. Activer une cible de fabrication ne modifie pas cette frontière.
   Il ne faut ni inventer sa nomenclature, ni présenter ce mécanisme comme
   un ordre de fabrication industriel intégralement reconstitué.
5. **Produits finis aux usines : pas de politique source affectée à ces
   stocks de sortie.** M-1430/268967 et M-1810/268091 ne sont pas dans les
   snapshots MRP éligibles à cette option ; leurs cibles restent nulles
   même avec le flag. Cela ne justifie pas de recopier arbitrairement les
   jours de sécurité des dépôts aux usines. Le pilotage du stock du dépôt
   et sa propagation vers la production doivent être examinés ensemble.

### Physique et disponible ne sont pas interchangeables

Les six couples ci-dessus n'ont aucun stock simulé indisponible sur 2025.
À Gaillac/773474, le plan du 29 juin documente pourtant **6,4 tonnes
courantes + 25,6 tonnes disponibles ultérieurement = 32 tonnes physiques**,
retrouvées dans la photo du 30 juin. Le modèle possède alors 3,2 tonnes,
toutes disponibles. Sur l'année, J courant et J futur valent chacun
12,6 tonnes en moyenne. Leur somme retrouve la photo dans 51 cas sur 52.
À Avène/693055, J est presque entièrement courant : son sous-stock ne
s'explique donc pas principalement par une disponibilité différée.

Les sources ne donnent pas un paramètre unique à convertir sans examen :
`Extract_En_cours` donne 21 jours ouvrés de réception pour l'O.Proc de
693055 (ligne 103) et 26 pour celui de 773474 (ligne 105), avec des dates
qui correspondent exactement à ces durées. Flow MRP indique respectivement
28 et 33 jours. Les valeurs ne doivent pas être fusionnées ni transformées
automatiquement en quarantaine physique. `tau_process` reste inchangé.

Un conflit de références subsiste aussi pour 268091 au dépôt : la politique
hebdomadaire porte `00` jour, tandis que le graphe et l'exécution retiennent
20 jours, avec une provenance d'ancienne confirmation industrielle. La
valeur n'a pas été arbitrairement remplacée par zéro pendant cet audit.

### Test isolé de la sécurité de fabrication

Un nouveau calcul de **365 jours** change uniquement l'activation de
`--production-mrp-safety-targets`, avec le même graphe, les mêmes capacités,
stocks initiaux et sources. Il termine sans erreur en **335,6 s**, code et
entrées inchangés. Les deux tests mémoire ciblés et la qualification CSV
réussissent. Ce test ne constitue pas une qualification de cinq ans ni une
nouvelle carte nominale.

Pour **773474 à Gaillac**, le stock moyen passe de 5 046 à **28 554 kg**,
contre 25 169 kg dans les sources. L'écart absolu moyen baisse de 20 246
à **4 738 kg**, et les jours à stock physique nul passent de 15 à zéro.
021081 à Gaillac s'améliore aussi. Les **27 autres comparaisons restent
identiques**, notamment Gien/773474, 693055 et les deux produits finis.
Cela isole le défaut de cible amont sans prétendre résoudre les autres
branches. Le stock indisponible n'est pas pour autant reconstitué.

Les quatre couples sources sans stock modélisé comparable sont également
signalés : 001893/Gaillac, 002612/Gaillac, 007923/Gien et 029313/Gien. Ils
ne doivent pas être remplacés par des stocks simulés nuls ou comptés comme
des comparaisons réussies.

Le [contrôle exhaustif des 29 couples](../../artifacts/testing/mrp_internal_chain_20261002/stock_coverage_29.json)
classe chaque flux, vérifie la règle réellement tracée et les paramètres
sources, puis relève les épisodes de stock nul. Dans la référence livrée,
10 couples ont au moins un jour à stock physique nul et 12 à stock
disponible nul. Ces nombres ne sont pas des nombres de ruptures clients :
une vidange après transfert ou entre deux lots doit être distinguée d'un
besoin effectivement non servi. La même vérification doit accompagner les
comparaisons de moyenne, plutôt que de limiter l'examen aux références
signalées par l'utilisateur.

La correction à généraliser doit couvrir le **calcul daté des achats et
des transferts**, la **disponibilité physique**, le **pilotage de fabrication**
et la **reconstitution des stocks de produits finis**, avec des conditions
par type de flux et des paramètres sourcés. L'objectif d'environ un an de
stock pour la chaîne du médicament reste collectif ; il ne devient pas
un an de sécurité ajouté à chaque étage.

Preuves : [sources, états de stock et en-cours](../../artifacts/testing/mrp_internal_chain_20261002/source_review.json),
[comparaison du test sur les 29 couples](../../artifacts/testing/mrp_internal_chain_20261002/comparison.json),
[commande et exécution](../../artifacts/testing/mrp_internal_chain_20261002/experiment/report.json),
[qualification CSV](../../artifacts/testing/mrp_internal_chain_20261002/native/qualify-fcb46b427e6341a7bd805172ac03f477/manifest.json).

## Correction commune à tous les achats externes — 2 octobre 2026

**État : correction implémentée ; calibration industrielle non validée globalement.**
Le scénario `source_safety_additive_v2` remplace, pour les achats externes,
la sélection de protections par article par un calcul commun. Les paramètres
restent ceux de chaque matière et de son site : partager une règle ne signifie
pas partager les mêmes délais, fournisseurs ou quantités standards.
Le scénario antérieur est conservé pour comparaison, sans écrasement.

### Règles et conditions effectivement implémentées

| Règle | Condition et calcul | Statut |
|---|---|---|
| Périmètre | Tous les couples d'achat externe agrégé déterminés par le graphe : 22 couples matière–site dans ce cas. Aucune liste d'articles autorisés dans cette nouvelle règle. | Vérifié dans les décisions exécutées des pilotes ; ne désigne pas les fabrications et transferts internes. |
| Besoin à couvrir | Besoins datés restants issus des fabrications projetées et rapprochement avec les besoins I du dernier plan industriel connu. Les besoins I sont des prévisions ; ils ne sont pas des sorties physiques déjà réalisées. | Mécanisme commun ; périmètre et calendrier de consommation encore imparfaits. |
| Sécurité | Réserver une fois le stock fixe F, puis avancer les besoins restants du nombre S de jours de sécurité sources, du lundi au vendredi. Cela conserve F en plus de la protection temporelle. | Formule additive candidate, maintenant réellement exécutée ; elle n'est pas une règle ERP confirmée pour chaque article. |
| Dates d'achat | Disponibilité protégée = besoin − S ouvrés ; arrivée physique visée = disponibilité protégée − traitement à réception ; dernière commande = arrivée physique visée − délai fournisseur. Le moteur conserve le calendrier de réception existant et le délai fournisseur fixe source. | Les trois délais sont distincts, sans ajouter deux fois S. Une date déjà passée reste un retard explicite. |
| Besoin net | Déduire le stock utilisable et les quantités fermes une seule fois ; distinguer stock encore indisponible, arrivée physique et disponibilité. | Une quantité ferme tardive n'est pas rachetée automatiquement. Le retard peut donc subsister. |
| Principal et secours | Dans une politique principal/secours documentée, réserver F avant de calculer le manque à la date protégée ; le secours couvre le manque que le principal ne peut satisfaire à temps. F seul ne justifie pas un achat de secours. | Le même calcul de sécurité fonctionne avec ou sans sourcing. Les rôles industriels non établis ne sont pas inventés. |
| Regroupement et arrondi | Regrouper les besoins nets à la même échéance avant d'arrondir à la quantité admissible de l'offre retenue ; réutiliser le surplus pour les besoins suivants. | Fenêtre retenue de 1 jour. L'essai à 7 jours ne fournit pas de gain général. Les règles d'admissibilité des offres préexistantes sont conservées. |
| Fabrication projetée | Maintenir la cible courante du contrôleur de production SD comme plancher dans sa projection, afin de prévoir les consommations BOM avant épuisement du stock de PF. | Correction de projection uniquement ; ni réservation matière ni fabrication exécutée. La cible future constante est une approximation révisable, pas un ordonnancement industriel confirmé. |

Les quantités physiques UN restent entières. Les stocks de sécurité sources,
stocks initiaux, engagements d'ouverture et délais fixes restent identiques
à la référence. Le standard utilisateur de 730384 reste **92 500 m** ; le
fichier FIA original n'est pas modifié. Les 33 capacités fournisseurs
effectives de la référence sont conservées, pour ne pas confondre changement
de règle MRP et changement de capacité. Les consommations attribuées aux
autres produits restent les hypothèses précédentes : cette passe ne les
transforme pas en données industrielles confirmées.

Les fabrications et transferts internes restent des flux différents d'un
achat fournisseur. Ils figurent dans les **29 comparaisons** de stock, mais
ne sont pas comptés comme 29 applications de la règle d'achat. Les cinq
nouveaux champs de décision permettent de vérifier la version de règle,
le mode de sécurité, la fenêtre de regroupement, la base des besoins et le
plancher de fabrication projeté. Une option de configuration seule ne tient
plus lieu de preuve d'application.

### Comparaison des deux pilotes sur 2025

Les deux simulations de 365 jours sont terminées sans modification du code
ou des entrées pendant leur exécution. Le recalcul indépendant de 66 plans
(22 couples, trois dates de décision) retrouve F réservé une fois, les
besoins avancés suivant S, les quantités fermes uniques et le besoin net
avant arrondi. Les contrôles de délais, lots, UN, capacités et bilans n'ont
pas trouvé d'écart technique.

L'écart absolu moyen est calculé sur les photos datées, avec le stock
physique total à la clôture précédente, sans interpolation ni mélange des
unités. La nouvelle règle améliore **9 des 22** achats externes et en
dégrade **13** ; sur les 29 comparaisons, 12 s'améliorent, 15 se dégradent et
2 restent identiques. Ce bilan ne permet pas de promouvoir ce scénario
comme une calibration globalement meilleure.

| Couple | Écart moyen avant → après | Lecture nécessaire |
|---|---:|---|
| 730384 / 1430 | 47 409,6 → 39 375,4 m | Minimum physique 911,8 → 45 533,4 m ; aucun jour sous les 23 500 m fixes en 2025. L'écart du quatrième trimestre augmente toutefois de 42 948,6 à 51 910,3 m. |
| 708073 / 1430 | 4 470,2 → 3 751,0 kg | La première réception est encore trop tardive : 2 juin, contre une première hausse source entre le 10 et le 17 mars. L'amélioration moyenne ne valide pas le calendrier. |
| 001848 / 1810 | 2 337,8 → 1 996,6 kg | Amélioration surtout en fin d'année ; le secours du printemps n'est toujours pas reproduit. |
| 042342 / 1430 | 24 320 219,1 → 31 958 491,8 UN | Dégradation importante ; le périmètre des usages partagés reste à traiter. |
| 338928 / 1810 | 661 302,2 → 906 252,3 UN | Dégradation importante du niveau de stock. |
| 338929 / 1810 | 420 392,7 → 583 503,2 UN | Dégradation importante du niveau de stock. |

Avec le regroupement de 7 jours, 17 des 22 comparaisons restent identiques
au regroupement de 1 jour, quatre se dégradent et une s'améliore (344135,
avec seulement trois photos). 708073, 730384 et 001848 ne changent pas.
La cadence hebdomadaire des exports MRP ne prouve pas une règle industrielle
de regroupement hebdomadaire. Le candidat retenu pour la qualification
longue utilise donc 1 jour. Les quantités servies de PF sur 2025 sont
identiques dans les deux pilotes et dans la référence.

Le [rapprochement des entrées H](../../artifacts/testing/mrp_unified_20261002/validation/receipt_plans_22_v2.json)
contrôle aussi 22 couples à trois dates de plan (J4, J123 et J361), en
confrontant les arrivées physiques projetées aux semaines explicitement
renseignées de la dernière version industrielle connue. Sur 60 comparaisons
avant/après exploitables avec H positif, la part de volume H retrouvée à
plus ou moins sept jours, moyennée par comparaison, passe de **61,48 % à
59,97 %** : 18 s'améliorent, 25 se dégradent et 17 restent identiques.
Ce n'est ni un nombre de commandes réelles, ni un score exhaustif sur les
52 versions. Les dates physiques futures ambiguës de 001893 ne sont pas
notées ; les semaines sources absentes ne deviennent pas des zéros.
Cette vérification supplémentaire confirme l'absence de gain global
démontré sur le MRP industriel : le scénario reste une comparaison séparée,
et ne remplace pas automatiquement la référence précédente.

### Écart restant sur 708073 : besoin prévu et consommation physique

Le 2 mars, le stock du simulateur vaut 8 361,871 kg contre 5 841,138 kg
dans le plan industriel, soit 2 520,733 kg de plus. Autour de cette date,
212,867 kg par jour sortent des besoins prévisionnels restants, alors que
le registre n'en consomme que 82,224 kg par jour au titre des autres usages
estimés ; aucune consommation BOM propre n'intervient du 2 au 8 mars.
Une proposition peut donc reculer quand les besoins expirent, même si la
règle de sécurité est active. Ce constat local ne prouve pas que toutes
les sorties I doivent devenir des consommations physiques : elles couvrent
un périmètre et des fabrications qu'il reste à rapprocher.

Il faut distinguer la correction de la règle commune, maintenant vérifiable,
de la reconstruction du calendrier des consommations. Réinjecter les entrées
H futures ou remettre artificiellement les stocks aux photos améliorerait
les courbes sans expliquer le MRP ; ce n'est pas ce que fait ce scénario.

Le [rapprochement des consommations pour les 22 couples](../../artifacts/testing/mrp_unified_20261002/validation/demand_scope_22.json)
étend ce contrôle. Pour chaque semaine cible, il retient uniquement le dernier
plan connu avant cette semaine, puis compare I une seule fois à la
consommation physique BOM + autres usages sur les mêmes jours couverts.
Le rapport consommation simulée / besoin prévu vaut notamment 14,5 % pour
338928, 22,9 % pour 338929, 51,0 % pour 730384, 59,2 % pour 042342,
72,9 % pour 708073 et 72,1 % pour 001848 à Avène. Il est de 97,0 % pour
002612 et 91,3 % pour 007923. Les semaines absentes restent inconnues ;
344135 ne permet pas de ratio exploitable. Ces écarts peuvent expliquer une
partie des surstocks, mais ne départagent pas seuls sur-prévision, décalage
de fabrication, stocks initiaux de PF et usages non représentés. I n'est
pas une mesure de consommation réellement exécutée.

Preuves : [pilote commun](../../artifacts/testing/mrp_unified_20261002/validation/common_365_review.json),
[pilote à 7 jours](../../artifacts/testing/mrp_unified_20261002/validation/weekly_365_review.json),
[oracle des 66 plans](../../artifacts/testing/mrp_unified_20261002/validation/common_365_snapshot_oracle.json),
[diagnostic de 708073](../../artifacts/testing/mrp_unified_20261002/validation/708073_drift.json).
La recette du calcul de cinq ans est conservée dans
`config/mrp_unified_20261002/checkpoint.zip` ; ses résultats et contrôles finaux
sont référencés dans le bilan de qualification ci-dessous après exécution.

### Qualification finale sur cinq ans et livraison

Le calcul de **1 825 jours est terminé**, code retour nul, sans modification
des 20 fichiers de calcul/affichage suivis ni des entrées gelées pendant
l'exécution. Durée observée : **1 197,8 s**, contre 675,2 s pour la référence
antérieure ; ce ne sont pas des mesures de performance contrôlées. Le coût
supplémentaire du calcul constitue aussi une limite de ce candidat.
Les 42 335 lignes comparées sur cinq exports confirment que sa première
année reproduit exactement le pilote, pour les stocks, consommations,
service et champs stables des achats.

| Contrôle sur les cinq années | Référence → règle commune | Limite |
|---|---:|---|
| 730384 : jours à stock disponible nul | 4 → 0 | Le disponible reste sous F pendant 19 jours, contre 71 auparavant. |
| 730384 : jours de production limitée par cette matière | 4 → 0 | Minimum disponible de 10 682,2 m ; une règle de planification ne garantit pas F chaque jour d'exécution. |
| 708073 : jours à stock disponible nul | 31 → 0 | Le disponible reste sous F pendant 77 jours, contre 83 auparavant. |
| 708073 : jours de production limitée par cette matière | 31 → 0 | Minimum disponible de 339,325 kg ; le calendrier industriel de 2025 reste mal reproduit. |
| Service aux deux produits finis | Inchangé chaque année | La conservation du service ne valide pas les niveaux de stock. |

L'audit vérifie **40 150 décisions**, soit 22 couples sur 1 825 jours, et
retrouve les 33 capacités de référence. Les quantités exécutées, délais,
arrondis et bilans contrôlés ne présentent pas d'anomalie. Le recalcul
indépendant détaillé de la formule porte sur **66 plans de 2025** : les
exports de plans hebdomadaires ne couvrent que les 52 dates de cette année.
Il ne faut pas transformer cette preuve en 66 plans sur chacune des cinq
années. Les **28 tests ciblés**, le doctor, la qualification CSV et leur
agrégation sur l'état final passent.

**Métadonnée héritée à ne pas prendre pour un ordre réel :** dans le graphe
figé, l'arête fournisseur de 708073 conserve `standard_order_qty=5000000`
avec `standard_order_uom=KG`. C'est incohérent avec FIA `268967.xlsx!G6:H6`
(5 000 KG). Le registre canonique des lots remplace déjà cette valeur lors
du chargement des voies : les **17 achats exécutés valent chacun 5 000 kg**.
L'audit conserve l'anomalie de métadonnée séparément ; elle ne constitue pas
un achat de cinq millions de kilogrammes. Le graphe historique n'a pas été
retouché après calcul pour masquer cette incohérence.

La [carte comparative](../../resultats/mrp_unified_20261002/comparaison.html)
ouvre 708073 par défaut et donne accès aux 29 couples. La vérification dans
un navigateur hors ligne compare 21 170 valeurs quotidiennes au CSV,
40 150 traces de règle, 51 100 nouveaux champs de décision et 2 918 points
affichés ; les six onglets, changements de matière, périodes et interactions
ciblées passent. Les deux suivis de lots et la carte antérieure sont conservés.

Preuves finales : [audit de cinq ans v3](../../artifacts/testing/mrp_unified_20261002/validation/common_1825_review_v3.json),
[ruptures et sécurité](../../artifacts/testing/mrp_unified_20261002/validation/five_year_focus.json),
[identité de la première année](../../artifacts/testing/mrp_unified_20261002/validation/prefix_2025.json),
[agrégation des contrôles](../../artifacts/testing/mrp_unified_20261002/native_final/gate-1a4a6799499d4ea1af5703d2ff62860a/manifest.json),
[navigateur](../../artifacts/testing/mrp_unified_20261002/view/browser_105a4321d5/report.json).
La petite archive `config/mrp_unified_20261002/map_recipe.zip` conserve le
générateur et ses dépendances propres, en complément des archives de sources
du calcul et de la référence. Les archives ont été vérifiées en lecture ;
une extraction suivie d'une nouvelle reproduction complète n'a pas été
exécutée ici. **Cette livraison est un scénario comparatif qualifié
techniquement, pas une nouvelle calibration nominale validée.**

## 708073 et 001848 : distinguer règle trouvée, exécutée et évaluée — 2 octobre 2026

**Rectification de la conclusion sur les essais globaux.** L'essai E a bien
activé une anticipation sur 22 couples : les traces d'exécution le confirment.
Face à D, il améliore sept écarts de stock et en dégrade quinze. Mais il
applique l'enveloppe MAX des protections et remplace les protections
préexistantes. Ce résultat ne démontre pas l'échec de la combinaison additive
observée dans le diagnostic source de 708073, ni celui de toutes les règles
communes correctement intégrées. L'argument « cela dégrade d'autres matières »
doit toujours nommer la formule exécutée, les mécanismes remplacés et le
périmètre réel. Voir la [vérification des essais historiques](../../artifacts/testing/mrp_708073_application_20261002/historical_application.json).

| Point | Constat source / diagnostic | Dernière simulation |
|---|---|---|
| 708073 : sécurité fixe et en jours | 2 000 kg et 10 jours ouvrés ; le diagnostic additif expliquait mieux les dates que MAX | Protection datée avec couverture ; la formule additive du diagnostic n'est pas celle testée par C/E |
| 001848 : sécurité | 20 jours ouvrés, stock fixe nul | Branche principal/secours distincte ; l'anticipation explicite par les jours de sécurité est désactivée dans le dernier scénario |
| 708073 : tailles d'entrées | Standard FIA 5 000 kg ; les plans H contiennent surtout 10 000 kg | Cinq achats de 5 000 kg lancés en 2025, dont quatre reçus en 2025 |
| Regroupement avant arrondi | Deux standards peuvent former une entrée de 10 000 kg ; cause exacte à établir | Aucun `procurement_batching` actif dans la configuration livrée |

Avec un stock fixe nul comme pour 001848, la distinction entre ajouter ce
stock fixe à la protection temporelle et prendre l'enveloppe MAX disparaît.
708073, avec 2 000 kg fixes, permet de tester cette différence. Les paramètres
propres aux articles sont normaux ; une sélection manuelle de formules par
article ne constitue pas une règle métier commune.

Les traces le confirment : à J109, 708073 utilise une protection de 2 000 kg,
sans anticipation explicite, et achète 5 000 kg ; à J104, 001848 utilise le
sourcing principal/secours et achète 6 000 kg sans protection datée. Le
moteur interdit actuellement de combiner directement cette protection datée
avec le sourcing. Une diffusion fiable demande donc de réunir ces mécanismes,
pas seulement d'ajouter une option dans chaque ligne de configuration.

Le [rapprochement numérique indépendant](../../artifacts/testing/mrp_708073_application_20261002/numeric/review.json)
confirme pour 708073 : moyenne simulée aux photos de 6 471,55 kg contre
10 173,39 kg dans les sources ; écart absolu moyen de 4 470,18 kg, contre
4 292,81 kg dans G. Le stock physique reste supérieur aux 2 000 kg fixes,
mais les réceptions et les niveaux de stock sont mal reproduits. Les trois
hausses nettes industrielles valent 9 142,674 kg, 10 697,822 kg et 10 146,487 kg.
Ce sont des variations nettes, pas des quantités brutes de commandes identifiées.
La première réception simulée arrive le 18 mai, alors que la première hausse
source est déjà visible entre le 10 et le 17 mars. Cet écart de calendrier
dépasse largement la tolérance d'une semaine recherchée.

Les 24 721,794 kg consommés par le modèle incluent 13 677,664 kg de BOM et
11 044,130 kg de consommation d'autres produits estimée. Cette dernière
reste une hypothèse, comme celle conservée pour 001848 ; elle n'est pas une
confirmation industrielle de partage. Une comparaison de règles doit tenir
ces consommations constantes et les distinguer des besoins I de planification.

Cette passe audite les exécutions terminées et leurs sources, sans nouvelle
simulation ni changement de moteur. Elle établit que la diffusion des
trouvailles est incomplète et que les essais historiques ne permettent pas
de rejeter la règle additive ou un regroupement commun non exécuté. Elle ne
prouve pas encore la réussite d'une correction globale de ces deux mécanismes.

## Diagnostic des creux de 730384 : règles communes incomplètes — 2 octobre 2026

La baisse de l'écart moyen annoncée ci-dessous **ne valide pas le respect
quotidien de la sécurité ni une règle MRP commune à toutes les matières**.
Le dernier scénario reste une configuration hybride, avec des protections
datées activées pour certains couples seulement. Cet audit ne modifie pas
le moteur, les sources ou la carte et ne lance aucune nouvelle simulation.

Pour 730384 / Gien, le stock physique de 2025 ne tombe pas exactement à zéro :
il reste **911,8 M du 21 juin au 1er juillet**. Le stock disponible reste à
ce niveau jusqu'au 8 juillet. Le plancher source de **23 500 M** est franchi
le 17 juin ; le physique reste inférieur pendant 15 jours, le disponible
pendant 22 jours. Sur cinq ans, le stock disponible atteint réellement zéro
pendant quatre jours (J958, J992, J993 et J1728), avec une fabrication limitée
par cette matière. Un volume annuel de produits finis livré satisfaisant
ne suffit donc pas à exclure les ruptures de composants.

Trois lots de fabrication de 107 800 UN consomment au total
`3 × 22 853,6 = 68 560,8 M` entre le 14 et le 21 juin. Le stock passe de
69 472,6 à 911,8 M. L'achat de 92 500 M lancé le 7 mai arrive le 2 juillet,
puis devient disponible le 9 juillet après cinq jours ouvrés de réception.
Le délai fournisseur fixe de 56 jours est respecté ; c'est l'anticipation
du besoin et de sa protection qui doit être examinée.

Deux défauts distincts apparaissent :

- **Protection du stock fixe perdue dans le calcul de couverture.** Pour
  730384 au plan du 4 mai, les besoins cumulés sur 71 jours valent
  86 083,4 M. La cible vaut `max(23 500, 86 083,4)`, puis le complément de
  réserve est calculé par `max(0, cible − besoins sur 71 jours)` : il est nul.
  Les 23 500 M restent un paramètre du modèle, mais ne constituent pas un
  plancher à chaque date. Le plan prévoyait déjà un passage sous ce seuil
  à J178 ; son achat proposé couvrait seulement le manque à J189.
- **Écart entre fabrication prévue et exécutée.** Le même plan ne contenait
  pas de besoin BOM propre de 730384 avant J266, alors que la production
  effective consomme trois lots en juin. Les besoins industriels ajoutés
  au plan n'assurent pas à eux seuls la cohérence avec cette exécution.

La protection `dated_stock_floor_with_coverage` concerne seulement 055703,
039668, 708073, 001757, 002612 et 007923 ; 730384 ne l'utilise pas. Une partie
des règles est commune (délais, arrondis admissibles, netting des engagements),
mais la politique de sécurité et le signal de besoin ne sont pas encore
unifiés. Les anciens essais C/E de sécurité datée ont bien été comparés
entre références ; leur résultat défavorable ne justifiait pas une adoption
globale. La configuration finale n'est donc pas une règle universelle validée.

Les sources confirment le décalage : dès les plans du 20 avril et du 4 mai,
une entrée de 92 500 M figure dans la semaine repérée au 25 mai. Les photos
passent de 78 300 M le 26 mai à 167 414 M le 2 juin, soit une hausse nette
de 89 114 M. Cette hausse ne permet pas d'identifier une quantité brute ou
une date exacte de livraison. Voir le [rapprochement source](../../artifacts/testing/mrp_730384_zero_20261002/source_context.json).
Les [contrôles numériques indépendants](../../artifacts/testing/mrp_730384_zero_20261002/numeric/trough_review.json)
reconstruisent les bilans quotidiens et les franchissements du plan du 4 mai ;
les [points de code et conditions actives](../../artifacts/testing/mrp_730384_zero_20261002/policy/findings.json)
localisent les deux mécanismes en cause.

La prochaine correction doit d'abord réconcilier les besoins datés utilisés
par les achats avec les fabrications effectivement décidées, puis appliquer
la protection suivant des conditions métier et les paramètres sources,
sans liste arbitraire d'articles. La validation devra publier pour chaque
couple les jours sous sécurité, les ruptures, les blocages, les quantités
et dates d'achat, en plus de l'écart aux photos. Elle doit distinguer un
manque déjà prévisible à la décision d'un besoin révisé après lancement.

## Application demandée : délais fixes et standard 730384 à 92 500 M — 2 octobre 2026

### Résultat retenu : capacités constantes

Le second calcul termine les **1 825 jours en 675,235 secondes**, avec code
et entrées inchangés. L'oracle indépendant confirme les 33 capacités de
référence, les stocks physiques UN entiers et les achats de 730384 par
multiples de 92 500 M. Pour 268091, 3 576 442 UN sont livrées pendant
chacune des cinq années : le blocage du premier essai est levé. Le volume
total livré sur cinq ans est identique à G, soit 17 882 210 UN ; le service
annuel de 268967 est également identique à la référence.

Pour 730384 en 2025, les cinq achats de 92 500 M remplacent les deux achats
de 370 000 M. L'écart absolu moyen aux stocks sources passe de 146 684,03
à **47 409,57 M (−67,68 %)**. Le stock final atteint 165 229,4 M, contre
442 729,4 M auparavant et 125 931 M dans la dernière photo industrielle.
Les dates de réception restent imparfaitement reproduites.

Sur les 29 couples article-site, **11 écarts de stock diminuent, 17 augmentent
et un reste identique**. La suppression globale de l'aléa n'est donc pas une
amélioration générale de calibration : l'écart moyen de 001848 / Avène
atteint 2 337,80 kg et celui de 001757 atteint 1 743,39 kg. Les consommations
complémentaires hypothétiques sont conservées et ne sont pas validées ici.

Livrable : [comparaison à capacités constantes](../../resultats/mrp_730384_fixed_20261002/comparaison_capacites_constantes.html).
Preuves : [contrôle indépendant final](../../artifacts/testing/mrp_730384_fixed_20261002/validation_v2/postrun.json)
et [manifeste de livraison](../../artifacts/testing/mrp_730384_fixed_20261002/manifest.json).
Le standard source FIA reste à 370 000 M ; 92 500 M est le choix utilisateur
appliqué dans la configuration reproductible, sans modification des Excel.

### Diagnostic conservé du premier essai et justification des capacités

**Premier essai rejeté après contrôle du service sur cinq ans.** La suppression
de l'aléa recalculait également les capacités fournisseur estimées. Pour
338928, la capacité passait de 62 500 à 20 779,2208 UN/j, sous le lot obligatoire
de 25 000 UN : aucun achat neuf n'était possible. La production de 268091
restait bloquée sur une campagne inachevée à partir de J302. Le volume servi
sur cinq ans était ainsi limité aux 3 125 053 UN de 2025. Les résultats
2025 ci-dessous restent un diagnostic du premier essai, pas une nouvelle
référence validée. La qualification arithmétique n'avait pas détecté cette
impasse opérationnelle ; le contrôle indépendant du service annuel l'a révélée.

Une seconde version conserve les **33 capacités effectives du précédent G**
comme valeurs fixes avec `--supplier-neutral-floors-csv`, sans colonne de
stock initial et donc sans modification de ces stocks. Cette option existante
remplace directement les capacités ; aucune échelle ×320 supplémentaire
n'est appliquée. Les capacités héritées sont des hypothèses calibrées du
modèle, pas des capacités industrielles confirmées. Le standard de 92 500 M
et `--no-stochastic-lead-times` restent actifs. La capacité de 338928 redevient
62 500 UN/j sans réintroduire un tirage de délai ni la marge de couverture.

La version à capacités constantes est définie par
[settings_final.json](../../config/mrp_730384_fixed_20261002/settings_final.json)
et [capacity_reference.csv](../../config/mrp_730384_fixed_20261002/capacity_reference.csv).
Son [calcul distinct](../../artifacts/testing/mrp_730384_fixed_20261002/capacity_fixed/report.json)
est contrôlé sur les cinq années ci-dessus ; l'archive
`checkpoint_final.zip` conserve cette recette. Aucun code moteur n'est modifié.

L'utilisateur demande de supprimer le côté aléatoire des délais et de retenir
**92 500 M comme quantité standard de 730384 / Gien**. Le scénario préparé
reprend G et ne change que le standard de son unique offre fournisseur,
370 000 → 92 500 M, ainsi que l'option `--no-stochastic-lead-times`.
Le mode de livraison fournisseur `source` est conservé. Le moteur existant
permet ces deux réglages ; aucun changement de code moteur n'est nécessaire.

L'option désactive l'échantillonnage des délais sur toutes les liaisons de
ce scénario et la majoration aléatoire utilisée pour la couverture.
Pour 730384, la livraison conserve ses 56 jours sources et le traitement
à réception ses cinq jours ouvrés. À J0, la couverture générique doit passer
de 118 à **71 jours** (56 + 14 de sécurité convertie + 1 de revue), sans
modifier les 10 jours ouvrés ni les 23 500 M de sécurité source. Les dates
de disponibilité conservent leur traitement séparé de la réception.

Le standard de 92 500 M s'applique à la proposition et à l'achat exécuté ;
un besoin supérieur peut encore donner un multiple de 92 500 M. Ce réglage
est une **décision de scénario explicitement demandée**, appliquée dès le
début du calcul. Le classeur FIA reste intact à 370 000 M. Les premiers
plans sources annonçaient 87 000 M : nous n'affirmons donc pas que 92 500 M
était un standard industriel prouvé sur toute l'année 2025.

Les hypothèses de consommation complémentaire sont conservées à l'identique
pour cette comparaison ; cette exécution ne les valide pas. Les anciennes
simulations et cartes sont conservées. Le calcul terminé dure 1 825 jours ;
seule 2025 est rapprochée des données industrielles disponibles.

Réglages persistants : [settings.json](../../config/mrp_730384_fixed_20261002/settings.json).
L'[archive unique](../../config/mrp_730384_fixed_20261002/checkpoint.zip)
conserve le code, les sources, le graphe corrigé et la commande exacte ;
son [contrôle d'intégrité](../../artifacts/testing/mrp_730384_fixed_20261002/archive_verification.json)
ne vaut pas rejeu depuis extraction. Le [rapport d'exécution](../../artifacts/testing/mrp_730384_fixed_20261002/report.json)
atteste un code retour nul et des empreintes stables, après 596,641 secondes
(9 min 57 s). La qualification technique sur cinq ans réussit ; elle ne
prouve pas la calibration industrielle.

| 730384 / Gien, année 2025 | Avant (G) | Délais fixes et standard 92 500 M |
|---|---:|---:|
| Achats nouveaux | 2 × 370 000 M | 5 × 92 500 M |
| Volume acheté | 740 000 M | 462 500 M |
| Stock physique moyen aux 52 photos | 257 191,42 M | 92 167,91 M |
| Écart absolu moyen aux photos sources | 146 684,03 M | 47 409,57 M |
| Stock physique à la clôture du 31 décembre | 442 729,4 M | 165 229,4 M |

La moyenne des photos sources est de 119 272,02 M. L'écart absolu moyen baisse
de **67,68 %**, mais le modèle reste en dessous des stocks industriels sur
une partie de l'année. Les cinq réceptions simulées arrivent les 26 février,
2 juillet, 11 août, 19 octobre et 22 novembre ; elles ne reproduisent pas
exactement les quatre hausses nettes identifiées dans les photos sources.
La consommation physique annuelle de 730384 reste 365 657,6 M dans les deux
calculs. Le nouveau maximum quotidien est de 188 083 M.

Sur l'ensemble des 29 couples comparables, **13 stocks se rapprochent,
15 s'éloignent et un reste identique**. La suppression des aléas et marges
de délai sur toutes les liaisons n'est donc pas une amélioration universelle
de calibration. Par exemple, l'écart moyen de 001848 / Avène passe de
1 999,35 à 2 325,74 kg, celui de 001757 de 1 423,88 à 1 676,93 kg. Les demandes
complémentaires de 001848 sont strictement identiques dans les deux calculs.

Sur cinq ans, les 20 achats de 730384 respectent le multiple de 92 500 M,
les 56 jours avant arrivée et les cinq jours ouvrés de réception. Les
191 625 valeurs contrôlées de stock physique en UN sont entières. La trace
de J0 confirme une fenêtre de couverture de 71 jours et une cible de
71 906,98 M avant achat, au lieu des 118 jours de la référence.

Preuves : [oracle indépendant](../../artifacts/testing/mrp_730384_fixed_20261002/validation/postrun.json)
et [qualification CSV](../../artifacts/testing/mrp_730384_fixed_20261002/validation/native/qualify-cebbd78bac6945f496d297c0f5a4ca1e/manifest.json).
La [comparaison interactive](../../resultats/mrp_730384_fixed_20261002/comparaison.html)
présente les deux simulations et les sources, avec 730384 sélectionné à l'ouverture.

## Rectification du périmètre des consommations complémentaires — 2 octobre 2026

L'utilisateur rappelle que les matières signalées comme partagées sont
**002612 / Avène, 007923 / Avène et 042342 / Gien**. **001848 / Avène n'a
pas été confirmée comme partagée.** La présenter comme telle dans
l'explication des derniers résultats était incorrect.

La configuration A2/G contient pourtant une consommation complémentaire
physique pour 001848. Elle provient d'une estimation automatique : sur le
support du premier plan du 5 janvier (J11 à J340, 29 lignes de besoin),
18 490 kg de besoins sources sont comparés à 5 108,536818 kg calculés à
partir des besoins du PF représenté et de sa BOM. La différence de
13 381,463182 kg devient une fraction de **72,371353 %** appliquée aux
besoins sources pour représenter des usages additionnels. Cette fraction
initiale reste fixe lors des révisions hebdomadaires de 001848.

Le champ `shared_use_status` vaut explicitement **`hypothesis_only`**.
L'estimateur `shared_components.py` retient les écarts au-delà de son seuil
sans exiger une confirmation de partage ; le moteur exécute ensuite les
demandes complémentaires configurées. Il y a **19 couples actifs** dans
A2/G, dont les trois signalés et **16 hypothèses supplémentaires**. Le
statut documentaire de ces dernières n'empêche pas leur effet physique.

Cette soustraction ne démontre ni l'existence d'autres produits consommateurs,
ni leur proportion. Un écart entre besoins sources et besoins calculés doit
d'abord rester un écart à expliquer : périmètre de demande, programme de
fabrication, nomenclature, calendrier ou autres causes possibles. Même pour
les trois matières partagées signalées, les proportions estimées ne sont
pas, à elles seules, des consommations industrielles mesurées.

La BOM fournie de 268091 contient 001848 à **1 218 G pour 1 000 PF** ; les
BOM fournies de 268967 et 773474 ne la contiennent pas. L'existence de stocks
001848 à Gien et Avène ne démontre pas plusieurs formulations utilisatrices
au même site d'Avène. Aucun champ source ne fournit la fraction de 72,37 %.
Ces constats ne prouvent pas non plus une exclusivité industrielle absolue,
les BOM disponibles ne couvrant pas toute l'entreprise.

Les résultats A2/G conservés sont donc **conditionnels à ces hypothèses
physiques non validées**. Les contrôles de calcul réussis ne valident pas
ce périmètre métier. Aucune nouvelle simulation ni suppression silencieuse
des calendriers n'est réalisée dans cette rectification. Avant de poursuivre
la calibration MRP, il faut séparer le périmètre signalé par l'utilisateur
des autres hypothèses et mesurer leur effet dans un calcul distinct.

Preuves : [périmètre source de 001848](../../artifacts/testing/mrp_730384_review_20261002/source_review/001848_scope.json)
et [inventaire des hypothèses actives](../../artifacts/testing/mrp_730384_review_20261002/parent_review/shared_scope_audit.json).

## Diagnostic ciblé de 730384 à Gien — 2 octobre 2026

Cette analyse porte sur les calculs A2/G déjà terminés ; aucune nouvelle
simulation ni modification du moteur n'est réalisée dans ce diagnostic.
L'unité de 730384 est le **mètre (M)** dans la FIA, les stocks et le MRP.

La FIA de `268967.xlsx`, cellule G7, donne une **quantité standard de
commande de 370 000 M**, sans préciser qu'elle est un minimum ou un multiple
obligatoire. Le simulateur l'interprète pourtant comme les deux, puis livre
la quantité commandée en une fois. Ce comportement existait déjà dans A2 ;
G rend aussi les propositions cohérentes avec cet arrondi d'exécution.

Dans les sources, les entrées H sont de **87 000 M** jusqu'au plan du
16 février, puis de **92 500 M** dès celui du 23 février. Les 295 positions H
positives sont réparties entre 52 versions de plan, pas 295 commandes.
`370 000 = 4 × 92 500` suggère plusieurs échéances possibles, sans démontrer
un fractionnement d'une commande identifiée ni un contrat annuel.

Les photos présentent quatre hausses nettes : 102 500 M entre les 3 et
10 mars ; 89 114 M entre le 26 mai et le 2 juin ; 93 000 M entre les 18 et
25 août ; 100 103 M entre les 10 et 17 novembre. Ces hausses nettes ne sont
pas des quantités brutes reçues, puisque des consommations ou ajustements
peuvent intervenir entre les photos.

Dans G, deux achats de **370 000 M**, soit 740 000 M, arrivent les 26 février
et 22 novembre 2025. Aux 52 dates de photo rapprochées de la clôture simulée
précédente, le stock physique moyen est **257 191 M**, contre **119 272 M**
dans les sources. Le maximum quotidien simulé atteint 465 583 M, contre
183 300 M pour le maximum des photos hebdomadaires ; leurs fréquences de
mesure sont différentes. Le problème est donc matériel, pas seulement visuel.

Une incohérence distincte subsiste dans la couverture : les achats exécutés
utilisent le délai source de **56 jours**, mais `pair_stock_cover_days`
utilise encore le quantile approximatif Erlang de **103 jours** lorsque le
drapeau stochastique est actif pour les autres flux. Avec 14 jours calendaires
équivalents à la sécurité source de 10 jours ouvrés et un jour de revue,
la couverture atteint 118 jours. Le traitement à réception de cinq jours
ouvrés intervient séparément dans la date de disponibilité (63 jours à J0),
pas dans ces 118 jours. Cette divergence n'est pas une donnée industrielle.

À J0, après une consommation de 22 853,6 M, le disponible vaut 45 533,4 M.
La cible calculée est de 108 710,844 M : le besoin net de lancement de
**63 177,444 M est arrondi à 370 000 M**. Réduire la marge de couverture
ne suffirait donc pas, à elle seule, à corriger la taille de cette livraison.

La BOM fournie utilise 212 M pour 1 000 unités du PF 268967. Aucun autre
emploi de 730384 n'est trouvé dans les BOM fournies ; son exclusivité dans
toute l'entreprise n'est pas démontrée. Le modèle ne lui ajoute pas de
consommation estimée d'autres produits. **Le mécanisme des matières partagées
n'est donc pas une cause identifiée pour ce cas.**

La correction à étudier doit rendre cohérentes couverture et dates en mode
« délai source », puis distinguer explicitement standard d'achat et taille
d'entrée en stock. Un candidat autour de 87 000/92 500 M nécessite un test
séparé et une hypothèse déclarée ; remplacer dès janvier le standard source
par la valeur dominante observée plus tard introduirait une information
future. La sécurité source (10 jours ouvrés, 23 500 M fixes) reste conservée.

Preuves : [lecture indépendante des Excel](../../artifacts/testing/mrp_730384_review_20261002/source_review/source_audit.json),
[désignation et emplois BOM](../../artifacts/testing/mrp_730384_review_20261002/source_review/source_labels.json),
[commandes et stocks des simulations conservées](../../artifacts/testing/mrp_730384_review_20261002/parent_review/simulation_comparison.json).

## Expérience : lots proposés et lots commandés — 2 octobre 2026

Objectif : tester une règle simple issue des rapprochements de 001848,
avec un témoin inchangé, puis contrôler les autres matières. Les entrées H
futures ne servent pas à commander : elles restent des cibles de comparaison.
Le moteur possédait déjà les propositions révisables, les achats lancés et
les besoins versionnés. Le nouveau candidat porte sur **le moment où la
taille de lot du fournisseur est appliquée**.

| Règle | Condition et comportement |
|---|---|
| Besoins connus | Utiliser la dernière version disponible à la décision ; horizon glissant de 364 jours. Les révisions ne sont pas additionnées entre elles. |
| Couverture existante | Déduire le stock disponible et chaque engagement une seule fois. Respecter les disponibilités futures des stocks détenus. |
| Dates distinctes | Distinguer besoin, disponibilité protégée, arrivée physique et lancement ; conserver sécurité source, délai nominal fournisseur et traitement à réception. |
| Lot provisoire candidat | Uniquement pour les offres explicitement admissibles, proposer avec le plus petit standard positif avant le lancement ; aucune commande n'est encore engagée. |
| Lot au lancement | À l'échéance, utiliser l'offre retenue et son lot de commande ; déduire immédiatement tout surplus des besoins suivants. L'arrondi est une convention testée, pas une contrainte FIA démontrée. |
| Fournisseur | Conserver les rôles principal/secours confirmés et les contrôles de délai et de prix ; ne pas étendre ces rôles à des fournisseurs sans configuration admissible. |
| Commande déjà lancée | Conserver son engagement et sa date prévue ; ne pas recommencer son délai à chaque recalcul. Aucune confirmation fournisseur inconnue n'est inventée. |

Le flag expérimental est
`meta.purchase_proposal_lot_policy = minimum_admissible_standard_until_release_v1`.
Son absence conserve le comportement courant. La séparation lot provisoire /
lot commandé est une hypothèse générale de calcul ; les données ne prouvent
pas encore que le MRP industriel choisit le minimum des standards admissibles.
La configuration actuelle de principal/secours concerne 001848 à Avène ;
les autres matières servent notamment de témoins de non-régression.

Les variantes sont construites sur les mêmes données et le même code :
**A**, référence acceptée ; **B**, A avec lots provisoires ; **C**, B avec
anticipation des besoins par la sécurité source (`source_safety_backwards_v1`).
C est construit depuis A pour ne pas confondre ce changement avec les autres
modifications du dernier essai. **D** reprend B et étend les besoins industriels
totaux de quatre à vingt-deux couples matière/site ; **E** ajoute à D la même
anticipation que C. Pilotes sur 2025, puis qualification à cinq
ans du témoin et du candidat retenu après comparaison. Aucun résultat positif
n'est présumé par cette description du protocole.

La référence ne possède les besoins industriels totaux que pour 001757,
002612, 007923 et 055703 à Avène. Pour 001848, elle combine les besoins propres
avec une consommation des autres produits estimée à 72,371 % des besoins
sources. Sur les semaines futures renseignées communes, les plans des
9, 16 et 23 février contiennent respectivement **18 320 / 20 130 / 20 130 kg**
de besoins sources, contre **14 131,93 / 15 783,91 / 15 935,16 kg** dans A.
Corriger seulement les tailles de lots ne peut pas supprimer cet écart amont.

Dans D/E, sur chaque fenêtre renseignée, le complément prévu est
`max(0, besoin industriel total − besoin propre)` : le total prévu est donc
`max(besoin industriel total, besoin propre)`. Les versions futures encore
inconnues et les entrées H ne sont pas injectées. Les quatre séries existantes
sont identiques ; les dix-huit autres sont ajoutées sans reprendre les
politiques fournisseurs du précédent essai. Ce changement alimente aussi
le calcul des cibles de couverture, avec leurs coefficients inchangés.
Il ne remplace pas la consommation physique BOM et ne modifie pas directement
le calendrier des consommations des autres produits du site.

Dans C/E, la sécurité en jours anticipe les besoins datés ; le stock de
sécurité fixe source reste une borne distincte. Le calcul conserve le maximum
entre la couverture des besoins anticipés et celle des besoins physiques
augmentée du stock fixe. Les anciens compléments de sécurité temporelle sont
désactivés pour ces achats afin de ne pas ajouter deux fois la même sécurité.
La règle visée remonte ensuite `lancement + délai fournisseur + réception`
pour respecter l'échéance protégée. C/E et le sourcing explicite de 001848
utilisent le calendrier futur. Dans A/B/D, les autres propositions figent
encore le délai total au jour de décision : recalculer la disponibilité à
partir du lancement peut donner un écart de un ou deux jours. L'analyse
distingue cette approximation d'un retard fournisseur.
Les engagements déjà lancés ne sont pas redatés.

### Résultats des cinq pilotes sur 2025

Les cinq calculs sont terminés, avec code et entrées inchangés pendant chaque
exécution. Les achats ci-dessous sont les **nouveaux achats lancés** ; la
commande initiale de 6 tonnes est comptée séparément. Les coûts ne couvrent
que l'achat externe de cette matière, pas le coût total de la chaîne.

| 001848 / Avène | A : référence | B : lots proposés | C : B + sécurité datée | D : B + besoins complets | E : D + sécurité datée |
|---|---:|---:|---:|---:|---:|
| Écart absolu moyen du stock aux 52 photos, kg | 1 937,27 | 1 937,27 | 2 232,67 | 1 999,35 | 2 269,70 |
| Achats nouveaux, kg | 24 000 | 24 000 | 24 000 | 24 000 | 24 000 |
| Lots lancés | 4 × 6 000 | 4 × 6 000 | 2 × 6 000 + 3 × 4 000 | 4 × 6 000 | 2 × 6 000 + 3 × 4 000 |
| Coût documenté, EUR | 37 920 | 37 920 | 69 360 | 37 920 | 69 360 |

B conserve strictement les stocks et le service de A : son effet concerne
les propositions. D améliore le stock de 13 des 22 couples d'achat externe
et en dégrade neuf ; le service du produit 268091 augmente de 28 800 UN.
E gagne encore 28 800 UN de service par rapport à D, mais dégrade 15 des
22 stocks. Les unités des différentes matières ne sont pas additionnées.
Ces résultats ne justifient pas une promotion globale de C/E au nominal.

Pour le plan du 23 février de 001848, D prévoit 20 078,09 kg sur les semaines
communes renseignées, contre 20 130 kg dans la source. Le manque de besoins
de A/B est presque résorbé, sans reproduire pour autant l'arrivée d'avril.
L'état utilisé par la décision diffère aussi : la source contient 5 874,44 kg
en J courant et 6 000 kg en J futur dans la semaine repérée au 2 mars ; le simulateur a
6 903,28 kg disponibles et 6 000 kg indisponibles jusqu'au 11 mars. Il faut
distinguer cet écart de stock/disponibilité du choix de la règle MRP, sans
réinjecter arbitrairement une photo industrielle dans la trajectoire simulée.

Un défaut de cohérence supplémentaire est identifié dans le plan générique :
hors politiques spécifiques, les propositions utilisent encore une taille
de lot libre, alors que leur exécution peut appliquer le standard d'achat.
La correction expérimentale suivante doit appliquer le même arrondi dès la
proposition lorsque les données permettent de déterminer ce standard sans
ambiguïté. Les lots fournisseurs non contraignants et les règles spécifiques
existantes doivent rester respectés.

### Candidat G : arrondi commun entre proposition et exécution

Le candidat G reprend D et active uniquement
`meta.purchase_planning_lot_policy = execution_standard_for_unambiguous_offer_v1`.
Cette deuxième étape utilise un nouvel état du code ; les cinq pilotes
précédents restent des résultats historiques de la première étape. Le
contrôle final compare A2 et G sur **le même moteur et 1 825 jours**,
en rapprochant uniquement leur année 2025 des données industrielles ; ses
résultats terminés sont présentés ci-dessous.

Conditions du nouvel arrondi :

- Achat externe agrégé, avec une seule offre ou une offre déjà sélectionnée
  explicitement dans la configuration ; aucun fournisseur n'est inventé.
- Standard déjà contraignant dans l'exécution nominale : la proposition
  utilise le même minimum et le même multiple. Ainsi, un besoin de 305 kg
  avec un standard de 300 kg produit 600 kg ; le surplus couvre la suite.
- Standard non contraignant : conserver cette exception. Un multiple physique
  de transport existant et les quantités physiques UN entières restent exigés.
- Une politique spécifique de sourcing, de regroupement ou de frontière a
  priorité. Les offres multiples non tranchées restent inchangées.
- Un standard incompatible avec le multiple physique provoque un refus
  explicite de ce candidat ; aucun nouveau multiple n'est fabriqué.

Dans ce graphe, 19 couples sont admissibles, dont **17 avec arrondi standard**.
333362 et 338929 conservent leur standard non contraignant. Le sourcing de
001848 reste celui testé en B/D ; 001893 et 021081 gardent leurs offres
multiples non tranchées. Ces conditions sont génériques dans le code : les
références citées décrivent le périmètre du jeu de données, pas des exceptions
codées dans la règle.

Les 33 tests ciblés et l'oracle indépendant de l'arrondi passent sur cet état
du code. Ils établissent la cohérence nominale du calcul, **pas** que tous les
standards industriels sont obligatoirement des minima ou des multiples.
La confrontation aux quantités H et aux stocks reste nécessaire. Les
contraintes de capacité ou les incidents peuvent encore limiter l'exécution
physique d'une proposition ; l'égalité proposition/exécution n'est pas promise
dans ces situations.

Le pilote G365 est terminé : **20 901 propositions et 386 achats exécutés**
des 17 couples respectent l'arrondi nominal, sans anomalie détectée. Ses
stocks et son service sont identiques au pilote D ; le gain de cette règle
porte donc ici sur les projections, pas sur la trajectoire physique.

Sur le même support de 1 109 instantanés, 37 539 semaines renseignées et
11 940 positions H positives des 22 couples :

| Appariement univoque des positions projetées | D | G365 |
|---|---:|---:|
| Quantité et semaine exactes | 370 | 952 |
| Quantité exacte et date à ±7 jours | 490 | 1 664 |
| Quantité exacte, sans contrainte de date | 934 | 2 629 |

L'amélioration à ±7 jours concerne 14 couples, huit restent inchangés et
aucun ne se dégrade sur ce critère. **L'objectif de reproduire une majorité
des quantités et dates industrielles n'est pas atteint** : 1 664/11 940 =
13,94 %, et 2 629/11 940 = 22,02 % lorsque la date est ignorée. Ces ratios
comptent des positions répétées dans les versions du plan, pas des commandes
industrielles identifiées ni des volumes achetés. Le support absent n'est
pas rempli de zéros et aucune même position n'est réutilisée dans un score.

La limite ne vient pas uniquement des dates. Par exemple, le moteur utilise
un standard de 1 100 kg pour 016332, alors que H contient fréquemment 200,
400 ou 600 kg ; pour 730384, le standard chargé est 370 000 m et H contient
92 500 ou 87 000 m. Pour 338928, le standard de 25 000 UN ne correspond pas
aux quantités H fréquentes de 147 072, 137 880 ou 36 768 UN. Ces contrastes
interdisent de généraliser « standard = multiple obligatoire » à partir du
seul intitulé FIA. Ils ne permettent pas non plus d'affirmer que chaque H
est une commande complète plutôt qu'une échéance de livraison. Aucun
conditionnement ni fractionnement industriel absent n'est inventé pour
forcer l'appariement.

### État matière de 001848 : cause distincte de la règle d'achat

Au 23 février, G a consommé 3 359,364535 kg depuis l'ouverture : 350,784 kg
pour le produit représenté et 3 008,580535 kg pour les autres usages du site.
La photo du 24 février et le plan du 23 février donnent 11 874,44 kg physiques.
En supposant que la seule entrée de la période est la commande initiale
documentée de 6 000 kg, le bilan des photos implique 4 388,206 kg de sorties
nettes, soit **1 028,841465 kg de plus** que la consommation représentée.
Ce bilan ne permet pas de classer toutes les sorties industrielles comme
consommation de production plutôt que transfert, rebut ou ajustement.

La ventilation physique garde une fraction annuelle fixe de 72,371353 %
pour les autres usages, alors que D/G utilisent déjà les besoins totaux du
site en planification. Sur cette fenêtre, la part théorique restante pour
le produit représenté serait 1 148,562 kg, contre 350,784 kg effectivement
consommés par ses fabrications dans le modèle. La différence de 797,778 kg
représente environ 77,5 % de l'écart de stock. Il s'agit de l'écart à cette
**hypothèse de ventilation**, pas de la preuve que l'usine aurait dû produire
la quantité correspondante. Le solde de 231,063 kg sépare les sorties nettes
déduites des photos et les besoins I sélectionnés avec le calendrier courant.

La date simulée de disponibilité du 11 mars vient de `Extract_En_cours.xlsx`,
ligne 8 : réception physique prévue le 20 février (G), traitement de 13 jours
(H), disponibilité le 11 mars (I). Le MRP du 23 février situe ensuite les
6 tonnes détenues en J dans la semaine repérée au 2 mars. Cette nouvelle
information de disponibilité n'est pas reprise par le calendrier initial
du simulateur. Une différence entre documents datés ne justifie ni une
modification arbitraire du délai nominal, ni une réinitialisation du stock.
Elle justifie de distinguer l'engagement conservé de ses dates prévisionnelles
susceptibles d'être révisées sur information nouvelle et identifiable.
L'écart de neuf jours entre les étiquettes « 2 mars » et « 11 mars » n'est
pas la mesure d'une avance physique exacte : le jour réel dans le premier
intervalle hebdomadaire et sa convention de borne restent à distinguer.

Les critères sont séparés : quantités des propositions, quantités des achats
lancés, stocks physiques aux photos de 2025, service et performance sur cinq
ans. Pour les plans, apparier une seule fois les entrées de même quantité,
avec semaine exacte puis tolérance de sept jours, sur le support futur connu
commun ; publier aussi les entrées supplémentaires et celles non retrouvées.
Chaque projection simulée est rapprochée de la dernière version industrielle
déjà connue. Ne pas comparer une disponibilité simulée à une livraison source,
ni additionner 52 versions pour annoncer un volume annuel commandé.

Le dernier texte utilisateur rend plausible un traitement achats distinct
du calcul du plan, mais ne fournit ni commande identifiée ni confirmation de
livraison au 6 avril. La documentation SAP distingue également le contrôle
de date dans certaines transactions achats du calcul MRP ; cela n'identifie
pas le paramétrage industriel utilisé ici.
Source : [contrôle de la date lors du choix fournisseur](https://learning.sap.com/courses/purchasing-in-sap-s-4hana/analyzing-special-aspects-in-customizing).

### Résultats finaux A2/G et décision de conservation

Les deux simulations de **1 825 jours** se terminent avec un code retour nul,
en **700,73 s pour A2** et **687,00 s pour G**. Code et entrées sont restés
inchangés pendant chaque calcul. Cet écart de temps isolé n'est pas une
preuve d'accélération du moteur. Les résultats de 2025 des simulations longues
sont identiques à ceux des pilotes correspondants ; la comparaison aux
sources porte uniquement sur 2025, pas sur cinq années de données réelles.

| Projections 2025, même support de 11 940 positions H sources | Référence A2 | Candidat G |
|---|---:|---:|
| Même quantité et même semaine | 382 | 952 |
| Même quantité à sept jours près | 493 | 1 664 |
| Même quantité, date ignorée | 911 | 2 629 |

La comparaison finale A2/G améliore les appariements de 16 des 22 couples,
en laisse cinq identiques et en dégrade un : **338929** (10 à 8 appariements
à sept jours près). Pour **001848 / 1810**, le score correspondant passe
de 18 à 32 sur 176 positions H. Il s'agit toujours de versions répétées de
plans, pas du nombre de commandes annuelles. Le candidat produit encore
11 046 positions sans correspondance à sept jours près et laisse 10 276
positions sources non retrouvées. La convention de regroupement employée
par cet oracle est la semaine commençant le dimanche ; la borne industrielle
exacte reste à confirmer et la tolérance de sept jours ne résout pas une
différence de nature entre commande et échéance de réception.

Sur les **stocks physiques aux photos**, le candidat améliore 13 des 22
couples d'achat externe et en dégrade neuf. Sur l'ensemble des 29 couples
comparables de la carte, le bilan est de 16 améliorés, 11 dégradés et deux
inchangés. Pour 001848, l'écart absolu moyen augmente de **1 937,27 à
1 999,35 kg** ; l'entrée d'avril n'est pas reproduite. Les quantités lancées
en 2025 restent quatre achats de 6 000 kg, distincts de l'engagement initial.

Sur cinq ans, les quantités finales servies des deux produits représentés
restent identiques. Pour 268091, la somme quotidienne des quantités en retard
passe de 6 523 104,025 à 3 838 453,025 UN·jours, soit une baisse de 41,16 %.
Ce progrès interne au modèle ne prouve pas la fidélité du MRP industriel.

**Décision : conserver G comme candidat séparé, sans remplacer la référence.**
La cohérence entre arrondi proposé et arrondi exécuté est vérifiée ; son
interprétation industrielle et la consommation des matières partagées ne
sont pas suffisamment établies pour annoncer une calibration globale.
Les essais C/E de sécurité datée sont conservés comme comparaisons, sans
activation générale. Les jours et stocks de sécurité sources ne sont pas
diminués pour rapprocher artificiellement les courbes.

### Livrables, vérifications et reproduction

- [Comparaison interactive A2/G](../../resultats/mrp_regles_communes_20261002/comparaison.html) : stocks et plans 2025, deux trajectoires issues des simulations longues, tableau de 29 couples cliquables.
- [Exécutions et commandes exactes](../../artifacts/testing/mrp_common_rules_20261002/experiment_v2/report.json) : paramètres, durées et empreintes avant/après.
- [Appariements des plans](../../artifacts/testing/mrp_common_rules_20261002/validator/plan_dates_v2_final_comparison.json) et [oracle indépendant des trajectoires](../../artifacts/testing/mrp_common_rules_20261002/validator/A2_G1825_final_postrun.json).
- [Qualification native agrégée](../../artifacts/testing/mrp_common_rules_20261002/native_final/gate-0a3f15ad38864cf8a4f1f390afc67b63/manifest.json) : doctor, 33 tests ciblés et deux qualifications CSV longues réussis.
- [Vérification numérique du contenu de la carte](../../artifacts/testing/mrp_common_rules_20261002/validator/payload_final_review.json) : 105 850 valeurs de stock, 1 646 photos sources et 718 cellules de métriques vérifiées.
- [Contrôle navigateur hors ligne](../../artifacts/testing/mrp_common_rules_20261002/browser_d3e23d91b0/report.json) : 2 918 rapprochements stock affiché/CSV aux photos, tableau, onglets, sélection, filtre du dernier trimestre et zoom. Ce contrôle ciblé de la comparaison autonome ne vaut pas qualification exhaustive de la carte complète et de ses suivis de lots.
- [Archive unique de reproduction](../../config/mrp_common_rules_20261002/checkpoint.zip) : sources, code, graphes et commandes A2/G ; [contrôle de son intégrité](../../artifacts/testing/mrp_common_rules_20261002/reproduction_bundle_verification.json).

L'archive préserve les fichiers nécessaires aux deux calculs et les versions
de dépendances déclarées. Son contenu a été vérifié sans extraction et sans
installation d'environnement ; aucun rejeu depuis une extraction n'est
annoncé. Les commandes portables de `reproduction-bundle.json` utilisent
`${PYTHON}`, `${ROOT}`, `${RUN_OUTPUT_0}` et `${RUN_OUTPUT_1}` : les sorties
doivent viser deux dossiers nouveaux. `regenerate.py` n'est pas modifié et
ne sélectionne pas automatiquement ce candidat. La comparaison peut être
reconstruite depuis les nouveaux CSV avec le module existant
`etudecas.visualization.maps.source_comparison` ; le rendu de cette expérience
est documenté dans `experiment_v2/orchestrate.py`. La reconstruction exacte
de ce rendu personnalisé à partir de la seule archive n'a pas été testée.

## Replanifications de février : effet des besoins révisés — 2 octobre 2026

Le classeur utilisateur `Replanifications_MRP_001848_1810.xlsx` et son texte
d'accompagnement portent sur **001848 / 1810**. Le diagnostic retire les
nouvelles entrées proposées à partir de mars et conserve les stocks J datés
ainsi que les 6 tonnes de l'en-cours initial. Il mesure un manque conditionnel
dans chaque version des besoins ; il ne représente pas une rupture réellement
survenue. Les grammes sources sont convertis en kilogrammes.
Au plan du 23 février, les 6 tonnes figurent déjà en **J7087**, datées du
2 mars : elles sont conservées à cette date et ne sont pas ajoutées une
seconde fois comme entrée H.

| Version du plan | Entrée source de 4 tonnes | Premier manque recalculé | Anticipation constatée |
|---|---|---|---:|
| 2 février | 18 mai | 6 juillet | 7 semaines |
| 9 février | 4 mai | 29 juin | 8 semaines |
| 16 février | 13 avril | 8 juin | 8 semaines |
| 23 février | 6 avril | 22 juin | 11 semaines |

### Déplacement du manque du 29 juin au 8 juin

Entre les versions du 9 et du 16 février, le besoin prévu au repère du
**8 juin passe de 1 800 à 2 700 kg**. Sans les nouveaux achats, la couverture
à cette date devient :

| Bilan au 8 juin | Plan du 9 février | Plan du 16 février |
|---|---:|---:|
| Ressources restantes avant cette sortie | 2 405,610 kg | 2 394,640 kg |
| Sortie de la semaine | 1 800 kg | 2 700 kg |
| Solde après sortie | +605,610 kg | −305,360 kg |

Le contrefactuel qui conserve tout le plan du 9 février et remplace seulement
les 1 800 kg du 8 juin par 2 700 kg donne **−294,390 kg** : cette seule
modification avance le premier manque de trois semaines. Il s'agit d'un test
en mémoire des prévisions de cette version, pas d'une modification des sources
ou d'une utilisation des consommations futures réellement constatées.

L'entrée source avance également de trois semaines, du 4 mai au 13 avril.
**La hausse des besoins explique le déplacement du manque et concorde avec
celui de l'entrée si l'anticipation observée est maintenue.** Elle ne démontre
pas comment les huit semaines ont été calculées. Le classeur extrait les dates
H sources avec `MINIFS` (`Lecture!B9:B12`), recalcule les premiers manques
(`C9:C12`), puis mesure leur différence. Il ne calcule pas une nouvelle date
H à partir des seuls paramètres de sécurité et de réception. Les huit semaines
ne sont pas une nouvelle règle universelle, ni une identification du délai
fournisseur à appliquer entre la livraison et le besoin.
Les 1 500 lignes recopiées dans `Source_MRP` concordent avec l'original sur
les 15 000 cellules contrôlées. La recherche du manque dans le classeur est
bornée à mars–juillet, ce qui couvre les quatre cas étudiés ; elle n'est pas
une vérification de tout l'horizon. Les textes explicatifs restent fixes si
des paramètres sont modifiés. Les liens du graphique sont contrôlés
statiquement ; son rendu dans Excel n'a pas été exécuté.

### Comparaison des ressources à une même date

À période comparable jusqu'au 8 juin, les nouvelles ressources sont
supérieures de **179,030 kg** à ce qu'indiquait l'ancien plan ; les besoins
augmentent de **1 090 kg**. L'effet net est donc **−910,970 kg**, soit le
passage de +605,610 à −305,360 kg. Une simple comparaison des stocks initiaux
de deux semaines différentes confondrait cet effet avec l'écoulement déjà
prévu de la première semaine.
L'ancien plan donne précisément **6 955,610 − 1 080 = 5 875,610 kg**
(`J5098 − I5098 = K5098`), face aux **6 054,640 kg** du nouveau plan
(`J6082`). Le gain de 179,030 kg est donc calculé dans les repères MRP,
sans déduire une convention universelle de semaine depuis les photos.

Les photos d'inventaire donnent **6 955,610 kg au 10 février** et
**6 054,640 kg au 17 février** (`Stocks!E164`, `E1112`, après conversion).
Ces photos sont des soldes : leur différence ne suffit pas à identifier une
consommation exécutée ou une réception individuelle. La décomposition permet
d'attribuer l'aggravation du manque projeté aux besoins révisés ; elle ne
démontre pas l'origine commerciale de ces besoins.

### Pourquoi le dernier mouvement reste distinct

Au plan du 23 février, le besoin du 8 juin diminue à **1 260 kg** et le solde
projeté à cette date remonte à **+774,440 kg**. Le premier manque recule au
22 juin, tandis que l'entrée avance au 6 avril. Une même marge constante
soustraite au premier manque ne reproduit donc pas cette séquence. Le passage
du 2 au 9 février présente déjà un résidu d'une semaine : manque avancé de
sept jours, entrée de quatorze jours.

Le modèle doit distinguer **date de besoin protégée calculée**, **date portée
par une proposition ou commande** et, si elle existe, **date suggérée de
replanification**. Dans SAP, une proposition non fixée peut être recalculée ;
un élément fixé peut donner lieu à une suggestion d'avance ou de report selon
les paramètres. Les messages 10 et 15 sont documentés, mais absents de cet
export ; ils ne prouvent pas le mécanisme appliqué ici. Une fixation seule
n'explique pas l'avance initiale au 6 avril.
Sources : [modes de recalcul](https://learning.sap.com/courses/consumption-based-planning-and-forecasting-in-sap-cloud-erp/scheduling-planning-runs),
[contrôle de replanification et messages](https://help.sap.com/docs/SUPPORT_CONTENT/mrp/3138697863.html).

Conséquence pour les expériences : utiliser les besoins datés de chaque
version, conserver les paramètres de sécurité sources et mesurer séparément
le manque, la disponibilité protégée, la réception et le lancement. Garder
les quatre versions ci-dessus comme cas de référence ; ne pas remplacer
une marge ajustée de sept semaines par huit ou onze semaines pour retrouver
une date. Le diagnostic ne valide pas encore un MRP autonome.

Preuves : [oracle depuis le Flow MRP original](../../artifacts/testing/mrp_replanning_review_20261002/source_oracle.json),
[audit du classeur](../../artifacts/testing/mrp_replanning_review_20261002/workbook_review.json),
[photos d'inventaire](../../artifacts/testing/mrp_replanning_review_20261002/stock_context.json),
[manifeste](../../artifacts/testing/mrp_replanning_review_20261002/manifest.json).
Le moteur et les cartes n'ont pas été modifiés pendant cette passe ; aucune
simulation n'a été relancée.

## Complément : projection glissante et lancement des achats — 2 octobre 2026

Le second texte utilisateur précise une distinction essentielle :
**la première apparition d'une entrée future dans un plan n'est pas la
date de lancement d'une commande**. Les 4 tonnes proposées dès janvier
ne prouvent donc aucun engagement ou gel à cette date. Les 63 entrées
conservées dans H2 restent des hypothèses de reproduction, pas des commandes
dont le statut ferme aurait été découvert. Une quantité de 4 ou 6 tonnes
ne suffit pas à déterminer la nature du document ou son fournisseur.

La documentation SAP distingue propositions internes modifiables et
commandes, ainsi que calcul sur l'horizon, période d'ouverture et conversion.
Elle décrit aussi des modes qui révisent les propositions non fixées tout
en conservant les propositions fixées. Cela fournit des mécanismes de
référence, **sans identifier le logiciel ou les paramètres de cet industriel**.
Sources : [processus MRP](https://learning.sap.com/courses/exploring-end-to-end-business-processes-in-sap-business-suite/analyzing-material-requirements-planning-mrp-_cf433b5f-83cf-4c45-a9f8-54c0e6ca0aa5),
[calculs successifs et période d'ouverture](https://learning.sap.com/courses/consumption-based-planning-and-forecasting-in-sap-cloud-erp/scheduling-planning-runs).

Le contrat à tester dans le simulateur doit séparer :

1. **Projeter** les besoins connus à la date du calcul sur l'horizon glissant,
   avec les stocks disponibles aux bonnes dates et les réceptions engagées.
2. **Proposer** des achats datés couvrant les manques protégés, avec quantité
   calculée selon les règles de lotissement. Une proposition peut être
   affichée plusieurs mois avant son lancement nécessaire.
3. **Lancer** les commandes selon leur date calculée et une règle explicite
   de traitement des achats. Le délai fournisseur sert à calculer cette
   date ; il ne limite pas la visibilité des besoins futurs.
4. **Réviser** les propositions encore modifiables et traiter explicitement
   les demandes de replanification des commandes engagées, sans double achat.

Pour 001848, la préférence pour le principal moins cher et le secours plus
rapide est confirmée par l'utilisateur. Elle ne prouve pas que **chaque
proposition lointaine** a déjà été affectée à ce fournisseur. Le choix doit
être testé au bon stade, en conservant la distinction entre proposition et
commande, plutôt que déduit de la seule quantité affichée.

Une piste supplémentaire est documentée par SAP : un arrondi porté dans
une fiche achat peut s'appliquer à la conversion en commande, alors que le
calcul de proposition suit son propre lotissement. Cela peut produire une
quantité proposée différente de celle finalement commandée. **Ce mécanisme
reste candidat pour les changements 4 → 6 tonnes** : les FIA disponibles
donnent des standards, sans démontrer ce paramétrage d'arrondi.
Source : [calcul des lots et arrondis](https://learning.sap.com/courses/consumption-based-planning-and-forecasting-in-sap-cloud-erp/understanding-the-lot-size-calculation).

**Contrôles directs du complément :** les 52 versions du Flow MRP vont
toutes, au niveau de l'export global, jusqu'à la date du calcul + 364 jours,
soit S+52. Les deux bornes représentent 53 repères hebdomadaires inclusifs,
pas 52 observations supplémentaires. Pour 001848/1810, la dernière ligne
exportée est plus proche dans chacune des 52 versions : au 19 janvier,
elle est datée du 9 novembre (`G2080`), contre le 18 janvier 2026 dans
l'export global. Une fin anticipée de lignes ne prouve pas un horizon MRP
plus court ; elle ne prouve pas non plus l'absence de besoins non exportés.

Dans la version du **19 janvier**, après conversion des grammes sources
en kilogrammes, `J2048` donne **8 797,022 kg** et `H2052` les **6 000 kg**
déjà attendus. En conservant cette entrée et en retirant
les autres H, le tableau des lignes 2064–2070 du texte est retrouvé :
**237,022 − 900 = −662,978 kg au repère du 6 juillet**. L'entrée de
4 000 kg est inscrite au **18 mai, H2065**, soit 49 jours avant ce manque.
Les dates de calcul, d'entrée proposée et de manque sont donc distinctes.
Le coefficient BOM est également confirmé : **1 218 g / 1 000 UN** de
268091, soit **121,8 kg pour 100 000 UN**, sans préjuger d'un OF réel.
Preuve : [contrôle horizon, janvier et BOM](../../artifacts/testing/mrp_reproduction_review_20261002/rolling_horizon_check.json).

Les besoins agrégés de la colonne I permettent de refaire le calcul aval,
mais ne distinguent pas prévisions de ventes, commandes clients et ordres
de fabrication. Pour isoler la règle d'achat, on peut utiliser uniquement
les besoins connus dans chaque version ; pour vérifier toute la chaîne
prévision → fabrication → matière, il faut aussi rapprocher leur origine.
Ne pas substituer les consommations réelles futures aux prévisions anciennes.
Le stock projeté K inclut les entrées proposées : sa positivité ne signifie
pas qu'aucun achat n'est nécessaire. Retirer une proposition dans un calcul
de diagnostic montre sa contribution à la couverture, sans prouver qu'elle
est liée à un besoin individuel précis.

## Reproduction H1/H2 fournie pour 001848 à Avène — 2 octobre 2026

Les deux classeurs utilisateur `Reproduction_MRP_001848_1810_2025.xlsx` et
`Regles_MRP_001848_1810_quatre_entrees.xlsx`, ainsi que le texte joint, ont
été examinés en lecture seule. Le premier contient de véritables formules
de propositions et de bilan. Une reconstruction indépendante depuis le
Flow MRP original, sans lire les résultats calculés du classeur, retrouve
ses résultats. Le rapprochement final porte sur **15 050 cellules numériques
des 2 150 lignes**, avec un écart maximal de 1,82 × 10⁻¹² kg.

### Ce que mesurent les résultats

| Rejeu des plans sources | H1 : choix selon délai disponible | H2 : conservation de certaines entrées |
|---|---:|---:|
| Stocks projetés identiques à 0,01 kg près | 1 147/2 150, soit 53,35 % | 2 040/2 150, soit 94,88 % |
| Écart absolu moyen sur le stock projeté | 1 054,53 kg | 97,08 kg |
| Plans entièrement reproduits | 2/52 | 22/52 |

Les 2 150 lignes comprennent **1 500 lignes originales et 650 semaines
intermédiaires ajoutées avec flux supposés nuls**. Sur les seules lignes
originales, H2 atteint 95,67 % et 77,61 kg d'écart moyen : les semaines
ajoutées n'améliorent donc pas artificiellement ce score.

H1 conserve l'entrée initiale de 6 tonnes, puis choisit le standard de
6 tonnes si la date calculée laisse au moins 56 jours, sinon celui de
4 tonnes à partir de 21 jours. H2 conserve **63 occurrences d'entrées
sources** : celles de 6 tonnes et l'entrée du 6 avril dans les plans du
23 février au 6 avril. Ce sont des positions répétées dans plusieurs
versions, **pas 63 livraisons de l'année**. Leur statut ferme est supposé
par le modèle, sans être fourni par un champ industriel.

Pour les propositions restantes, H2 emploie un regard à **7 semaines**,
issu de l'arrondi supérieur de (20 + 13) / 5, et des multiples de 4 tonnes,
avec plafonnement au besoin net restant jusqu'à la dernière ligne exportée.
Ce calcul est une hypothèse de reconstitution : la quantité standard de la
fiche achat ne prouve pas, à elle seule, un multiple obligatoire. Le regard
porte sur le solde à t+7, pas sur le minimum des soldes intermédiaires ; aucun
déficit masqué de cette façon n'a été trouvé sur ces 52 plans.

H2 génère 115 entrées face à 113 positions sources restant à retrouver.
L'appariement indépendant, une entrée au plus de chaque côté, confirme
**63 correspondances exactes en semaine et quantité**, et **100 à ±1 semaine
avec quantité identique**. À cette tolérance : 15 entrées générées sans
correspondance et 13 entrées sources non retrouvées, soit 86,96 % de précision
et 88,50 % de rappel. Ces observations entre versions ne sont pas des
commandes indépendantes.

### Ce que cela explique, et ce qui reste à identifier

La distinction **proposition recalculable / approvisionnement conservé**
est une piste concrète. Les quatre volumes retenus concordent avec les deux
offres, conditionnellement aux dates de plan et de réception déjà choisies.
En revanche, **H2 conserve précisément l'entrée d'avril dont on cherche à
expliquer la date** : il ne démontre ni pourquoi elle est avancée au 6 avril,
ni quand la commande part, ni le fournisseur effectivement retenu.

Dans H1, les formules donnent priorité à la ligne fournisseur de 56 jours :
elle est actuellement la moins chère, mais modifier les prix ne modifie
pas la sélection. H2 ne teste pas la faisabilité du délai fournisseur.
Le cas de juin tombe exactement à 56 jours et dépend donc de la convention
de semaine et du jour réel de lancement. Ces points interdisent de considérer
le classeur comme un moteur autonome de choix fournisseur déjà validé.

Chaque version repart des besoins et stocks datés sources : **52 relectures
indépendantes**, sans état des commandes transmis automatiquement d'un plan
au suivant. Le score 94,88 % décrit le stock projeté de ces relectures,
pas la précision d'une simulation annuelle ni celle des stocks physiques.
Sur les 51 prévisions de photo à une semaine du classeur, H2 donne un écart
moyen de **1 071,11 kg**, contre **1 040,56 kg** en conservant simplement la
photo précédente. L'autre convention de semaine testée donne 1 447,46 kg
pour H2 ; ce score ne suffit pas à identifier le calendrier industriel.

La suite à qualifier est donc une règle commune : calcul du manque protégé,
choix de l'offre réalisable au meilleur coût, passage explicite d'une
proposition à une commande engagée, puis maintien ou replanification de
celle-ci. Elle doit fonctionner sans exceptions « conserver tout lot de
6 tonnes » ou « conserver la semaine du 6 avril ». **Le moteur et les cartes
n'ont pas été modifiés et aucune simulation n'a été relancée pour cet audit.**

Preuves : [reconstruction indépendante](../../artifacts/testing/mrp_reproduction_review_20261002/rebuild.json),
[métriques et rapprochement des sources](../../artifacts/testing/mrp_reproduction_review_20261002/metrics_check.json),
[dépendances des formules et limites](../../artifacts/testing/mrp_reproduction_review_20261002/interpretation_review.json),
[manifeste de cette passe](../../artifacts/testing/mrp_reproduction_review_20261002/manifest.json).

## Fournisseur de secours et audit des quatre entrées — 2 octobre 2026

Le classeur utilisateur `Regles_MRP_001848_1810_quatre_entrees.xlsx` a été
rapproché des sources, en lecture seule. La nouvelle hypothèse examinée est :
**le principal devient trop lent, une commande est lancée chez le secours
lors de la première version affichant la nouvelle semaine**. Le mécanisme
est industriellement cohérent ; son déclenchement sur cet épisode reste
à démontrer. Ni l'identité de la commande ni sa date d'envoi ne figurent
dans les H agrégées.

### Convention de semaine : deux lectures à conserver dans le diagnostic

L'utilisateur envisage maintenant que le dimanche **6 avril soit la fin
de la semaine du 31 mars au 6 avril**. La lecture alternative est une semaine
commençant autour de ce dimanche, avec activité du 7 au 11 avril. Le nom de
la colonne et le dimanche seuls ne tranchent pas. Le rapprochement du carnet
initial ci-dessous favorise le dimanche précédant les dates G, sans établir
la convention de toutes les H ultérieures. **La formulation antérieure
présentant le lundi suivant comme une convention confirmée était trop forte.**

La réception physique est inférée entre les photos des **7 et 14 avril**,
indépendamment de cette convention. La comparer à une semaine finissant le
6 avril ou à une semaine suivante ne conduit pas à la même appréciation du
retard. Aucune date exacte de livraison ne doit en être déduite.

### Test du lancement supposé le 23 février

| Offre et calendrier testés | Arrivée physique calculée | Disponibilité après 13 jours lundi–vendredi |
|---|---|---|
| Secours, 21 jours calendaires | 16 mars | **2 avril** |
| Principal, 56 jours calendaires | 20 avril | **7 mai** |
| Variante principal, 56 jours ouvrés | 12 mai | 29 mai |

Avec un lancement le lundi 24 février, les deux premières disponibilités
deviennent respectivement le 3 avril et le 8 mai. **Le 2–3 avril appartient
bien à la semaine finissant le 6 avril.** Cette correspondance suppose
toutefois que H représente la disponibilité après traitement. Elle ne
retrouve pas l'arrivée physique visible entre les photos des 7 et 14 avril,
et elle diffère de la sémantique G étayée sur le carnet initial.

Le test déterminant est la faisabilité du principal au regard du besoin
protégé : sans les 4 000 kg et les achats ultérieurs, en conservant les
6 000 kg antérieurs, ce besoin apparaît le **26 mai** dans l'ancrage initial,
ou entre le **19 et le 26 mai** avec la semaine de besoin finissant le
22 juin. Le principal disponible le 7 mai serait encore à temps. Pour un
lancement compris entre les 17 et 24 février, sa disponibilité va du 1er
au 8 mai : la conclusion reste la même.

Ainsi, avec le délai fournisseur **calendaire**, « le principal est en
retard sur le besoin protégé » n'est pas retrouvé dans les champs connus.
Il serait trop tard pour une **échéance déjà imposée en avril** ; cette
condition n'explique pas pourquoi cette échéance a été imposée. Les
4 000 kg sont déjà proposés au plan du **19 janvier, H2065**, pour une semaine
de mai. Le 23 février identifie une révision de date, pas un lancement certifié.

En prenant **H comme arrivée physique et le dimanche comme fin de semaine**,
l'hypothèse utilisateur donne néanmoins une frontière utile :

| Plan connu | Semaine d'arrivée H supposée | Fenêtre de lancement avec 56 jours calendaires |
|---|---|---|
| 2 février | 12–18 mai | 17–23 mars |
| 9 février | 28 avril–4 mai | 3–9 mars |
| 16 février | 7–13 avril | **10–16 février** |
| 23 février | 31 mars–6 avril | **3–9 février, déjà passé** |

Le principal devient donc trop tard pour **tenir la cible H déjà inscrite**
si aucune commande n'a été engagée à temps. Le secours à 21 jours pourrait
encore la tenir avec un lancement du **10 au 16 mars**. Ce raisonnement rend
le secours plausible, sans imposer un départ de commande dès le 23 février.
Il ne déduit pas l'avance d'une semaine : un fournisseur plus rapide donne
une arrivée possible plus tôt, mais ne modifie pas à lui seul la date du
besoin à protéger. La cible H et la règle qui la produit restent à rapprocher.

La variante 56 jours ouvrés rendrait le principal tardif face au besoin
protégé de mai. Elle donne aussi, à partir des premières versions portant
6 tonnes, des arrivées le 23 juin, le 25 août et le 13 octobre ; les photos
encadrent les réceptions aux 23–30 juin, 1er–8 septembre et 13–20 octobre.
**Ce sont des concordances exploratoires**, dépendantes de dates de lancement
supposées. Le libellé FIA « jours » ne confirme pas ce calendrier. Aucune
fermeture n'a été ajustée pour retrouver septembre et aucun délai fournisseur
du moteur n'a été modifié. Ne pas combiner un principal en jours ouvrés et
un secours en jours calendaires pour fabriquer une preuve de bascule.

### Ce que le nouveau classeur confirme

Les quatre recalculs, depuis les plans du 19 janvier, 30 mars, 1er juin et
20 juillet, retrouvent chacun **49 jours entre le repère de la proposition
et celui du premier manque sans cette entrée ni les suivantes**. Les entrées
antérieures et les J datées sont conservées. Cela soutient une anticipation
des propositions, sans expliquer chacune de leurs révisions ultérieures.

Sur 176 occurrences H dans les versions successives, **102/120 quantités
autres que 6 tonnes** sont à 42 ou 49 jours du manque, contre **24/56** pour
6 tonnes. Le premier groupe contient **52 soldes terminaux**, pas uniquement
des lots standards ; les répétitions entre versions ne sont pas des commandes
indépendantes. Hors positions terminales, la correspondance vaut **81/124**.
Les changements de 4 à 6 tonnes pour juin, septembre et octobre s'accompagnent
respectivement de **+26,400 kg, +708,018 kg et +181,700 kg** de besoin net à
horizons communs. L'ajout de 2 tonnes sur un lot ne provient donc pas simplement
d'un ajout de 2 tonnes de consommation. La recomposition des achats est
étayée ; le fournisseur effectivement choisi et le passage à un statut
ferme ne sont pas identifiés.

### Conséquence pour la règle du simulateur

La règle de secours doit comparer **la disponibilité après traitement** de
chaque offre au **besoin protégé**, en tenant compte des approvisionnements
déjà alloués. Elle ne doit pas acheter deux fois la même quantité. Cette
comparaison existe dans le candidat `source_safety_backwards_v1`.
Dans le run existant `run_need_dates_2`, le 23 février, le principal est
disponible le **7 mai**, contre un premier besoin protégé manquant le
**2 juin**. Aucun nouvel achat ni secours n'est proposé du 16 février au
2 mars. Ce comportement est cohérent avec ce besoin calculé ; la date
industrielle d'avril exige encore une condition que cette reconstruction
ne retrouve pas. **Aucune nouvelle simulation ni modification moteur**
pendant cette passe.

Preuves : [audit du classeur](../../artifacts/testing/mrp_backup_trigger_20261001/workbook_check.json),
[calcul des deux offres](../../artifacts/testing/mrp_backup_trigger_20261001/backup_timing.json),
[règle existante et CSV](../../artifacts/testing/mrp_backup_trigger_20261001/engine_rule_check.json),
[manifeste](../../artifacts/testing/mrp_backup_trigger_20261001/manifest.json).

## Enquête complémentaire sur la semaine repérée par le 6 avril — 1er octobre 2026

**Convention discutée, précisée dans la section du 2 octobre ci-dessus :**
le 6 avril 2025 est un dimanche repère, pas un jour de livraison. La hausse
entre les photos du 7 avril (7 709,420 kg) et du 14 avril (10 987,820 kg)
encadre une réception probable ; son jour et l'heure des photos restent
inconnus. La lecture « semaine suivante du 7 au 13 avril » utilisée dans
cette passe est une hypothèse de rattachement, pas une convention confirmée
par l'utilisateur. La lecture « semaine finissant le 6 avril » doit également
être conservée dans les comparaisons.

Dans les tableaux ci-dessous, les dates du dimanche désignent donc des
**semaines sources**, à distinguer des dates précises figurant dans l'Extract.
Les oracles historiques conservent leurs conventions de calcul explicites ;
la présente correction supprime la fausse précision quotidienne du récit.

Cette passe confronte des mécanismes documentés par SAP aux sources locales.
**L'ERP de l'industriel reste inconnu.** Aucun paramètre SAP absent des sources
n'est ajouté au modèle. Les calculs sont des diagnostics sur les plans connus,
avec conservation des approvisionnements antérieurs ; ils ne sont pas une
nouvelle simulation ni une calibration validée.

### Résultat nouveau : H du carnet initial suit la livraison prévue dans l'Extract

Hors Gaillac, déjà contrôlé précédemment, **43 lignes d'en-cours MP/AC sur
14 couples article/site** ont été rapprochées du plan du 5 janvier :

| Regroupement de l'Extract par article/site/semaine | AVICDE | ECHCDE | Total |
|---|---:|---:|---:|
| Date G, livraison : quantité exactement retrouvée en H | 26/26 | 9/9 | **35/35** |
| Date I, entrée après traitement : quantité exactement retrouvée en H | 5/28 | 0/9 | **5/37** |

Ces comptes portent sur des groupes hebdomadaires, pas sur des ordres
identifiés. Exemple 001848/Avène : Extract ligne 8, **G = 20 février,
I = 11 mars** ; Flow MRP du 5 janvier, **H88 = 6 000 kg dans la semaine du
16 février**, H91 = 0 dans celle du 9 mars. La même préférence pour G existe
pour les deux libellés AVICDE et ECHCDE dans ce sous-ensemble. Elle ne prouve
pas la convention de toutes les propositions futures.

**Conséquence pour K :** le solde exporté additionne H à cette semaine de
livraison, tandis que J futur est réparti par disponibilité. Il ne faut donc
pas appeler systématiquement K « stock utilisable après traitement ». Son
bilan arithmétique exact ne prouve pas qu'il soit l'indicateur de disponibilité
effectivement utilisé par le calcul industriel. Ce constat ne justifie ni
la suppression de R dans le moteur ni l'ajout d'une deuxième réception.

### Ce que les nouvelles contre-épreuves éliminent

| Version MRP | Semaine repère de la première H de 4 000 kg | Semaine repère reconstruite avec S20 et R13 ouvrés |
|---|---|---|
| 2 février | 18 mai, H4122 | 18 mai |
| 9 février | 4 mai, H5110 | 11 mai |
| 16 février | 13 avril, H6090 | 20 avril |
| 23 février | 6 avril, H7092 | 4 mai |

Pour le 23 février, les sept positions dans la semaine et trois arrondis
hebdomadaires testés donnent **du 4 au 18 mai**, jamais le 6 avril. Dans cette
reconstruction, aucun délai de sécurité constant testé ne reproduit les
quatre dates avec R13. Les
moyennes fixes sur 4/8/13/26 semaines donnent chacune zéro correspondance
exacte sur ces quatre plans ; les fenêtres incomplètes sont exclues du
diagnostic, et non remplies arbitrairement.

Le changement de H6000 vers J6000 ne crée pas non plus l'urgence recherchée :
au 23 février, après anticipation des besoins de 20 jours ouvrés, le solde
minimal avant le J du 2 mars reste **+2 254,44 kg**. Avec la disponibilité au
11 mars de l'Extract, il reste **+1 344,44 kg** et le premier manque anticipé
reste le 26 mai. Exclure complètement ces 6 000 kg provoque une réception
théorique le 5 mars, pas le 6 avril. Les trois passages H→J comparables
d'avril, juin et septembre ne déplacent pas la réception suivante ; celui
d'octobre change aussi sa quantité. Le reclassement seul n'est donc pas une
règle générale d'avancement d'une semaine.

Le regroupement entre matières du même fournisseur n'est pas établi non
plus : dans le plan du 23 février, 001757 et 007923/Avène conservent leurs H
du 13 avril, 029313/Avène celle du 20 avril. Aucune H au 6 avril pour ces
trois matières. Cela n'exclut pas des livraisons communes avec des articles
absents de l'export.

### Ce qui reste compatible, sans cause démontrée

La position **4 000 kg dans la semaine repérée par le 6 avril reste identique
pendant sept versions**, du 23 février au 6 avril inclus. Une réception conservée après engagement est
compatible avec cette stabilité. La fixation explique son maintien éventuel,
**pas l'origine de l'avance** du 13 au 6 avril.

Pour une arrivée physique pendant la semaine du **7 au 13 avril**, la plage
théorique de lancement est le **10–16 février avec 56 jours calendaires**,
ou le **17–23 mars avec 21 jours calendaires**. Au plan du 23 février, une
**nouvelle** commande au fournisseur à 56 jours ne peut donc plus respecter
cette cible, contrairement à celui à 21 jours. Ce calcul explique une
faisabilité conditionnelle du secours ; il ne démontre ni pourquoi cette
semaine a été choisie, ni une date réelle de lancement. Les calculs antérieurs
9 février/16 mars utilisaient le dimanche comme jour représentatif : ce ne
sont pas des dates de commande industrielles retrouvées.
Une proposition de 4 000 kg existe déjà en janvier pour mai, alors que les
deux délais seraient compatibles : quantité et urgence ne sont pas synonymes.

### Mécanismes officiels et conditions d'emploi

- SAP distingue l'affichage d'une date de réception et d'une date de
  disponibilité après traitement. Il peut aussi afficher des besoins
  anticipés par la sécurité. Ces options ne prouvent pas un mélange de
  conventions dans notre export ; le rapprochement G/I ci-dessus les teste
  sur le carnet initial. [Individual Line Display](https://help.sap.com/docs/SAP_ERP_SPV/66326f67e0e1416d83c0fdfa4060189d/7f98b6535fe6b74ce10000000a174cb4.html).
- Le délai de sécurité anticipe les besoins ; un profil supplémentaire peut
  modifier sa valeur selon **la période du besoin**, s'il est effectivement
  paramétré. Aucun profil de ce type n'est fourni ici : conserver S20.
  [Safety Time / Actual Range of Coverage](https://help.sap.com/docs/SAP_ERP_SPV/85d3fce10e264972a0155c8b46ecf93b/8aaace5314894208e10000000a174cb4.html).
- Un lot périodique peut regrouper les besoins et ancrer la disponibilité
  sur le premier besoin ou une borne de période. Il faut connaître la
  période et la convention de date ; une extraction hebdomadaire ne les
  établit pas. [Availability Date for Period Lot-Sizing Procedure](https://help.sap.com/docs/SAP_S4HANA_ON-PREMISE/af9ef57f504840d2b81be8667206d485/ce97b6535fe6b74ce10000000a174cb4.html).
- Une réception déjà fixée peut rester à sa date pendant que le MRP
  recommande une avance ou un report. Distinguer **date conservée,
  recommandation et modification effectivement appliquée**. Le contrôle
  peut chercher une réception fixe existante avant de créer une nouvelle
  proposition. [Rescheduling check](https://help.sap.com/docs/SUPPORT_CONTENT/mrp/3138697863.html).

Le dossier de références décrit aussi revue périodique, profils de fixation,
calcul à rebours/en avant et leurs contre-exemples. Un calcul en avant après
une date de lancement devenue impossible ne justifie pas, à lui seul, une
arrivée avancée de quatre semaines. Aucun calendrier mensuel, délai de gel
universel ou supplément de sécurité n'est déduit du seul cas d'avril.

**Règle commune à conserver :** pour une nouvelle proposition, calculer la
disponibilité requise à partir du besoin protégé, puis l'arrivée physique
après retrait de R, puis le lancement après retrait du délai fournisseur.
Pour du stock déjà reçu, utiliser sa date de libération sans ajouter une
nouvelle livraison. Pour un approvisionnement déjà engagé, examiner sa
couverture et une éventuelle replanification avant un achat supplémentaire.
Les statuts de l'engagement et le calendrier de lotissement manquent pour
attribuer une cause certaine au mouvement du 23 février.

Preuves : [diagnostic H/J](../../artifacts/testing/mrp_mechanisms_20261001/source_diagnosis.json),
[oracle indépendant](../../artifacts/testing/mrp_mechanisms_20261001/independent_diagnosis.json),
[dates du carnet initial](../../artifacts/testing/mrp_mechanisms_20261001/opening_date_semantics.json),
[fournisseurs et stabilité](../../artifacts/testing/mrp_mechanisms_20261001/supplier_calendar_review.json),
[références officielles](../../artifacts/testing/mrp_mechanisms_20261001/reference_review.json),
[validation finale](../../artifacts/testing/mrp_mechanisms_20261001/final_validation.json),
[manifeste](../../artifacts/testing/mrp_mechanisms_20261001/manifest.json).

## Relecture des documents fournis et de la politique de stock — 1er octobre 2026

Périmètre : `001848_1810_exploration_MRP_2025.html`,
`Audit_MRP_001848_1810_2025.xlsx` et le texte d'analyse fournis par
l'utilisateur, confrontés aux classeurs locaux. Les pièces reçues sont
conservées intactes. Cette passe complète la synthèse ci-dessous ; elle
**ne modifie ni le moteur, ni ses paramètres, ni les cartes de simulation**.

### Ce que dit exactement la feuille « Politique de stock MRP »

Dans `Flow_Data_Inventory_and_Replenishment_rules.xlsx`, la feuille contient
**27 politiques article/site**, sans date de validité ni historique des
paramètres. C'est la feuille `Stocks` qui contient les photos successives.
La colonne E est un **délai de sécurité en jours ouvrés** ; F est une
**quantité fixe de sécurité**, exprimée dans l'unité indiquée en colonne G. Ce sont deux données
distinctes.

Pour **001848/1810**, les cellules **E12 = 20**, **F12 = 0**, **G12 = G**
signifient 20 jours ouvrés de protection et aucun plancher fixe renseigné.
**F12 = 0 ne supprime pas la protection temporelle.** Les 13 jours de
traitement à réception viennent de la colonne E, « Temps de réception en
jours », de `Flow_Data_MRP_results`, constante sur les 1 500 lignes de ce
couple ; ils ne viennent pas de F12. R désigne ce délai dans nos formules,
et non une lettre de colonne du classeur.

| Configuration renseignée | Nombre de politiques | Exemples et valeurs normalisées |
|---|---:|---|
| Sécurité en jours, quantité fixe nulle | 21 | 001848/1810 : 20 j ; 055703/1810 : 30 j ; 007923/1810 : 15 j. |
| Sécurité en jours et quantité fixe positive | 4 | 333362/1430 : 10 j et 110 000 UN ; 730384/1430 : 10 j et 23 500 m ; 049371/1810 : 40 j et 888 kg ; 708073/1430 : 10 j et 2 000 kg. |
| Quantité fixe positive, délai nul | 1 | 021081/1450 : 900 000 kg. |
| Les deux valeurs explicitement nulles | 1 | 268091/1920. Cela ne décrit pas à lui seul toutes ses règles de réapprovisionnement. |

Six couples présents dans le Flow MRP n'ont pas de ligne de politique :
001848/1430, 001893/1450, 002612/1450, 007923/1430, 029313/1430 et
693055/1450. **Absent n'est pas égal à zéro**, ni à la valeur d'un autre site.
Les 888 000 G de F26 valent 888 kg ; les 2 000 000 G de F27 valent 2 000 kg.

La feuille ne donne ni la formule de conversion des jours en quantité, ni
la règle d'addition ou de maximum lorsque E et F sont tous deux positifs.
Elle ne prouve donc pas qu'un « stock de sécurité = consommation moyenne
× (20 + 13) » est la règle industrielle de 001848. Le cadre commun reste
le calcul daté du besoin protégé, de l'arrivée physique et du lancement,
avec le calendrier propre à chaque délai. Les conditions et limites des
règles R05 à R09 ci-dessous restent applicables.

La feuille voisine `Taile de Lot` décrit aussi des contraintes distinctes
des politiques de sécurité : 268967/Gien a minimum = maximum = 107 800 ;
268091/Avène a minimum 28 800 et maximum 142 485. Les lots fixes des PFI
Gaillac sont 3 200 000 pour 773474 et 600 000 pour 693055, en valeurs brutes.
Cette feuille n'a pas de colonne d'unité : la conversion doit rester liée
au référentiel article (G pour ces deux PFI), pas devinée à partir du nombre.

### Ce que les pièces reçues permettent de confirmer pour 001848/Avène

La contre-vérification indépendante retrouve exactement les **1 500 lignes
MRP, 52 versions et 53 photos** du classeur fourni. Les sommes de J coïncident
avec la photo du lundi suivant dans **51 plans sur 52**. L'exception reste
le plan du 2 mars : J total 10 774,206 kg contre 11 334,440 kg photographiés
le 3 mars, soit −560,234 kg. Ce J total correspond à la photo du 10 mars ;
cela signale un décalage possible, sans prouver sa cause.

Les cinq épisodes suivants sont cohérents avec une réception physique,
suivie d'une disponibilité ultérieure. Les intervalles viennent des photos,
pas d'un journal de livraisons identifiées.

| Intervalle entre photos 2025 | Approvisionnement probable | Semaine future portant la quantité J dans le plan suivant |
|---|---:|---|
| 17–24 février | 6 000 kg | 2 mars |
| 7–14 avril | 4 000 kg | 20 avril |
| 23–30 juin | 6 000 kg | 6 juillet |
| 1er–8 septembre | 6 000 kg | 14 septembre |
| 13–20 octobre | 6 000 kg | 26 octobre |

Total probable : **28 000 kg**. Sous cette reconstruction des entrées,
`10 262,646 + 28 000 − 7 604,440 = 30 658,206 kg` de sorties nettes sur
la période du 1er janvier au 29 décembre. Ce n'est pas une mesure certifiée
de consommation de fabrication : d'autres mouvements nets restent possibles.
Additionner H des semaines courantes des 52 versions donne **58 000 kg** ;
ce cumul compte aussi des prévisions successives d'un même approvisionnement,
et ne mesure donc pas le tonnage reçu.

**Exemple d'avril :** la photo passe de 7 709,420 kg le 7 avril à
10 987,820 kg le 14 avril. Avec une entrée de 4 000 kg, le mouvement net
sortant reconstruit est 721,600 kg. Au plan du 13 avril, J14156 =
6 987,820 kg dans la semaine courante et J14157 = 4 000 kg dans la semaine
du 20 avril. Leur somme vaut 10 987,820 kg. Les 4 000 kg futurs sont donc
déjà compris dans le stock détenu ; leur passage dans la semaine courante
du plan suivant ne doit pas produire une seconde réception physique.

**Précision de date :** « J courant » signifie affecté à la semaine courante,
pas nécessairement utilisable dès le dimanche du plan ou le lundi de la
photo. Une arrivée entre le 7 et le 14 avril, suivie de 13 jours lundi–vendredi,
donne une disponibilité entre le 24 avril et le 1er mai. La semaine repérée
par le 20 avril contient les 24 et 25 avril : il existe donc des dates
compatibles avec R13. Ce rapprochement hebdomadaire ne prouve ni la date
exacte de livraison, ni celle du contrôle qualité, ni un traitement réel
réduit à sept jours. L'Extract initial fournit séparément le couple
20 février → 11 mars, compatible avec 13 jours ouvrés.

En été, les photos sont constantes à 6 173,320 kg les 28 juillet, 4, 11 et
18 août, tandis que I courant porte 900 kg dans plusieurs plans successifs.
Un besoin non exécuté puis reporté est compatible avec cette signature et
avec la fermeture de début août indiquée par l'utilisateur. Un stock net
constant ne suffit toutefois pas, à lui seul, à exclure des mouvements
compensés. Il ne faut ni certifier trois consommations de 900 kg, ni affirmer
leur absence sans cette réserve.

Les **169 changements de H** recensent des changements de positions de
prévision, et non 169 commandes ; **133** concernent des semaines présentes
dans les deux plans comparés. Les **746 changements de I** sont comparés
sur des semaines communes. La page HTML embarque ces derniers mais ne les
affiche pas dans son interface. Elle est autonome, avec une courbe PNG fixe
et des sélecteurs/tableaux décrits dans le code. **Les interactions n'ont
pas été testées dans un navigateur pendant cette passe.**

### Portée pour les règles et la simulation

L'analyse reçue explique la séparation du stock détenu et de sa disponibilité
en avril. **Elle n'explique pas le motif de l'avancement décidé dans le plan
du 23 février, du 13 au 6 avril.** La chronologie est établie ; la cause reste
ouverte. Elle ne retrouve pas non plus une date certaine de création de la
commande à partir de la seule soustraction du délai fournisseur.

La relecture du moteur et des CSV existants ne montre pas de double ajout
du traitement à réception : R est ajouté une fois pour les achats nouveaux ;
l'en-cours initial de 6 000 kg conserve ses deux dates du 20 février et du
11 mars. Le moteur distingue stock physiquement détenu, indisponible et
libéré. Il ne recopie pas les H industrielles comme de nouveaux achats fermes.
Les J des versions ultérieures ne doivent pas écraser les stocks calculés
d'une simulation autonome ; cela relèverait d'un mode de rejeu historique
distinct, explicitement nommé.

Le run existant consomme zéro pour 001848 pendant les semaines du 27 juillet,
3 août et 10 août : le besoin courant reporté n'est pas automatiquement
consommé trois fois. Ce résultat local ne certifie pas le traitement d'un
besoin réellement nouveau annoncé en cours de semaine. Aucune nouvelle
simulation n'a été exécutée pour cet audit documentaire.

**Provenance :** trois des sept empreintes annoncées dans `Guide_sources`
diffèrent des fichiers locaux actuels : Inventory, Extract_En_cours et
268967. Les quatre autres, dont Flow MRP, correspondent. Les photos et les
cellules de 001848 contrôlées correspondent néanmoins aux sources locales.
Les fichiers ne sont donc pas déclarés identiques octet pour octet sur la
seule foi du classeur fourni ; aucune divergence métier n'a été établie sur
les cellules rapprochées. Les deux jeux d'empreintes figurent dans la preuve.

Preuves de cette passe :
[politique de stock](../../artifacts/testing/mrp_supplied_review_20261001/policy_review.json),
[contre-vérification du classeur](../../artifacts/testing/mrp_supplied_review_20261001/workbook_review.json),
[audit statique du HTML](../../artifacts/testing/mrp_supplied_review_20261001/html_review.json),
[relecture du moteur et du run existant](../../artifacts/testing/mrp_supplied_review_20261001/engine_review.json),
[manifeste agrégé](../../artifacts/testing/mrp_supplied_review_20261001/manifest.json).

## Référence de lecture et règles communes — synthèse du 1er octobre 2026

Cette section rassemble la dernière passe complète. Les sections suivantes
conservent les calculs détaillés et les essais antérieurs. **Le moteur et les
cartes n'ont pas été modifiés pendant cette passe.** Une règle est dite
confirmée lorsqu'elle vient d'une décision utilisateur, d'un paramètre source
ou d'un rapprochement arithmétique contrôlé. Une règle soutenue reste une
hypothèse compatible avec plusieurs cas. Un comportement documenté chez un
éditeur n'identifie pas le logiciel ni les options de l'industriel.

### Ce qui a été vérifié

- **53 398 lignes MRP**, 52 versions, 1 637 plans article/site/version,
  33 couples article/site et **1 646 photos de stock**.
- Les 53 398 récurrences de K sont justes après normalisation des unités.
  **1 236 K sont négatifs** : il s'agit de soldes prévisionnels, pas de stocks
  physiques négatifs constatés.
- Sur **1 615 rapprochements** entre J total et photo du lundi suivant la
  version, **1 131 sont égaux** à 0,00001 unité près. Ce décalage de date est
  explicite ; une égalité n'établit pas l'heure de prise de photo.
- **800 lignes J futures** représentent du stock déjà détenu avec disponibilité
  ultérieure, selon la signification confirmée par l'utilisateur.
- **296 transitions** présentent une signature compatible avec un report de
  besoin courant, dont 22 pour 001848/Avène. Critère : amplitude de la surprise
  de stock >1 unité,
  H de la semaine courante inchangée, puis compensation à 99 % au moins par
  la révision de I courant. Ce sont des signatures, pas 296 OF identifiés.
- Un second calcul indépendant, en fractions exactes, a confirmé les comptes,
  les bilans et l'identité des 296 transitions. Les classeurs sont inchangés.

Les statistiques concernent toutes les données présentes, y compris les
couples hors périmètre physique du simulateur. Les 33 couples ne sont pas
33 achats externes actifs ; le périmètre courant comporte 22 achats actifs.

### Lire correctement les colonnes et les stocks

| Donnée | Sens retenu et contrôle | Conséquence pour le simulateur |
|---|---|---|
| A : version du plan | Date à laquelle le plan est connu | Ne pas utiliser une version future pour une décision passée. |
| G : semaine cible | Repère hebdomadaire, pas date exacte de commande | Les comparaisons de dates doivent conserver cette précision. |
| H : entrées projetées | Réceptions prévues ; achat, fabrication ou transfert selon le flux | Une H n'est ni automatiquement une livraison exécutée, ni un ordre nouvellement créé. |
| I : sorties/besoins projetés | Besoins industriels du périmètre source ; ils peuvent être révisés ou reportés | Ne pas les assimiler systématiquement à une consommation physique de la semaine. |
| J : stock physique réparti par disponibilité | J courant utilisable dans la période ; J futur déjà détenu, utilisable plus tard | Une libération de J futur change l'état du stock, pas le total physiquement reçu. |
| K : stock fin de semaine projeté | `K(t) = K(précédent) + J(t) + H(t) − I(t)` ; zéro initial avant première ligne | Contrôle du plan, pas preuve d'exécution des H et I. |
| Photo « Stock Total » | Quantité détenue au moment de la photo | Une variation est un mouvement net : entrées moins sorties, avec ajustements/transferts possibles. |

Exemples d'écarts persistants J total/photo : **−19 kg pour 002612/Gaillac dans
51 plans**, **−1 500 000 unités pour 042342/Gien dans 42 plans**, **−179,98 kg
pour 001848/Gien dans 30 plans**. Ils suggèrent des stocks hors du périmètre
MRP ou des conventions différentes, sans en prouver le statut. Ils ne doivent
être ni effacés ni transformés en stock disponible par défaut.

### Catalogue des règles et conditions

| Règle | Condition et comportement à conserver/rechercher | État des preuves |
|---|---|---|
| R01 — Périmètre article/site et unités | Calculer par article, site, unité et usage ; normaliser G/KG, UN/ZUN, bases de prix et devises. Une matière partagée ne peut être dimensionnée avec la seule demande d'un PF. | Confirmé par les sources ; allocation exacte des usages encore partielle. |
| R02 — États physiques | Séparer détenu, utilisable, indisponible, réservé et en transit. Un changement d'état ne crée pas une réception supplémentaire. Ne pas assimiler un résidu photo/J à une quantité utilisable. | J futur confirmé ; certains statuts détaillés absents. |
| R03 — Bilan et prévision | Calculer le besoin net daté avec le stock utilisable et les approvisionnements conservés ; réviser la prévision avec la version connue au jour de décision. | Bilans confirmés ; toutes les H ne portent pas de statut d'engagement. |
| R04 — Besoins reportés | Réconcilier le besoin restant de la semaine courante avec ce qui est déjà exécuté ou en attente. Une révision de I ne doit pas produire automatiquement une deuxième consommation. | Soutenu par les 296 signatures ; ordre par ordre non identifié. |
| R05 — Sécurité temporelle | Anticiper les besoins concernés de S jours ouvrés, lundi–vendredi, avant le calcul net des nouvelles propositions. Garder la consommation physique à sa date propre. | S et calendrier confirmés ; mécanisme candidat déjà présent dans le moteur. |
| R06 — Sécurité fixe | Un plancher fixe et une sécurité en jours sont deux paramètres. Leur combinaison doit être explicitée ; le maximum et l'addition ne sont pas équivalents. | Additif mieux soutenu sur 708073, 333362, 730384 ; contre-exemple 049371. Aucune généralisation automatique. |
| R07 — Chaîne de dates | Distinguer lancement, arrivée physique et disponibilité après traitement. Pour une nouvelle proposition : besoin protégé → retrait de R → arrivée, puis retrait du délai fournisseur → lancement. Ne pas compter R deux fois. | FIA et Extract donnent des repères ; calendrier exact de certains R encore candidat. |
| R08 — Engagements et propositions | Recalculer librement une proposition modifiable ; conserver l'identité et la quantité déjà engagées. Une date proposée par le MRP n'est pas nécessairement une date acceptée par le fournisseur. | Mécanisme industriel documenté ; statuts individuels absents des H. |
| R09 — Avancer avant de racheter | Si un approvisionnement prévu couvre la quantité mais arrive après le besoin protégé, étudier son avancement. S'il est non modifiable ou insuffisant, déterminer un complément ou un secours, sans dupliquer la quantité engagée. | Mécanisme documenté et alerte concrète vérifiée ; possibilités réelles d'avancement non fournies. |
| R10 — Quantités de commande | Distinguer standard, lot fixe, minimum, multiple, maximum et regroupement temporel. Appliquer seulement les paramètres dont la signification est établie et dater leur validité. | Lots fixes Gaillac confirmés ; standards FIA présents ; chronologie complète des paramètres absente. |
| R11 — Regroupement | Regrouper les besoins dans une fenêtre commune uniquement si son origine et sa durée sont justifiées ; vérifier le résultat sur d'autres références et versions. | Existence de regroupements soutenue ; pas de fenêtre universelle démontrée. |
| R12 — Fournisseur principal/secours | Pour 001848 : principal moins cher 6 000 kg/56 j, secours 4 000 kg/21 j ; tester le recours au secours lorsque le principal ne peut pas assurer la date protégée selon les engagements et possibilités réelles. | Rôles principal/secours confirmés par l'utilisateur ; déclenchement exact sur la date protégée encore candidat. H seule ne prouve pas le fournisseur choisi. Pas de généralisation sans preuve aux autres matières. |
| R13 — OF et nomenclature | Un OF prévu peut encore générer des besoins ; un OF déjà prélevé ne doit pas consommer une seconde fois. Relier les conversions et les consommations au statut de l'ordre. | BOM et O.Proc présents ; statut de prélèvement incomplet. |
| R14 — Transferts entre sites | Ne partager les stocks que sur une route établie, avec délai et affectation ; distinguer achat externe et transfert interne. | Route 773474 Gaillac→Gien documentée ; mutualisation 001848 non démontrée. |
| R15 — Couverture annuelle du médicament | Suivre la cible utilisateur d'environ un an sur toute la chaîne 268967, en PF équivalents de positions physiques distinctes, affectées au même périmètre de demande. | Objectif confirmé ; allocation amont et demande de référence non réconciliées. Ce n'est pas un an de sécurité à ajouter sur chaque site. |
| R16 — Calendriers et horizon | Conserver un horizon roulant de 52 semaines avec versions connues ; distinguer calendrier de commande, réception, production et libération. La fermeture de début août est confirmée, mais deux ou trois semaines et les opérations concernées restent à préciser. | Principe confirmé ; calendrier détaillé absent. Ne pas ajuster des jours fermés uniquement pour retrouver une date. |

Le délai fournisseur nominal reste celui des sources, conformément au choix
utilisateur d'abandonner pour le moment une loi de retards/avances estimée.
Les quantités physiques en UN restent entières ; les prévisions peuvent être
fractionnaires. La sécurité dépôt conserve 100 % des jours sources.
`tau_process` reste sa convention de planification actuelle, sans ajout d'une
durée physique de fabrication non confirmée.

### Pourquoi une date est avancée : distinguer la cause et l'action

Une date protégée peut avancer parce que les besoins augmentent ou sont
avancés, que le stock utilisable diminue, qu'une réception/libération est
retardée, ou que le calendrier/paramétrage change. Cela ne commande pas à
lui seul la création d'un nouvel achat : l'action dépend des approvisionnements
déjà prévus et de leur possibilité d'être modifiés.

Pour 001848/Avène :

| Révision | Mouvement de la H source | Ce qu'expliquent les besoins et stocks exportés avec S20/R13 |
|---|---|---|
| 2→9 février | 18 mai→4 mai | Une semaine retrouvée, 18→11 mai ; l'autre semaine reste ouverte. |
| 9→16 février | 4 mai→13 avril | Trois semaines retrouvées, 11 mai→20 avril ; décalage absolu d'une semaine conservé. |
| 16→23 février | 13 avril→6 avril | Non expliqué : cette reconstruction donne 20 avril→4 mai. |

Anticiper chaque I avant de déduire les stocks et réceptions a également été
testé, avec deux lectures des H antérieures : déjà disponibles, ou physiques
puis disponibles après R. Les deux donnent encore **4 mai au plan du 23 février**,
pas 6 avril. Le code `plan_anticipated_requirements` anticipe déjà chaque besoin
avant le calcul net ; cette passe n'identifie donc pas un bug d'ordre de calcul
du moteur. L'oracle simplifié des sections précédentes reste un diagnostic
différent dans certains cas de réceptions antérieures tardives.

**Exemple de condition appelant à examiner un avancement d'approvisionnement
avant un nouvel achat :** au plan du 20 avril, H15118 prévoit 6 000 kg au 1er juin.
Avec R13 ouvrés, leur disponibilité est au 18 juin. Un besoin anticipé produit
un manque de **72,378 kg au 9 juin**, ensuite couvert par ces 6 000 kg. Cette
alerte ne prouve pas qu'il faille avancer les **4 000 kg du 31 août** (H15127).
Elle concerne d'abord la date des 6 000 kg, si ces derniers peuvent être
avancés. Le diagnostic compte 38 alertes dont le premier déficit est
quantitativement couvert par des H antérieures encore attendues. Dans 36 cas,
le solde redevient positif à une H ; dans deux cas, une J le rétablit d'abord.
Ce ne sont ni 38 avancements possibles prouvés ni 38 achats supplémentaires
démontrés.

### 001848 à Gien n'explique pas, à ce stade, l'avance à Avène

Les 52 versions et 53 photos de chaque site ont été croisées. Au 23 février,
les H/I de Gien au 6 et au 13 avril sont inchangés : **H6042/H7044 = 7 000 kg,
I6042/I7044 = 2 602 kg ; H6043/H7045 = 0 et I6043/I7045 = 2 116,750 kg**.
Gien ajoute 7 000 kg au 16 mars (H6039/H7041), sans mouvement opposé de
4 000 kg qui expliquerait directement Avène.

La fusion hypothétique des stocks, sans délai de transfert, prédit le 20 avril
au lieu du 6 avril dans le plan du 23 février. Sur 124 H non terminales, son
erreur moyenne est de 13,55 jours contre 8,19 pour le calcul local ; elle ne
valide donc pas un stock commun. Les coïncidences de dates entre sites ne sont
pas plus fortes que des témoins décalés. Cela ne prouve pas qu'aucun transfert
ponctuel n'existe : aucun transfert n'est établi par ces seuls rapprochements.

Les paramètres sont aussi distincts : R13 à Avène, **R26 pour 001848/Gien dans
Flow MRP**, contre R14 dans l'ancien Extract ; aucune sécurité spécifique à
001848/Gien n'est renseignée dans la feuille politique. La BOM 268967 ne
contient pas 001848 : sa consommation Gien ne peut être expliquée par ce seul PF.

### Gaillac, les ordres initiaux et l'objectif d'un an

La route documentée du médicament est
**021081 → 773474 fabriqué à Gaillac → Gien → 268967 → dépôt**.
Gaillac assure donc réception, stockage, fabrication et expédition.
693055 relève de l'autre chaîne et n'est pas ajouté à la couverture du 268967.

L'Extract comporte 53 AVICDE, 29 ECHCDE et 22 O.Proc. Pour Gaillac, les
18 ECHCDE et 5 AVICDE de 021081 totalisent **1 320 000 kg** ; leurs **14
regroupements par semaine de livraison correspondent exactement aux H du
premier plan**. C'est une preuve forte que les H initiales incluent du carnet
existant, pas uniquement de nouvelles décisions MRP. Les deux O.Proc Gaillac
sont 600 kg de 693055 et 3 200 kg de 773474. Ce dernier demanderait
**28 608 kg de 021081** selon la BOM ; le carnet ne prouve pas si la matière
est déjà prélevée. Ne pas ajouter l'OF aux photos, puis consommer encore
automatiquement toute sa matière.

Pour 021081, les 53 photos dépassent le plancher source de 900 000 kg, alors
que J immédiatement utilisable est inférieur à ce niveau dans 50/52 plans.
La part future de J atteint une médiane de **75,22 %**. Ce constat impose de
tester le plancher avec les disponibilités et engagements datés ; il ne prouve
pas un minimum instantané de 900 000 kg utilisables chaque jour.

La conversion théorique des quatre positions physiques distinctes est, après
normalisation des stocks 021081/773474 en **kg** et 268967 en **unités** :

`PF équivalents = stock021081_Gaillac / 0,08631317892`

`                + (stock773474_Gaillac + stock773474_Gien) / 0,009654718`

`                + stock268967_dépôt`

Les coefficients viennent de 8,94 kg de 021081/kg de 773474 et
0,009654718 kg de 773474/PF. Ne pas ajouter les autres composants, les H,
les quantités du carnet ou les J futurs une seconde fois.

En affectant **théoriquement tout** ce stock au PF étudié, on obtient
16,84 millions de PF au 1er janvier et 23,47 millions au 29 décembre.
Cela représenterait 6,66 puis 9,29 années des besoins 2025 du premier plan dépôt,
ou 10,68 puis 14,89 années de la demande du fichier demand_PF. **Ce ne sont
pas des surstocks industriels démontrés.** L'amont et l'aval ne constituent
pas encore un périmètre fermé : le premier plan sort 1 138 452 kg de 021081,
alors que les H de 773474, 64 000 kg, n'en nécessiteraient théoriquement que
572 160 kg. Usages, horizons et affectation doivent être réconciliés avant
d'étalonner l'objectif d'un an. Choisir après coup le dénominateur qui donne
environ un an ne validerait pas cette règle.

### Références industrielles et limites de la conclusion

La recherche a couvert **19 sources officielles SAP, Microsoft et Oracle**,
regroupées en 16 mécanismes. Elles décrivent plusieurs familles de MRP et
leurs options ; elles ne démontrent pas leur fréquence d'utilisation ni le
paramétrage de cet industriel. Les distinctions pertinentes sont notamment :
[besoins anticipés avant calcul net chez SAP](https://help.sap.com/docs/SAP_SUPPLY_CHAIN_MANAGEMENT/5632d7cbffa04b21be22106e9a212038/2f31c95360267614e10000000a174cb4.html),
[avancement/report des ordres existants chez Microsoft](https://learn.microsoft.com/en-us/dynamics365/supply-chain/master-planning/action-messages),
[lot fixe, multiple et couverture regroupée chez Oracle](https://docs.oracle.com/en/cloud/saas/supply-chain-and-manufacturing/25c/faspf/item-attributes-and-order-modifiers-for-supply-planning.html),
[stock bloqué et disponibilité attendue](https://learn.microsoft.com/en-us/dynamics365/supply-chain/inventory/inventory-blocking).

Les règles communes à poursuivre concernent d'abord **les états et engagements**,
puis les paramètres de date et quantité. Il n'est pas justifié d'ajouter une
marge arbitraire pour retrouver le 6 avril, de décréter un gel de 56 jours, ou
de fusionner les deux sites de 001848. L'épisode du 23 février reste ouvert.

Ordre de qualification pour la suite : (1) état disponible/indisponible et
périmètre comparable ; (2) besoin courant restant et reports sans double
consommation ; (3) maintien/avancement des approvisionnements prévus avant tout
complément ; (4) paramètres de lotissement et leur validité ; (5) allocation
de la chaîne du médicament. Chaque mécanisme doit être testé séparément,
puis sur d'autres matières, avant une simulation complète de cinq ans et une
nouvelle carte. Les anciens calculs ne deviennent pas des validations de ces
changements futurs.

Preuves de cette passe : [audit de tous les flux et photos](../../artifacts/testing/mrp_final_synthesis_20261001/flow_stock_audit.json),
[oracle indépendant](../../artifacts/testing/mrp_final_synthesis_20261001/validation.json),
[001848 deux sites](../../artifacts/testing/mrp_final_synthesis_20261001/multisite.json),
[ordre d'anticipation et engagements](../../artifacts/testing/mrp_final_synthesis_20261001/netting_sequence.json),
[Gaillac et couverture du médicament](../../artifacts/testing/mrp_final_synthesis_20261001/gaillac.json),
[catalogue des références industrielles](../../artifacts/testing/mrp_final_synthesis_20261001/mrp_reference_research.json).

## Hypothèse utilisateur : couvrir sécurité + traitement à réception

Pour 001848, S20 + R13 représente **33 jours ouvrés candidats de couverture**,
à convertir en une quantité par les besoins. Des jours seuls ne définissent
pas un stock en kg. Le délai fournisseur intervient ensuite pour déterminer
le lancement ; il n'est pas ajouté ici à une seconde anticipation de réception.

Deux interprétations ont été contrôlées, sans modification du simulateur :

1. **Besoins datés sur S+R jours.** Le contrôle quotidien indépendant conserve
   les J et H antérieures, examine chaque préfixe des besoins nets et ne retire
   pas R une seconde fois. Sur les 176 H de 001848, il donne les mêmes semaines
   que le calcul daté S puis R, en bornant de la même façon les dates déjà
   passées au jour de décision. Il s'agit d'une reformulation de la couverture,
   pas d'une nouvelle explication des avances. Les sept cas où cette borne
   intervient ne constituent pas une amélioration spécifique à S+R.
2. **Moyenne prévisionnelle × (S+R).** Calcul en jours ouvrés :
   `Q = somme des besoins de W semaines / (5 × W) × (S + R)`.
   Le franchissement de Q donne directement la réception à viser, **sans
   retrancher R ensuite**. Fenêtres fixes et roulantes de 4, 8, 13, 26 et
   52 semaines testées ; aucune extension de prévision pour compléter une
   fenêtre roulante manquante. Les H précédentes sont conservées, et la
   recherche d'un nouveau franchissement commence après la précédente H.

| Plan 001848 | H source étudiée | Couverture datée de 33 jours |
|---|---|---|
| 2 février | 18 mai | 18 mai |
| 9 février | 4 mai | 11 mai |
| 16 février | 13 avril | 20 avril |
| 23 février | 6 avril | 4 mai |

Pour les moyennes, la fenêtre roulante de huit semaines est la meilleure parmi
les fenêtres donnant une date pour tous les cas d'apprentissage de 001848
janvier–juin. Elle est ensuite conservée pour les autres matières et le second
semestre, sans choisir une fenêtre différente par article.

| Article / site | H non terminales comparables | Erreur moyenne, besoins datés S puis R | Erreur moyenne, moyenne prévisionnelle × (S+R) |
|---|---:|---:|---:|
| 001848 / Avène | 124 | **8,19 jours** | 11,23 jours |
| 029313 / Avène | 151 | **3,80 jours** | 5,42 jours |
| 039668 / Avène | 81 | **5,01 jours** | 6,74 jours |
| 055703 / Avène | 189 | **6,44 jours** | 9,37 jours |

Sur 001848 juillet–décembre, hors sélection de fenêtre, l'erreur passe de
8,48 à 10,08 jours. Des épisodes isolés sont mieux expliqués, par exemple
039668 dans le plan du 19 janvier : réception source du 6 avril, ancienne
prédiction au 30 mars, nouvelle au 6 avril. Mais le plan du 5 janvier de cette
même matière se dégrade : réception source du 13 avril, ancienne prédiction
au 6 avril, nouvelle au 30 mars. Ces exemples ne justifient pas une promotion.

734545 a également été testé : la moyenne roulante ne produit aucune date
pour 10 des 335 H non terminales, faute de franchissement dans les fenêtres
futures complètes disponibles. Ses scores sur 325 cas ne doivent pas être
comparés directement au score daté sur 335 comme une amélioration globale.

Au 23 février de 001848, aucune moyenne testée ne retrouve le 6 avril. La
moyenne fixe de quatre semaines produit même un seuil de 5 082 kg, supérieur
au disponible de 4 784,440 kg dès la semaine courante, avant la libération des
6 000 kg en J au 2 mars. Cette alerte immédiate illustre la limite d'un seuil
brut ; elle ne prouve pas qu'un nouvel achat soit nécessaire. Les J futurs
sont bien conservés dans le calcul.

Les scores portent sur des propositions répétées dans les versions MRP,
avec les approvisionnements précédents fournis par la source. Ils ne sont ni
des retards fournisseurs mesurés ni une simulation autonome de toutes les
commandes. Les semaines absentes sont des mouvements non exportés, pas une
preuve de besoins industriels nuls. Le calendrier lundi–vendredi et R ouvré
restent les conventions testées ; aucun jour férié supplémentaire n'a été inféré.

Preuves : [calcul et transfert entre matières](../../artifacts/testing/mrp_001848_rule_search_20261001/combined_horizon.json),
[oracle indépendant 001848](../../artifacts/testing/mrp_001848_rule_search_20261001/oracle/combined_safety.json).

## Comparateurs avec peu de hausses de stock — 1er octobre 2026

Recherche source, sans modification ni nouvelle exécution du simulateur. Les
quatre couples suivants sont effectivement représentés dans le modèle et ont
chacun 53 photos de stock. Cela ne signifie pas que leur calibration soit déjà
bonne. Une hausse entre photos est un mouvement **net**, pas le décompte des
livraisons : une réception peut être masquée par une consommation simultanée.

| Article / site | Hausses entre photos 2025 | Sécurité source, jours ouvrés | Stock fixe source | Traitement réception source | Délai fournisseur FIA, jours | Quantité standard FIA |
|---|---:|---:|---:|---:|---:|---:|
| 039668 / Avène | 4 significatives + 0,03 kg | 7 | 0 | 1 | 35 | 450 kg |
| 029313 / Avène | 7 | 7 | 0 | 1 | 56 | 300 kg |
| 708073 / Gien | 3 | 10 | 2 000 kg | 5 | 28 | 5 000 kg |
| 734545 / Gien | 6 | 10 | 0 | 1 | 21 | 6 300 unités |

039668 et 029313 permettent une comparaison à sécurité et traitement identiques,
avec des délais fournisseur différents ; leurs besoins et quantités restent
différents. 708073 isole un cas de protection fixe et temporelle. 734545 contrôle
les unités physiques, mais son fournisseur dans le carnet initial diffère de
la FIA : ce n'est pas le premier cas à utiliser pour identifier le sourcing.
344135 est écarté de cette sélection : seulement trois photos, malgré son
apparente absence de hausse. 021081 présente sept hausses mais 24 H dans les
semaines courantes des plans ; il n'est donc pas un cas simple de réception.

### Ce que soutiennent les dates, et ce que leur précision interdit de conclure

L'oracle conserve les J et les H précédant celle étudiée, puis cherche le
premier besoin non couvert, ou le passage sous la quantité fixe lorsqu'elle
existe. Il anticipe de S jours ouvrés puis de R jours ouvrés candidats. C'est
une explication d'une réception avec les précédentes fournies par la source,
**pas une simulation autonome**. Pour 708073, anticiper le passage sous le
plancher fixe est lui-même une hypothèse de combinaison des deux protections.

| Article | H non terminales, répétées entre versions | Semaine exacte, besoin placé au dimanche | Compatible avec un jour inconnu dans la semaine du besoin |
|---|---:|---:|---:|
| 039668 | 81 | 24 | 75 |
| 029313 | 151 | 69 | 149 |
| 708073 | 189 | 137 | 138 |
| 734545 | 335 | 53 | 307 |

Le dernier chiffre est une compatibilité d'intervalle, **pas un jour ajusté**
pour reproduire chaque réception. Il considère les sept jours à partir du
dimanche porté dans l'export ; ce sens de l'étiquette hebdomadaire reste une
convention candidate. Une étiquette de fin de semaine donnerait d'autres
comptes et ne permettrait pas de revendiquer ces compatibilités. Exemple
039668, plan du 5 janvier : H398
prévoit 300 kg le 13 avril ; le premier besoin non couvert est dans la semaine
du 20 avril, I399. Avec S7 + R1 ouvrés, placer arbitrairement ce besoin au
dimanche donne la semaine du 6 avril. Le placer plus tard dans sa semaine peut
donner celle du 13 avril. Cet écart ne justifie donc pas de retirer la sécurité.

Sur 708073, le plan du 5 janvier place 10 000 kg en H856, semaine du 30 mars.
Le passage sous les 2 000 kg intervient dans la semaine du 20 avril (I859) dans
ce calcul sans la H étudiée ni les suivantes. L'anticipation S10 + R5 retrouve
la semaine du 30 mars. Sur les 189 H non terminales, l'erreur absolue moyenne
est de 2,41 jours, contre 9,33 jours sans R et 16,33 jours sans S. La quantité
fixe, les entrées conservées et les hypothèses de calendrier doivent rester
explicites ; ce score ne prouve pas à lui seul la règle industrielle.

**Résultat nouveau : combinaison des protections fixe et temporelle.** Pour
708073, sans la H856 du 30 mars ni les suivantes, le solde au 20 avril est
**262,155718 kg**, inférieur au plancher de 2 000 kg ; il devient négatif au
11 mai, à **−614,069632 kg**. Anticiper le franchissement des 2 000 kg de S10,
puis de R5, donne la semaine du **30 mars**, comme la source. Protéger séparément
le plancher fixe et les besoins temporels, puis prendre la protection la plus
forte, donne ici la semaine du **13 avril**.

Le moteur candidat `plan_anticipated_requirements` utilise une enveloppe
`max(besoins cumulés anticipés, besoins cumulés physiques + stock fixe)`.
L'hypothèse additive utilise un plancher fixe en plus de la couverture
temporelle. La comparaison indépendante suivante porte sur des diagnostics
hebdomadaires avec H précédentes sources, **pas sur une exécution de ce moteur**.
Les nouvelles positions sont celles dont la paire semaine/quantité n'existait
pas dans le plan précédent ; elles ne prouvent pas la création d'un ordre.

| Article / site | Positions non terminales nouvelles ou modifiées | Erreur moyenne additive | Erreur moyenne protections séparées MAX |
|---|---:|---:|---:|
| 708073 / Gien | 91 | **2,31 jours** | 13,85 jours |
| 333362 / Gien | 287 | **15,02 jours** | 17,98 jours |
| 730384 / Gien | 83 | **6,75 jours** | 13,83 jours |
| 049371 / Avène | 67 | 31,45 jours | **28,52 jours** |

Pour 708073, l'avantage existe au premier comme au second semestre :
2,76 contre 13,82 jours sur 38 positions, puis 1,98 contre 13,87 jours sur
53 positions. Sur toutes ses 189 H non terminales, l'additif retrouve 137
semaines exactes, contre 13 pour MAX. Mais **049371 est un contre-exemple** :
ces résultats ne justifient pas d'imposer l'addition partout. Prochaine
vérification métier : comprendre cet écart à besoins, plancher fixe, calendrier
et engagements identiques, avant toute modification du nominal. Cette piste
ne résout pas directement 001848, dont la quantité fixe de sécurité est nulle.

Le délai fournisseur sert ensuite à calculer la **date limite de lancement** :
`réception physique visée − délai fournisseur`. Il ne faut pas le retrancher
une deuxième fois de la réception déjà anticipée par sécurité et traitement.
À réception visée identique, 56 jours imposent un lancement 21 jours plus tôt
que 35 jours. Les fichiers ne certifient pas ces dates de création de commande.

### Les quantités de planification ne sont pas constantes sur toute l'année

Les propositions non terminales montrent des changements groupés entre versions :

- **039668** : 300 kg dans les premiers plans, puis 450 kg à partir du plan du
  **30 mars** (H398 au 5 janvier ; H12443 et H12456 au 30 mars). Des exceptions
  de 250 kg et 399,85 kg apparaissent ensuite en semaine courante.
- **734545** : 6 400 unités dans les premiers plans, puis 6 300 à partir du
  **25 mai** (H900 ; H20997 et H21004).
- **708073** : 10 000 kg, soit deux standards FIA actuels, dans les projections
  initiales ; 5 000 kg pour les futures réceptions de 2026 à partir du plan du
  **7 décembre** (H856 ; H50046 et H50050).
- **029313** : 149 des 151 H non terminales valent 300 kg ; les deux autres
  valent 299,8 et 400 kg. Les répétitions entre plans ne sont pas des commandes
  indépendantes.

Ces constats sont compatibles avec une évolution des règles de lotissement,
des engagements ou des ajustements de quantités ; ils ne prouvent pas une
modification précise du paramétrage ERP. Appliquer la quantité FIA unique à
toute l'année ne suffit donc pas à expliquer toutes les propositions. Ne pas
créer des exceptions par article pour recopier cette chronologie. La règle
commune à rechercher doit distinguer **quantité standard, multiple de commande,
proposition ajustable et approvisionnement déjà engagé**.

### Retour sur 001848 : les moyennes ne résolvent pas le 23 février

L'oracle indépendant a testé des sécurités quantitatives calculées sur 4, 8,
13, 26 et 52 semaines de besoins prévisionnels, ainsi que des moyennes roulantes
dont la fenêtre reste dans l'horizon exporté. Au 23 février, les cinq seuils
fixes sont respectivement 3 080 ; 2 625 ; 2 464,62 ; 2 344,62 ; 1 548,46 kg.
Ils donnent des réceptions en mai, **aucune au 6 avril**. Les variantes
roulantes ne retrouvent pas non plus cette date.

Sur les 124 H non terminales, la règle datée S20 + R13 reste à 8,19 jours
d'erreur moyenne ; la moyenne roulante de quatre semaines, en recherchant le
prochain franchissement après la H antérieure conservée, est à 8,92 jours.
La moyenne fixe de 26 semaines est à 13,04 jours. Les semaines absentes ne
certifient pas des besoins industriels nuls. Le cas du 23 février reste donc
**non expliqué**, plutôt que résolu par une nouvelle moyenne arbitraire.

La documentation industrielle confirme que sécurité temporelle et sécurité
quantitative calculée sur une moyenne sont deux mécanismes distincts, et que
l'affichage peut distinguer réception physique et disponibilité. C'est une
source d'hypothèses, pas la preuve que l'entreprise utilise ce logiciel ou ces
options : [SAP, sécurité temporelle](https://help.sap.com/docs/PRODUCT_ID/fe39e10a9a864a8f8dc9537704f0fa13/8aaace5314894208e10000000a174cb4.html),
[SAP, couvertures](https://help.sap.com/docs/SAP_ERP/85d3fce10e264972a0155c8b46ecf93b/87aace5314894208e10000000a174cb4.html?version=6.06.latest),
[SAP, affichage des dates](https://help.sap.com/docs/SAP_ERP_SPV/66326f67e0e1416d83c0fdfa4060189d/7f98b6535fe6b74ce10000000a174cb4.html).

Preuves : [sélection des cas](../../artifacts/testing/mrp_001848_rule_search_20261001/study/forecast_crosscheck_candidates.json),
[comparaison des dates et quantités](../../artifacts/testing/mrp_001848_rule_search_20261001/sparse_receipt_transfer.json),
[oracle indépendant des cas peu fréquents et des protections fixes](../../artifacts/testing/mrp_001848_rule_search_20261001/study/sparse_independent_check.json),
[oracle des moyennes 001848](../../artifacts/testing/mrp_001848_rule_search_20261001/oracle/forecast_safety.json).

## Recherche quantitative d'une règle commune : 52 versions et quatre matières

Étude `mrp_001848_rule_search_20261001`, sans modification du simulateur. Les
52 versions de 001848/Avène servent à tester explicitement des règles, avec
contrôle indépendant. Trois autres matières, **001757, 055703 et 039668 à Avène**,
servent à vérifier le transfert. Le choix parmi 16 conventions de dates est
effectué sur les versions janvier–juin de 001848 uniquement ; juillet–décembre
et les autres matières ne servent pas à choisir cette convention.

**Correction des diagnostics précédents :** une semaine sans ligne doit quand
même être examinée pour rechercher le passage sous la couverture. Les tableaux
historiques ci-dessous qui recherchaient ce passage seulement aux dates exportées
ne donnent pas toujours le premier franchissement. Exemple du plan du 16 février :
au **11 mai**, semaine absente de l'export, le solde reporté est **5 164,640 kg**,
pour **5 470 kg** de besoins renseignés dans les quatre semaines suivantes.
Le franchissement est donc déjà là dans la reconstruction de l'export, et non
au 18 mai. Une absence de ligne n'est pas une preuve de consommation réelle nulle.

### Règle candidate soutenue par les comparaisons

1. Recalculer le besoin restant à partir du stock disponible et des quantités
   déjà présentes mais disponibles plus tard, sans les compter deux fois.
2. Conserver les réceptions déjà engagées à leur date de disponibilité. Dans
   l'oracle source, pour étudier une H, retenir les H précédentes et les J ;
   la H étudiée et les suivantes sont les propositions à expliquer. Cette
   convention ne prouve pas le statut ferme des H retenues.
3. Parcourir **toutes les semaines** et tester la couverture des besoins futurs,
   en tenant compte des réceptions retenues qui deviennent disponibles avant ces
   besoins. Vérifier chaque sous-période pour qu'une réception tardive ne masque
   pas un manque antérieur. Pour 001848, la protection utilise 20 jours ouvrés.
4. Remonter le traitement à réception : **13 jours ouvrés candidats** pour 001848.
   Les calculs sont ramenés aux semaines du fichier ; ils ne sont pas des dates
   exactes de réception. La convention initiale lundi–vendredi n'ajoute pas de
   calendrier de fermeture ou jours fériés non établi.
5. Remonter ensuite le délai fournisseur pour obtenir la date limite de
   **commande**, et évaluer principal/secours à cette échéance. Ce dernier point
   utilise les délais FIA ; les exports H ne valident pas les dates réelles
   d'émission ni l'identité fournisseur de chaque approvisionnement.

Précision : la couverture nette du point 3 n'est pas le seul stock physique
divisé par la consommation moyenne. Elle examine le stock disponible **et les
réceptions retenues** face aux besoins datés. Si B(t) est le solde au jour t,
N(t) est le maximum positif des besoins cumulés moins réceptions retenues sur
chaque préfixe des 20 jours ouvrés suivants ; l'alerte est **B(t) < N(t)**.
Cette formulation est équivalente, dans la reconstruction source, à anticiper
le premier besoin net non couvert de la sécurité source, puis du traitement de
réception. Elle ne consiste pas à attendre une rupture pour décider.

Les deux formulations donnent les mêmes dates sur les **176 H de 001848**.
C'est une équivalence arithmétique, pas 176 preuves industrielles supplémentaires.
Les variantes de couverture brute sans netting des réceptions futures retenues
peuvent créer de faux signaux et ne sont pas utilisées comme règle retenue.

### Résultats et limites

L'oracle retient les **réceptions sources précédentes** pour prédire celle qui
est étudiée : il mesure une explication étape par étape, **pas une simulation
autonome reconstituant toutes les commandes**. Les occurrences se répètent entre
versions et ne sont pas des commandes indépendantes. Les derniers compléments
de chaque plan sont exclus du tableau suivant pour ne pas gonfler l'accord.

| Matière | Occurrences non terminales | Semaine exacte | À une semaine près | Écart absolu moyen |
|---|---:|---:|---:|---:|
| 001848 | 124 | 53 | 86 | 8,19 jours |
| 001757 | 597 | 112 | 404 | 10,22 jours |
| 055703 | 189 | 79 | 158 | 6,44 jours |
| 039668 | 81 | 24 | 80 | 5,01 jours |

Sur le second semestre de 001848, non utilisé pour sélectionner la convention :
**25/66 semaines exactes**, **50/66 à une semaine près**, erreur moyenne 8,48 jours.
Pour les H non terminales de 001848 **strictement à plus de 56 jours** de leur
version, l'oracle indépendant trouve **43/69 exactes, 65/69 à une semaine près**,
erreur moyenne **3,25 jours**. Ce sous-ensemble descriptif ne prouve pas un seuil
de gel de 56 jours ; le score global ci-dessus reste indispensable.

Pour l'approvisionnement devenu celui d'avril :

| Versions | Semaine source | Semaine calculée par la règle |
|---|---|---|
| 5 janvier au 2 février | 18 mai | **18 mai** |
| 9 février | 4 mai | 11 mai |
| 16 février | 13 avril | 20 avril |
| 23 février | 6 avril | **4 mai** |
| 2, 9 et 16 mars | 6 avril | 13 avril |
| 23 et 30 mars, 6 avril | 6 avril | 20 avril |

La règle retrouve exactement le début de la chronologie, puis laisse des écarts,
notamment **28 jours au 23 février**. Ni un arrondi hebdomadaire ni l'égalité
fortuite 16 février + 56 jours = 13 avril ne résolvent cette exception. Il serait
incorrect de présenter le calcul comme l'ERP industriel entièrement identifié.

### Zoom sur le passage du plan du 2 au 9 février : 18 mai vers 4 mai

Pour 001848/Avène, la H de 4 000 kg passe de H4122 (18 mai) à H5110 (4 mai).
La réception précédente de 6 000 kg reste au 16 février (H4109/H5099).
Le stock net après les besoins de la semaine du 9 février est presque identique :
ancien plan `6 985,640 − 930 − 180 = 5 875,640 kg`, nouveau plan
`6 955,610 − 1 080 = 5 875,610 kg`. Les cellules sont J4107/I4107/I4108 et
J5098/I5098. Le besoin courant augmente de 900 kg, mais le stock repris dépasse
de 899,970 kg ce qu'attendait l'ancien plan à cette date : il ne faut pas
interpréter les 900 kg isolément comme un surcroît net de demande.

Pour diagnostiquer la date à assurer, conserver les J et la H précédente de
6 000 kg ; retirer uniquement la H de 4 000 kg étudiée et les propositions
ultérieures. Parcourir toutes les semaines, y compris sans ligne exportée.

| Version du plan | Premier passage sous la couverture des 20 jours ouvrés | Solde projeté à cette date | Besoins exportés des quatre semaines suivantes | Réception calculée en remontant R13 ouvrés | H source |
|---|---|---:|---:|---|---|
| 2 février | 8 juin | 1 205,640 kg | 1 870 kg | semaine du 18 mai | 18 mai |
| 9 février | 1er juin | 2 405,610 kg | 2 530 kg | semaine du 11 mai | 4 mai |

Le 8 juin n'a pas de ligne dans l'ancien plan : le solde est reporté depuis
K4123, calculé ici sans la H4122. Les 1 870 kg viennent de I4124/I4125/I4126 :
60 + 910 + 900. Pour le nouveau plan, le 1er juin correspond à la ligne 5112 ;
la couverture est 1 800 + 10 + 720 kg (I5113/I5114/I5115). Les semaines
absentes ne prouvent pas une consommation industrielle nulle : c'est la
reconstruction des mouvements exportés.

Au 29 juin, sans les propositions étudiées, les soldes deviennent 235,640 kg
dans l'ancien plan et −124,390 kg dans le nouveau. L'écart de 360,030 kg
correspond à 360 kg de besoins supplémentaires cumulés après le 9 février et
à 0,030 kg de différence de stock net. Les besoins sont aussi redistribués
dans le temps, notamment autour de mai et juin.

**Conclusion limitée :** les révisions de besoins expliquent une semaine
d'anticipation avec la règle S20/R13. La source anticipe de deux semaines :
la semaine supplémentaire, du 11 au 4 mai, reste non expliquée par cette règle.
Ni une variation de délai fournisseur ni une date effective de lancement
de commande ne sont démontrées par ces deux plans.

### Zoom sur le passage du plan du 9 au 16 février : 4 mai vers 13 avril

Même diagnostic, avec les 6 000 kg du 16 février conservés et les 4 000 kg
étudiés ainsi que les propositions suivantes exclus du calcul du besoin net.
La H étudiée passe de H5110 (4 mai) à H6090 (13 avril), toujours pour 4 000 kg.

Au **11 mai**, date à examiner même sans ligne exportée dans ces deux plans :

| | Plan du 9 février | Plan du 16 février |
|---|---:|---:|
| Solde projeté sans les propositions étudiées | 5 545,610 kg | 5 164,640 kg |
| Besoins des quatre semaines suivantes | 4 940 kg | 5 470 kg |
| Marge par rapport à cette couverture | +605,610 kg | **−305,360 kg** |

Le nouveau plan franchit donc déjà le seuil de couverture au **11 mai**,
contre le **1er juin** dans l'ancien : trois semaines plus tôt. Le stock projeté
au 11 mai baisse de 380,970 kg et les besoins des quatre semaines suivantes
augmentent de 530 kg. En détail : 2 570 → 2 190 kg au 18 mai (I5111/I6094),
aucune ligne → 10 kg au 25 mai (I6095), 570 kg inchangés au 1er juin
(I5112/I6096), **1 800 → 2 700 kg au 8 juin** (I5113/I6097).

Cette baisse de couverture n'est pas une baisse du stock net de départ :
après les besoins du 16 février et la réception conservée de 6 000 kg,
l'ancien plan donne 11 515,610 kg (K5099), le nouveau 11 874,640 kg (K6082),
soit **359,030 kg de plus**. Les besoins cumulés du 23 février au 4 mai
augmentent toutefois de 740 kg, expliquant la baisse nette projetée de
380,970 kg au 11 mai.

En remontant R13 ouvrés depuis les semaines de franchissement, la règle donne
les semaines du **11 mai puis du 20 avril**, tandis que les H sources sont
au **4 mai puis au 13 avril**. Le **déplacement de trois semaines** est donc
retrouvé ; il reste le **même décalage absolu d'une semaine** dans les deux
plans. Cela explique le mouvement sans prétendre expliquer les dates exactes
ni attribuer une date réelle de commande ou un fournisseur à cette H.

Un mécanisme complémentaire de maintien des approvisionnements est soutenu :
sur **48 positions H** encore futures dans le plan suivant et à au plus 56 jours,
**45 conservent date et quantité**. Cela motive de distinguer engagements et
propositions modifiables ; cela ne permet pas de déclarer un gel automatique
universel à 56 jours. La date d'avril, stabilisée sur sept versions, est compatible
avec ce maintien, sans identifier la décision initiale du 23 février.

Autre piste concrète : réconcilier les besoins reportés de la semaine courante.
Du plan du 9 au 16 mars, le stock repris dépasse l'ancien solde attendu de
**718,744 kg**, tandis que le besoin courant augmente de **720 kg**. Les soldes
de fin de semaine restent à **1,256 kg** près. Cela est compatible avec des
besoins non exécutés reportés, pas nécessairement une demande supplémentaire.
Le gel actuel de la semaine courante du moteur doit être vérifié sur le besoin
restant **de planification**, sans ajouter de consommation ni doubler les arriérés.

Les propositions terminales restent des compléments nets dans les exports ;
leur arrondi comme s'il s'agissait déjà de commandes physiques est une autre
convention à tester. Aucun changement du nominal ni nouvelle simulation n'est
effectué dans cette recherche. Sources inchangées et preuves indépendantes :
[résultats inter-matières](../../artifacts/testing/mrp_001848_rule_search_20261001/candidate_scores_dense.json),
[oracle 001848](../../artifacts/testing/mrp_001848_rule_search_20261001/oracle/rule_search.json),
[manifeste de recherche](../../artifacts/testing/mrp_001848_rule_search_20261001/manifest.json).

### Sécurité en jours, quantité protégée et demande prévisionnelle

Les **20 jours ouvrés** de 001848 peuvent être traduits en une quantité variable
de besoins à protéger. Le stock fixe source vaut zéro ; cela n'annule pas la
sécurité temporelle. Deux conventions doivent rester distinctes : somme des
besoins datés sur les 20 prochains jours, ou 20 fois une demande journalière
moyenne sur une fenêtre définie. La recherche ci-dessus teste surtout les
besoins datés ; elle n'établit pas la fenêtre moyenne utilisée par l'ERP.

Les I des plans Flow sont déjà des **prévisions de besoins matière**, et non
des consommations exécutées. Ils ont été examinés dans leurs versions successives.
Le fichier `demand_PF.xlsx`, feuille `Demande`, porte aussi 52 valeurs de prévision
pour le PF 268091, total **3 576 442 UN**. Avec `268091.xlsx!BOM!A3:F3`
(1 218 g de 001848 pour 1 000 PF), cela représente **4 356,106356 kg** théoriques
de matière, hors effets de stocks PF, calendrier de fabrication et pertes.
Le plan source du 5 janvier porte **19 414,006 kg** de besoins de 001848 : il
ne faut pas remplacer ce besoin industriel par la seule conversion du PF étudié,
ni attribuer tout l'écart à une règle MRP. Le périmètre des autres usages et les
conventions de production comptent. Les colonnes `forecast_demand` et `real demand`
sont identiques pour ces 52 valeurs : ce fichier ne mesure pas leur erreur de
prévision indépendamment.

Le constructeur du simulateur répartit ces 52 pas par semaines depuis J0 du
scénario ; l'onglet Overview (11 juin / Day / 11 pas) ne date pas la série utilisée.
Dans les calculs avec `--mrp-forecast-source source`, la planification prend
d'abord les sorties PF du MRP industriel au dépôt, avec cette série en repli.
Après nomenclature, le rapprochement des composants ajoute seulement le manque
entre besoins propres et total matière industriel ; il ne somme pas deux fois
les deux prévisions. La demande physique client garde la série `demand_PF`.
Ce mélange de périmètres doit rester explicite lors de toute calibration.

## Enquête ciblée : origine de l'avance au 6 avril dans le plan du 23 février

Cette enquête cherche la **décision initiale d'avance**, pas le maintien de la
date ensuite. Dix classeurs métier ont été lus, dont l'ancien extract de
paramètres, les deux Flow, `Extract_En_cours`, les trois classeurs produits,
`Data_poc`, `demand_PF` et `Fournisseur`. Aucun paramètre supplémentaire, date de
création/confirmation de cette commande, statut de gel ou modification de règle
datée du 23 février n'a été trouvé. Les deux Flow ne contiennent pas de formule
Excel ni de requête externe permettant de lire l'algorithme source.

Les paramètres restent **20 jours ouvrés de sécurité, zéro stock fixe**, dans
l'ancien et le nouveau fichier de politique. Le temps de réception reste
**13 jours**. Les offres connues restent 21 jours / 4 000 kg / 4,20 € et
56 jours / 6 000 kg / 1,58 €. `Extract_En_cours!8` documente la commande initiale
de 6 000 kg d'Avène, pas celle de 4 000 kg d'avril. La ligne 7 concerne Gien.

Contrefactuels indépendants, alignés au 23 février et calculés avec la règle
candidate de couverture nette continue puis 13 jours ouvrés de réception :

| Changement isolé | Semaine de réception calculée |
|---|---|
| Besoins et état du plan du 16 février, reportés au 23 février | 20 avril |
| Seulement le stock corrigé de −0,200 kg | 20 avril |
| Seulement les 6 000 kg disponibles au 2 mars plutôt qu'immédiatement | 20 avril |
| Seulement les besoins révisés du plan du 23 février | **4 mai** |
| Ensemble des changements du plan du 23 février | **4 mai** |
| Même plan, 6 000 kg disponibles au 11 mars selon l'extract initial | **4 mai** |
| Date effectivement inscrite dans H du plan du 23 février | **6 avril** |

Le stock comparable avant les besoins du 23 février est de 5 874,640 kg dans
l'ancien plan, contre 5 874,440 kg dans le nouveau, hors les 6 000 kg distingués.
Les modifications visibles retardent la date calculée ; elles ne produisent pas
l'avance demandée. Ce résultat réfute **cette explication par notre règle**,
pas toute règle ERP possible. Il ne faut pas présenter une décision fournisseur,
un arbitrage manuel ou un gel comme des faits établis.

Le contrôle supplémentaire de réception physique confirme que conserver
**13 avril → disponibilité 30 avril** (ou **14 avril → 1er mai**), avec les
13 jours lundi–vendredi sans jours fériés, protège les besoins de mai du plan du
23 février. La date du 6 avril n'est donc pas rendue nécessaire par ces seuls
paramètres. Cette vérification reste un contrefactuel, pas une exécution réelle.

Deux contrôles de contexte n'apportent pas non plus de déclencheur établi :
plusieurs autres réceptions d'Avène restent prévues au 13 avril, donc pas de
déplacement général de ce créneau ; Gien prévoyait déjà 7 000 kg du même article
au 6 avril dans la version du 16 février, et conserve cette date le 23 février.
Une consolidation de transport n'est ni démontrée ni ajoutée au modèle.

**Conclusion : la cause exacte du choix du 6 avril n'est pas identifiée.**
La distinction engagement/proposition explique potentiellement la stabilité
ultérieure, mais ne répond pas à la décision du 23 février. Pour l'attribuer,
il faut soit établir une autre règle sur les données, soit disposer du détail
de l'élément d'approvisionnement (identité, dates demandée et confirmée, statut,
ou message de replanification). Aucun changement du moteur ne force cette date.

[Contrefactuels indépendants](../../artifacts/testing/mrp_001848_rule_search_20261001/oracle/feb23_causality.json),
[inventaire des dix classeurs](../../artifacts/testing/mrp_001848_rule_search_20261001/study/feb23_sources.json),
[manifeste de cette enquête](../../artifacts/testing/mrp_001848_rule_search_20261001/feb23_manifest.json).

## Essai commun : anticiper les besoins des jours de sécurité sources

Option expérimentale `meta.purchase_need_date_policy = "source_safety_backwards_v1"`.
Le comparateur est `mrp_global_rules_20261001/experiment/run_safety_total_all` :
il porte les 22 séries de besoins industriels et les 20 choix fournisseurs explicites,
dont le délai de 28 jours de 001893. La variante change une seule clé de son graphe.
La référence acceptée `shared_007923/run_shared` reste un second comparateur.
Ce choix permet de séparer l'effet des nouvelles échéances de l'ancien changement
de fournisseur utilisé pour la planification. Aucun remplacement automatique du nominal.

Pour chaque besoin matière **restant**, la disponibilité souhaitée est avancée des
jours de sécurité source, lundi–vendredi. Les besoins dont la date protégée est
dépassée sont exigibles aujourd'hui : ils ne disparaissent pas et ne sont pas
consommés fictivement. Le stock disponible et les engagements sont déduits selon
leurs dates de disponibilité. Les propositions remontent le calendrier de réception
puis le délai fournisseur pour trouver la dernière date de lancement réalisable.
Cette inversion du calendrier évite une réception disponible après une échéance
de week-end. Aucun nouveau calendrier de congés ou jours fériés n'est ajouté.

Le stock fixe source est conservé par une enveloppe commune :
`max(cumul des besoins anticipés, cumul des besoins physiques + stock fixe)`.
L'ancienne couverture temporelle et son complément ne s'ajoutent pas à cette enveloppe.
Les allocations et bilans physiques sont reconstruits aux dates d'origine :
la protection n'est pas une consommation. Les standards, exceptions existantes,
prix, délais fournisseurs, stocks initiaux et demandes physiques sont conservés.
Les prévisions UN peuvent être fractionnaires ; les achats et stocks physiques UN
restent entiers. Les engagements ne sont ni annulés ni avancés automatiquement.

Périmètre : **22 couples achetés**, dont matières premières et emballages ;
sept à Gien, quatorze à Avène et 021081 à Gaillac. Les fabrications et transferts
internes conservent leurs contrôleurs. 001848 garde principal moins cher/secours
plus rapide, évalués maintenant sur les échéances protégées ; cette politique
fournisseur n'est pas inventée pour les autres articles. 021081 garde ses parts
historiques et son délai agrégé conservateur. L'inventaire des paramètres et la
recette sont dans `artifacts/testing/mrp_need_dates_20261001/experiment`.

Les CSV distinguent l'échéance physique et le besoin anticipé. Le panneau MRP
affiche les jours de sécurité appliqués, le stock fixe, le premier manque protégé
avant propositions et la quantité couverte après cette échéance. Les anciens
indicateurs de moyenne/couverture restent des diagnostics, sans piloter les
achats de ce candidat. Un manque protégé n'est pas une rupture physique observée.

Résultat : simulation de **1 825 jours terminée en 664 secondes**, sous
`run_need_dates_2`, avec sources et moteur inchangés pendant l'exécution.
La comparaison industrielle porte uniquement sur 2025. Sur les **22 couples
achetés**, l'erreur absolue moyenne de stock diminue pour **7** et augmente pour
**15**, par rapport au comparateur précédent `safety_total_all`. Avec les effets
indirects sur les autres stocks, les 29 couples comparables donnent 10 améliorations,
15 dégradations et 4 égalités. Face à la référence acceptée plus ancienne,
le bilan des 29 couples est de 18 améliorations, 10 dégradations et une égalité.
Ces deux comparateurs ne sont pas interchangeables. Le candidat reste séparé.

Exemples d'erreur absolue moyenne annuelle, dans l'unité de l'article :

| Article / site | Unité | Comparateur précédent | Besoins anticipés | Variation |
|---|---|---:|---:|---:|
| 001848 / Avène | KG | 2 001,37 | 2 269,70 | +13,41 % |
| 001893 / Avène | KG | 21 733,07 | 18 374,92 | −15,45 % |
| 002612 / Avène | KG | 27 408,18 | 31 104,15 | +13,48 % |
| 007923 / Avène | KG | 12 192,92 | 13 668,39 | +12,10 % |
| 049371 / Avène | KG | 2 243,58 | 1 905,83 | −15,05 % |
| 055703 / Avène | KG | 147,95 | 154,76 | +4,61 % |
| 333362 / Gien | UN | 189 450,08 | 178 997,10 | −5,52 % |

Pour 001848, le premier nouvel achat principal passe du 15 avril au **12 mars** :
arrivée physique le **7 mai**, disponibilité le **26 mai**. L'arrivée industrielle
entre les 7 et 14 avril n'est toujours pas reproduite. L'erreur de stock du dernier
trimestre diminue de 17,70 %, mais celle de l'année augmente de 13,41 %.
Les nouveaux achats lancés en 2025 restent à **24 000 kg**, avec deux commandes
principales de 6 000 kg et trois commandes de secours de 4 000 kg. Leur coût engagé
passe de **37 920 à 69 360 €** (+82,91 %), dont une commande du 31 décembre reçue en
2026. Ce montant simulé n'est ni une dépense industrielle observée, ni un flux de
trésorerie ; il exclut les engagements initiaux et les coûts opérationnels/transport.
Le service client et le retard quotidien ne se dégradent pas sur cinq ans face
au comparateur précédent. Cela ne valide pas la calibration des stocks.

Vérifications : **29 tests ciblés en mémoire**, bilans physiques et intégralité UN,
contrôle indépendant de 1 610 nouvelles commandes et de 40 150 lignes de trace
quotidienne. Les projections physiques restent distinctes des besoins anticipés :
aucune seconde consommation n'est ajoutée. L'oracle contrôle 110 instantanés
de planification (22 couples, cinq dates de 2025) ; les comparaisons de stocks
reposent sur 1 459 photos, dont seulement trois pour 344135. Les périodes absentes
ne sont pas remplacées par zéro. Les anciens comparateurs sont conservés,
sans prétendre les avoir tous resimulés cinq ans dans cette itération.
Le premier lancement échoué sur un champ CSV optionnel reste enregistré ;
la correction et le lancement réussi sont documentés séparément.

[Comparaison interactive](../../resultats/regroupement_001757_20260929/comparaison_mrp_besoins_anticipes.html)
et [carte avec le panneau de comparaison](../../resultats/regroupement_001757_20260929/carte_mrp_besoins_anticipes.html).
Les autres panneaux et les deux suivis de lots de cette carte conservent leurs
résultats historiques. Le [manifeste de vérification](../../artifacts/testing/mrp_need_dates_20261001/manifest.json)
rassemble les preuves. La suite doit rapprocher les besoins restants et les stocks
disponibles à chaque décision, avant de modifier de nouveau les règles communes.

## 001848 à Avène : entrée entre les photos des 7 et 14 avril 2025

Analyse limitée à 001848/division 1810, sans modification du simulateur.
Les quantités des deux fichiers Flow sont en G pour cette référence, converties ici en kg.
L'inventaire donne **7 709,420 kg le 7 avril** (`Stocks!E835/H835`) et
**10 987,820 kg le 14 avril** (`E1104/H1104`), soit +3 278,400 kg.

Le plan MRP du 6 avril porte **4 000 kg d'entrée** dans la case datée du 6 avril
(`Feuille1!H13165`). Le plan du 13 avril répartit ensuite le stock physique entre
6 987,820 kg dans la case du 13 avril (`J14156`) et 4 000 kg dans celle du 20 avril
(`J14157`). Leur somme retrouve exactement la photo du 14 avril. Cette répartition
est cohérente avec la convention confirmée : le stock physique positionné dans une
semaine future est déjà présent sur site mais disponible plus tard.

Avec cette réception de 4 000 kg, le bilan implique **721,600 kg de sorties nettes**
entre les photos. Ce n'est pas une mesure indépendante des seules consommations :
d'autres ajustements éventuels ne sont pas identifiés. Le MRP du 6 avril prévoit
1 440 kg de besoins (`I13165`), qui ne doivent pas être assimilés aux sorties exécutées.

L'entrée projetée de 4 000 kg la plus proche est positionnée au 18 mai dans le plan
du 19 janvier (`H2065`), au 4 mai dans celui du 9 février (`H5110`), au 13 avril
dans celui du 16 février (`H6090`), puis au 6 avril dès le 23 février (`H7092`).
Cette dernière date reste stable dans les versions consultées jusqu'au 6 avril.
Le rapprochement de ces lignes est une hypothèse de continuité de l'approvisionnement,
pas une identité de commande démontrée : les lignes n'ont pas d'identifiant d'ordre.

**Estimation principale : commande autour du 17–23 mars**, si l'entrée observée
correspond au fournisseur VD0519670A, dont le standard est 4 000 kg, le délai
21 jours et le prix 4,20 €/kg (`268091.xlsx`, `FIA!A3:H3`). Une arrivée entre les
photos des 7 et 14 avril, moins 21 jours calendaires, donne les bornes du 17 au
24 mars. La quantité rend ce fournisseur plausible, sans l'identifier avec certitude.
Avec VD0951020A (56 jours, standard 6 000 kg, 1,58 €/kg, `FIA!A4:H4`), la même
arrivée conduirait plutôt au **10–17 février**, mais les 4 000 kg ne correspondent
pas à son standard ; un achat hors standard ou une réception partielle resterait possible.

Les 13 jours de traitement à réception (`Feuille1!E13165`) concernent la disponibilité
après l'arrivée physique ; ils ne sont pas retranchés une seconde fois pour dater
la commande à partir de l'entrée physique. Prévision d'une réception, émission
d'une commande, arrivée physique et disponibilité doivent rester distinctes.
Cette estimation suppose le délai fournisseur annoncé respecté ; la date réelle
de création et le fournisseur de cette réception ne sont pas explicitement fournis.

### Pourquoi les simulations actuelles ne produisent pas cette entrée

Lecture des trois calculs conservés (`run_shared`, `run_total_all`,
`run_safety_total_all`), limitée à M-1810/item:001848 : aucun nouvel achat en mars.
Le premier achat après le carnet initial est identique dans les trois scénarios :
**6 000 kg commandés le 15 avril à VD0951020A, reçus physiquement le 10 juin,
disponibles le 27 juin**, dans `mrp_orders_daily.csv`. L'ordre initial de 6 000 kg
reste celui d'`Extract_En_cours!8`, livré le 20 février et disponible le 11 mars.

Le 17 mars, la trace de `run_total_all` projette un premier manque le **30 juin**,
alors qu'un nouvel achat principal pourrait être disponible dès le **29 mai**.
Elle contient 18 000 kg de propositions futures, aucune à lancer ce jour-là, et
aucune proposition de secours. Le moteur anticipe donc, mais ne voit pas de besoin
justifiant un achat de secours pour avril dans son propre calcul.

Trois écarts distincts sont constatés :

- La photo du 17 mars donne 10 232,950 kg ; la clôture simulée du 16 mars vaut
  11 155,070 kg. Le modèle dispose déjà de 922,120 kg de plus avant l'entrée d'avril.
- Le MRP du 16 mars révise le besoin de cette semaine de 1 080 kg (`I9097`, version
  du 9 mars) à 1 800 kg (`I10077`). La trace du moteur référence encore `I9097`
  pour la semaine en cours, conformément au gel de cette semaine. Réviser ce
  traitement demande de distinguer besoins restants, reports et quantités déjà
  consommées, afin de ne pas les compter deux fois. Avec le stock J et les besoins I
  du plan source du 16 mars, en retirant les nouvelles entrées H, le solde devient
  négatif dans la case du **1er juin** ; cela diffère du 30 juin projeté par le moteur.
- La sécurité source de 20 jours ouvrés est présente dans les paramètres, mais
  **001848 reste exclu de la nouvelle protection continue** à cause de sa politique
  principal/secours. Le 17 mars, le complément technique de couverture daté est nul.
  Il ne faut pas présenter la simple présence des 20 jours comme une preuve qu'un
  plancher continu de stock est respecté par cette branche.

Le déclencheur du secours dans `mrp_planning.py:1052` recherche un manque physique
futur avant la première disponibilité possible du principal. Les exigences
techniques `reserve:` sont exclues de ce déclencheur. Une fois un achat ferme,
le moteur ne le reprogramme ni ne l'annule automatiquement. Les propositions
futures restent révisables. Ces règles expliquent la décision simulée ; elles ne
prouvent pas le critère exact utilisé par l'industriel pour les 4 tonnes d'avril.
Le déplacement des entrées H ne prouve pas non plus qu'il s'agissait déjà d'ordres fermes.

Suite à tester : rapprocher les besoins restants à même date et même stock,
intégrer une protection cohérente au calcul principal/secours, puis vérifier les
dates et quantités obtenues. Aucun changement du moteur ni nouvelle simulation
n'a été effectué pour ce diagnostic.

### Contrôle du seuil de couverture : livraison du 7 au 14 avril

Diagnostic complémentaire demandé : l'alerte est le passage du stock projeté sous
les besoins des **20 prochains jours ouvrés**, pas son passage sous zéro. Lecture
directe des huit versions du 16 février au 6 avril, calcul décimal en kg, sans
modification du moteur. Sur les cases hebdomadaires, le seuil retenu est la somme
des besoins I des **quatre semaines suivantes**. C'est une convention de lecture
hebdomadaire ; elle ne fournit pas un jour exact de consommation.

Le contrefactuel retire **uniquement les 4 000 kg H prévus en avril**, pour mesurer
leur utilité. Tous les J et toutes les autres H sont conservés aux dates du fichier.
Cela ne certifie pas que ces autres H soient fermes. Avec toutes les H, le calcul
retrouve les K sources et ne détecte pas de franchissement sous le seuil calculé.

Dans la version du **16 mars**, retrait de `H10080` uniquement :

| Case hebdomadaire | Solde sans ces 4 000 kg | Besoins des quatre semaines suivantes | Position |
|---|---:|---:|---|
| 6 avril | 6 262,950 kg | 3 060 kg | Au-dessus |
| 20 avril | 5 182,950 kg | 3 440 kg | Au-dessus |
| 27 avril | 4 282,950 kg | 3 480 kg | Au-dessus |
| 4 mai | 3 202,950 kg | 3 300 kg | **Sous le seuil de 97,050 kg** |

Le seuil du 4 mai vient de `I10085:I10088` : **180 + 1 280 + 940 + 900 = 3 300 kg**.
Les quatre cases existent ; aucune semaine absente n'est inventée pour ce seuil.
Avec l'entrée d'avril conservée, `K10084` vaut **7 202,950 kg**. Les 4 000 kg
suppriment donc ce déficit de couverture. Les 97,050 kg ne sont pas une quantité
de commande proposée : taille standard et couverture des besoins ultérieurs
restent à prendre en compte.

Si la case du dimanche 4 mai est représentée par le **lundi 5 mai**, retirer les
**13 jours lundi–vendredi** de réception donne le **16 avril** comme arrivée
physique limite, disponible le 5 mai. Pour une échéance stricte au dimanche
4 mai, il faudrait arriver le **15 avril**, disponible le vendredi 2 mai.
On ne retire pas une seconde fois les 20 jours de sécurité. Avec les délais FIA,
la commande limite serait le **19 février** au principal (56 jours calendaires),
ou le **26 mars** au secours (21 jours), dans la convention du lundi 5 mai.
Une commande le 17 mars au secours
arriverait le 7 avril, disponible le 24 avril selon la convention actuelle :
elle protégerait le seuil, mais ce calcul n'impose pas de commander dès le 17 mars.
Les jours fériés ne sont pas ajoutés ; les 13 jours ouvrés sont une convention
candidate, pas un calendrier industriel confirmé.

Les versions du 2 et 9 mars retrouvent également le seuil au 4 mai. Celles du
23 et 30 mars et du 6 avril le placent au 11 mai, soit une arrivée limite au
23 avril pour une disponibilité le lundi 12 mai. Dès le **23 février**, l'entrée est pourtant
déjà prévue dans la case du 6 avril, tandis que le franchissement recalculé sans
cette entrée se situe au **25 mai**. La règle testée explique l'utilité de la
réception pour préserver la couverture, **pas sa date exacte ni son maintien**.
Une date engagée conservée malgré les révisions reste une hypothèse ; les H
n'en renseignent pas le statut. Ne pas transformer le 16 avril calculé en une
preuve de la réception industrielle entre les 7 et 14 avril.

[Calcul décimal, cellules et empreinte source](../../artifacts/testing/mrp_001848_coverage_review_20261001/source_calculation.json).

### Révision du 16 février : pourquoi les 4 000 kg passent de mai à avril

La question porte sur la **révision du plan**, pas sur une nouvelle commande
détectée en mars. La séquence source est : 18 mai dans le plan du 2 février
(`H4122`), 4 mai dans celui du 9 février (`H5110`), puis **13 avril** dans celui
du 16 février (`H6090`). La dernière révision avance donc la case de **21 jours**.
Sans identifiant d'ordre, cette continuité de la ligne de 4 000 kg reste un
rapprochement entre versions, pas un suivi certifié d'une commande individuelle.

Pour comparer les deux derniers plans, conserver la première entrée de **6 000 kg
en février**, tous les J et les autres H ; retirer seulement les 4 000 kg de mai
dans l'ancien plan et ceux d'avril dans le nouveau. Au **18 mai**, on obtient :

| Indicateur | Plan du 9 février | Plan du 16 février |
|---|---:|---:|
| Stock projeté sans les 4 000 kg étudiés | 2 975,610 kg (`K5111 − 4 000`) | 2 974,640 kg (`K6094 − 4 000`) |
| Besoins exportés des quatre semaines suivantes | 2 380 kg | 3 290 kg |
| Marge par rapport à ces besoins | +595,610 kg | **−315,360 kg** |
| Besoin du 8 juin | 1 800 kg (`I5113`) | **2 700 kg (`I6097`)** |

Le stock projeté au 18 mai ne change que de **−0,970 kg**, tandis que les besoins
exportés de sa fenêtre de protection augmentent de **910 kg**. La hausse de
900 kg au 8 juin est le changement principal de cette fenêtre. Le solde de
10 kg provient de la case du 25 mai présente dans le nouveau plan ; cette case
est absente de l'ancien export, ce qui ne certifie pas une consommation nulle.
Les autres besoins de la fenêtre sont 570 kg au 1er juin et 10 kg au 15 juin,
inchangés. Sur les lignes exportées, le premier franchissement du seuil passe
du **1er juin** (2 405,610 < 2 530 kg) au **18 mai** (2 974,640 < 3 290 kg).
Les semaines absentes limitent la précision du diagnostic chronologique.

La lecture de toutes les lignes ajoute un résultat plus précis : avant le besoin
du **8 juin**, le solde sans les 4 000 kg est de **2 405,610 kg** dans l'ancien
plan, contre **2 394,640 kg** dans le nouveau. Après les besoins de cette semaine,
il passe respectivement à **+605,610 kg** et **−305,360 kg**. Si l'on remet uniquement
le besoin du 8 juin à 1 800 kg dans le nouveau plan, le solde reste **+594,640 kg** :
cette hausse de 900 kg suffit donc à expliquer le déficit nouveau à cette case.

| Version | Réception H étudiée | Premier solde négatif sur les lignes exportées, sans cette H | Intervalle |
|---|---|---|---:|
| 9 février | 4 mai (`H5110`) | 29 juin : −124,390 kg (`K5115 − 4 000`) | 56 jours |
| 16 février | 13 avril (`H6090`) | 8 juin : −305,360 kg (`K6097 − 4 000`) | 56 jours |

**Le premier déficit physique projeté et la réception prévue se déplacent tous
deux exactement de 21 jours.** C'est une correspondance numérique qui explique
l'amplitude du déplacement entre ces deux versions. Elle ne prouve pas que le
MRP industriel utilise ce déficit comme déclencheur, ni que les 56 jours soient
le délai fournisseur : l'intervalle relie ici réception et manque, pas commande
et réception. Le standard de 4 000 kg est déjà présent dans l'ancien plan ; aucune
bascule effective de fournisseur n'est établie par cette révision.

La révision est plus large que cette ligne : les besoins exportés à partir du
16 février passent de **17 240 à 20 130 kg** (+2 890 kg). Le stock initial du
nouveau plan, 6 054,640 kg, dépasse de 179,030 kg les 5 875,610 kg que l'ancien
plan projetait après sa semaine du 9 février. Les entrées H restantes passent
de **11 364,390 à 14 075,360 kg**, soit **+2 710,970 kg = 2 890 − 179,030**.
L'entrée de 6 000 kg de février est maintenue ; une autre entrée de 4 000 kg est
maintenant prévue au 22 juin, avec un reliquat final de 75,360 kg. Les 13 jours de
réception restent inchangés ; les sources de paramètres donnent toujours 20 jours
de sécurité et zéro stock fixe, sans historique de modification de ces paramètres.

**La règle des 20 jours de couverture seule reste insuffisante pour dater H.**
Avec 13 jours ouvrés de réception et le lundi suivant comme date représentative,
la protection du 19 mai donnerait une arrivée limite au **30 avril**, encore
après la case source du 13 avril. Il reste donc une convention de calendrier,
de protection ou de décision à identifier. Le motif de 56 jours ne s'étend pas
automatiquement aux versions voisines : le plan du 2 février donne 49 jours ;
dans celui du 23 février, une autre réception conservée masque le déficit proche.
Ne pas attribuer ces semaines à une avance réelle du fournisseur, car il s'agit
ici de dates **prévues** révisées dès février. Les cellules et contre-calculs sont
conservés dans `source_calculation.json`, rubrique `february_full_revision`.

### Révision du 23 février : nouvelle avance du 13 au 6 avril

La version suivante est un contre-exemple à l'explication par le seul seuil de
couverture : `H6090` (plan du 16 février, **13 avril**) devient `H7092` (plan du
23 février, **6 avril**), pour 4 000 kg. Pourtant, sans cette seule entrée d'avril,
le franchissement des quatre semaines de besoins passe du **18 mai** au **25 mai**.
Au 18 mai, on passe de 2 974,640 kg contre 3 290 kg nécessaires à **3 864,440 kg
contre 3 810 kg**. La protection devient donc suffisante à cette case dans le
nouveau plan. La réception avance d'une semaine alors que le besoin de protection
calculé recule d'une semaine.

Les besoins ont été redistribués : 13 avril **540 → 720 kg**, 18 mai
**2 190 → 1 140 kg**, 25 mai **10 → 900 kg**, 8 juin **2 700 → 1 260 kg**.
Le stock projeté sans cette entrée au 6 avril reste presque identique :
7 344,640 → **7 344,440 kg**. La hausse locale de 180 kg au 13 avril ne suffit
donc pas à imposer une livraison une semaine plus tôt selon le seuil testé.

Autre changement réel : les 6 000 kg prévus en février (`H6082`) sont désormais
du stock J disponible ultérieurement (`J7087`, semaine du 2 mars). Les
**5 874,440 kg** immédiatement disponibles (`J7086`) et ces **6 000 kg** totalisent
**11 874,440 kg**, exactement la photo du 24 février (`Stocks!E1084/H1084`).
Ce passage de réception prévue à stock physiquement présent explique la nouvelle
répartition de février, sans créer un déficit de couverture proche d'avril.

Contre-calcul contrôlé indépendamment : garder le plan du 23 février et déplacer
uniquement ses 4 000 kg du 6 au **13 avril**. Le stock reste **7 344,440 kg** au
6 avril pour **2 340 kg** de besoins des quatre semaines suivantes (`I7093:I7096`,
fenêtre complète). Dès le 13 avril, les soldes retrouvent exactement ceux de la
source. Aucun déficit projeté ni franchissement sur les fenêtres complètes
contrôlées n'apparaît. Ce contre-calcul suit K qui crédite H immédiatement ;
il n'est pas une simulation physique d'un délai de qualité.

Enfin, **23 février + 56 jours = 20 avril**, pas 6 avril. L'égalité précédente
16 février + 56 jours = 13 avril était un indice, pas une preuve que la date
du calcul MRP soit celle du lancement. Il ne faut donc pas implémenter cette
égalité comme règle de commande. Un recalage d'approvisionnement déjà planifié
reste possible ; les sources examinées ne permettent pas d'en identifier ici
le motif ni de le qualifier de décision manuelle. Résultats et lignes conservés
dans `source_calculation.json`, rubrique `february23_revision`. Aucun changement
de moteur ni de calendrier n'est effectué à partir de ce diagnostic.

### Version du 2 mars : besoin de protection plus proche et deuxième réception avancée

La semaine suivante modifie de nouveau le diagnostic. Dans le plan du **2 mars**,
les premiers 4 000 kg restent au **6 avril** (`H8107`), mais les 4 000 kg suivants
passent du **22 juin** (`H7102`, ancien plan) au **11 mai** (`H8112`), soit **six
semaines plus tôt**. Le réapprovisionnement doit être analysé dans son ensemble.

Le stock projeté à la fin de la case du 2 mars est presque inchangé entre les
deux versions : **10 234,440 → 10 234,206 kg**. En revanche, les besoins sont
révisés : 16 mars **720 → 1 080 kg**, 23 mars **540 → 720 kg**, 30 mars
**180 → 360 kg**, 6 avril **730 → 1 090 kg**, 4 mai **360 → 900 kg**.
En retirant uniquement la première réception de 4 000 kg d'avril et en gardant
les autres entrées, le stock au 4 mai passe de **5 004,440 à 3 384,206 kg**.
Dans le nouveau plan, les quatre semaines suivantes exigent **3 700 kg** :
`I8112:I8115 = 190 + 390 + 1 650 + 1 470`. Le manque de protection est donc
**315,794 kg**, avec un stock physique projeté encore positif. Le seuil devient
insuffisant dès la case du **4 mai**, contre le **25 mai** dans le plan précédent.
L'ancien total exporté sur cette fenêtre vaut 2 970 kg ; sa semaine du 11 mai
est absente et n'est pas certifiée nulle.

La réception de mai arrive après ce premier besoin de protection : elle ne peut
pas remplacer celle d'avril. Les 4 000 kg d'avril portent le solde source du
4 mai à **7 384,206 kg**. Ce plan renforce donc l'utilité d'une réception en avril,
sans déterminer à lui seul sa semaine exacte. Les informations révisées du
2 mars ne doivent pas être utilisées rétrospectivement comme si le plan du
23 février les connaissait déjà. Calcul conservé dans `source_calculation.json`,
rubrique `march2_revision`, sans modification du moteur.

### Chronologie complète du 5 janvier à la réception d'avril

Reprise des **15 versions** du 5 janvier au 13 avril, avec `Extract_En_cours`,
les inventaires et les offres FIA. Les versions sont des plans alternatifs :
leurs entrées ne s'additionnent pas comme des commandes exécutées.

`Extract_En_cours.xlsx`, `Sheet1!A8:I8`, identifie une ligne **ECHCDE** pour
001848/1810 : fournisseur **VD0951020A**, **6 000 000 G = 6 000 kg**, livraison
prévue le **20 février**, traitement **13 jours**, date d'entrée **11 mars**.
Ces deux dates concordent avec 13 jours lundi–vendredi, sans jours fériés ajoutés.
Il s'agit de dates du carnet, pas d'horodatages de réception exécutée. La ligne 7
du même article concerne Gien (1430), et ne doit pas être ajoutée à Avène.

Les 6 000 kg sont déjà dans les plans à partir du 5 janvier, dans la case du
16 février, jusqu'à la version du 16 février. Le plan du 23 février les reprend
en J futur à la semaine du 2 mars ; la photo du 24 février corrobore leur présence
physique. Cette disponibilité hebdomadaire J ne reproduit pas exactement le
11 mars du carnet : les deux sources sont conservées sans forcer leur égalité.

| Version MRP | Approvisionnement qui précède celui d'avril | Prochaine entrée après février | Entrées suivantes du plan, kg |
|---|---|---|---|
| 5 janvier | 6 000 kg, semaine du 16 février | **3 331,160 kg le 18 mai** | Aucune autre H |
| 12 janvier | 6 000 kg, 16 février | **3 331,360 kg le 18 mai** | Aucune autre H |
| 19 janvier | 6 000 kg, 16 février | **4 000 kg le 18 mai** | 822,978 le 24 août |
| 26 janvier | 6 000 kg, 16 février | 4 000 kg le 18 mai | 824,360 le 24 août |
| 2 février | 6 000 kg, 16 février | 4 000 kg le 18 mai | 1 004,360 le 24 août |
| 9 février | 6 000 kg, 16 février | **4 000 kg le 4 mai** | 1 364,390 le 20 juillet |
| 16 février | 6 000 kg, 16 février | **4 000 kg le 13 avril** | 4 000 le 22 juin ; 75,360 le 12 octobre |
| 23 février | 6 000 kg déjà présents, J futur au 2 mars | **4 000 kg le 6 avril** | 4 000 le 22 juin ; 255,560 le 12 octobre |
| 2 mars | Stock J, plus de H de février | 4 000 kg le 6 avril | **4 000 le 11 mai** ; 75,794 le 5 octobre |
| 9 mars | Stock J | 4 000 kg le 6 avril | 4 000 le 18 mai ; 75,794 le 12 octobre |
| 16 mars | Stock J | 4 000 kg le 6 avril | 4 000 le 1er juin ; 4 000 le 17 août ; 749,050 le 12 octobre |
| 23 mars | Stock J | 4 000 kg le 6 avril | 4 000 le 1er juin ; 4 000 le 17 août ; 930,680 le 12 octobre |
| 30 mars | Stock J | 4 000 kg le 6 avril | 4 000 le 1er juin ; 4 000 le 17 août ; 932,180 le 12 octobre |
| 6 avril | Stock J | 4 000 kg le 6 avril | **6 000 le 1er juin** ; 2 958,580 le 14 septembre |
| 13 avril | **4 000 kg déjà présents**, J futur au 20 avril | La H d'avril disparaît | 6 000 le 1er juin ; 2 960,180 le 21 septembre |

Au 5 janvier, la quantité de 3 331,160 kg est exactement le reste du plan :
**19 414,006 kg de besoins − 10 082,846 kg de stock − 6 000 kg déjà attendus**.
Au 19 janvier, le reste après les 6 000 kg vaut **4 822,978 kg** : la source
le répartit en **4 000 + 822,978 kg**. C'est un constat de calcul net et de
découpage du plan, pas la preuve de commandes émises à ces dates. Dans les
15 versions, les soldes K se reconstruisent par J + H − I et le dernier K vaut
zéro ; somme(H) = somme(I) − somme(J). Cette fermeture du plan exporté ne doit
pas devenir une cible de stock physique réel nul.

La quantité de 4 000 kg existe dès le 19 janvier, avant les avances de février.
Le standard est compatible avec l'offre de secours, mais les H n'identifient
pas le fournisseur. La seule commande Avène nominative dans l'extrait est celle
de 6 000 kg chez le principal. Au 6 avril, la prochaine H de juin passe d'ailleurs
de 4 000 à 6 000 kg : il ne faut pas supposer toutes les H futures au même fournisseur.

La date du 6 avril reste ensuite stable sur **sept versions successives**, du
23 février au 6 avril, alors que les besoins et les H suivantes changent. Cela
justifie de rechercher une règle de maintien des engagements/propositions,
sans certifier un statut ferme que le fichier ne donne pas. L'arrivée physique
des 4 000 kg est corroborée entre les photos des 7 et 14 avril ; J du plan du
13 avril distingue 6 987,820 kg immédiatement et 4 000 kg à la semaine du 20 avril.

Contrôle des stocks : **14 des 15 sommes J** retrouvent exactement la photo du
lundi suivant. Exception : plan du **2 mars**, J = **10 774,206 kg**, contre
**11 334,440 kg** dans la photo du 3 mars, soit **−560,234 kg**. Ce J correspond
au stock de la photo du 10 mars et du plan du 9 mars ; cela ne suffit pas à
prouver une erreur de datation. Cet écart est supérieur aux 315,794 kg de manque
de protection calculés au 4 mai dans le plan du 2 mars : il est donc matériel
pour la calibration. Ajouter fictivement les 560,234 kg à la disponibilité
initiale ferait passer ce solde de 3 384,206 à 3 944,440 kg, au-dessus de 3 700 kg.
Ce simple contre-calcul n'autorise pas la correction : la disponibilité de la
différence n'est pas documentée. Aucun ajustement arbitraire n'est appliqué.

Le calcul reste contemporain de chaque version : les révisions du 2 mars ne
peuvent pas justifier comme information déjà connue l'avance visible au
23 février. La règle des 20 jours avec 13 jours de réception ne reproduit pas
tous les déplacements de dates. Les règles de quantité nette sont établies
sur ces exports ; le calendrier exact de replanification et l'émission de la
commande d'avril restent à identifier. Données, cellules et contrôles conservés
dans `source_calculation.json`, rubrique `chronology_from_january`.

### Reconstitution du calcul industriel : quantités et anticipation

Nouvelle lecture directe des **52 versions de 001848/1810**, avec calculs en
mémoire et contre-calcul indépendant. Les **176 cellules H positives** sont des
entrées dans des versions alternatives du plan, pas 176 commandes exécutées.
Aucune règle du moteur, carte ou simulation n'est modifiée par cette analyse.

**Quantité nette à couvrir.** Dans les 52 versions de ce seul couple, le dernier
K renseigné vaut zéro et `somme(H) = somme(I) - somme(J)` ; le résidu numérique
maximal après conversion en kg est inférieur à 0,000001 kg. Cela décrit les
lignes exportées, sans inventer de besoins dans les semaines absentes. Exemples :

| Version | Besoins I du plan, kg | Stock J total, kg | Entrées H, kg |
|---|---:|---:|---:|
| 5 janvier | 19 414,006 | 10 082,846 | 6 000 + 3 331,160 |
| 19 janvier | 19 620,000 | 8 797,022 | 6 000 + 4 000 + 822,978 |
| 16 mars | 22 982,000 | 10 232,950 | 4 000 + 4 000 + 4 000 + 749,050 |

Les H du 5 janvier sont `H88/H101`, ceux du 19 janvier
`H2052/H2065/H2073`, ceux du 16 mars `H10080/H10088/H10095/H10100`.
La dernière proposition peut donc être un complément net inférieur au standard.
Le contre-calcul indépendant retrouve 64 H à 4 000 kg, 56 à 6 000 kg et quatre
à 5 000 kg (`H18190/H35393/H48201/H50325`). Les 52 autres quantités correspondent
exactement aux 52 dernières entrées positives des plans ; aucun de ces reliquats
n'apparaît avant la dernière entrée. Cela appuie la distinction entre tailles
usuelles et solde final projeté, sans identifier le nombre d'ordres derrière H.
L'export ne justifie ni un minimum de 6 000 kg pour toutes les propositions,
ni l'assimilation de chaque proposition de 4 000 kg à un achat de secours ferme.
Le solde terminal nul est un constat sur 001848, **pas une cible industrielle
universelle à imposer aux autres articles ou à la simulation physique**.

**Positionnement avant le manque.** Pour chaque H, conserver les entrées
antérieures et tous les J, retirer cette H et les suivantes, puis cumuler les I
renseignés. La première semaine déficitaire est un résultat conditionnel du plan,
pas une rupture industrielle observée. Sur 176 cellules, elle se situe 49 jours
après H dans 80 cas, 42 jours dans 46, 70 jours dans 12, 35 jours dans 12,
56 jours dans 11, 63 jours dans cinq, 91 jours dans quatre, 28 jours dans trois,
77 jours dans deux et 21 jours dans un. Les semaines non exportées ne sont pas
des observations de consommation nulle.

Sur les **126 H placées à plus de 49 jours de leur version**, 113 (89,7 %)
précèdent ce manque de **42 ou 49 jours**. Cette sélection descriptive n'identifie
pas les engagements fermes. Elle renforce la piste déjà étudiée le 30 septembre :
**20 jours ouvrés de sécurité + 13 jours de réception**, soit 33 jours ouvrés,
environ six à sept semaines. Elle ne démontre pas une formule exacte : le choix
du jour représentatif d'une semaine, son arrondi et le calendrier restent à établir.
Le cas `H22174` du plan du 8 juin donne notamment seulement 35 jours malgré son
éloignement de 70 jours de la version.

Une fermeture candidate du 4 au 24 août retrouve deux anticipations de 70 jours
avec ces 33 jours ouvrés et un rabattement au dimanche précédent :
`H7102` (22 juin, manque le 31 août) et `H5118` (20 juillet, manque le 28 septembre).
Deux semaines ne retrouvent pas ces deux dates avec la même convention. Cela ne
confirme ni ces dates de fermeture ni un calendrier unique : par exemple `H30180`
(25 janvier 2026, manque le 8 mars) demande un arrondi différent. Aucun calendrier
de fermeture n'est ajouté au moteur à partir de ces seuls rapprochements.

**Application à l'entrée d'avril.** Dans le plan du 16 mars, retirer les nouvelles
H laisse 6 262,950 kg à la fin de la case du 6 avril, puis -97,050 kg dans celle
du 1er juin. Une anticipation de 33 jours lundi–vendredi à partir du 1er juin
donnerait le **16 avril**, avant choix de convention hebdomadaire et sans jours
fériés : elle rapproche la réception d'avril, mais **ne retrouve pas exactement
la case du 6 avril**. Avec 21 jours fournisseur, ce calcul indicatif remonterait
au 26 mars ; il ne prouve donc pas l'estimation du 17–24 mars tirée de l'arrivée
physique. Ces deux calculs ne doivent pas être confondus.

La case du 6 avril reste inchangée de la version du 23 février à celle du 6 avril,
alors que le manque conditionnel se déplace du 22 juin au 1er juin, puis au 8 juin.
C'est compatible avec une date d'approvisionnement conservée malgré les révisions
des besoins, mais le statut ferme de cette entrée n'est pas renseigné. Le calcul
doit donc distinguer **nouvelles propositions recalculables** et **approvisionnements
déjà engagés** ; recalculer toutes les H comme des besoins nouveaux ne reproduirait
pas cette stabilité. La règle exacte d'engagement reste à identifier.

Enfin, K crédite H dans sa semaine, alors que le carnet initial et les photos
associent les H rapprochées à des arrivées physiques. Il faut conserver cette
convention de K pour comparer les exports et tenir séparément la disponibilité
physique : décaler toutes les H de 13 jours dans K ajouterait une convention
absente de sa récurrence. Ces mesures portent sur l'anticipation MRP, pas sur
des retards fournisseurs. Elles expliquent pourquoi la seule date de manque
physique du simulateur ne suffit pas, sans certifier encore le déclencheur exact
des 4 tonnes reçues entre les 7 et 14 avril.

## Extension globale des règles communes — essais du 1er octobre 2026

Deux nouveaux calculs de **1 825 jours** sont comparés à la dernière référence
retenue, avec l'amélioration 007923. Le moteur n'est pas modifié : les règles
existantes sont activées dans deux graphes distincts. **Ces essais ne remplacent
pas automatiquement la référence.** La calibration industrielle porte sur 2025,
seule année couverte par les photos réelles ; le service est aussi contrôlé sur cinq ans.

- **Besoins industriels** : rapprochement du total I sur les 22 achats externes,
  contre quatre auparavant. Les six protections continues existantes sont conservées.
- **Besoins + sécurité** : même rapprochement, et protection continue sur 20 achats,
  soit 14 ajouts. 001848 conserve principal/secours et 021081 ses fournisseurs multiples.
- Les produits finis et intermédiaires fabriqués/transférés ne deviennent pas des
  achats externes. Ils peuvent évoluer indirectement avec la disponibilité des composants.

### Règle testée et paramètres préservés

Pour chaque semaine effectivement renseignée, le complément prévisionnel vaut
`max(besoins industriels I − besoins propres déjà planifiés, 0)`. Les besoins propres
ne sont pas supprimés lorsqu'ils dépassent I. La version doit être connue au jour
de la décision ; **une semaine absente n'est pas un zéro**. Les 36 482 cellules I
retenues ont été vérifiées directement dans les Excel par un oracle indépendant.
344135 ne dispose que de 17 versions MRP et trois photos de stock comparables.
730384 garde son unité M ; les prévisions UN peuvent être fractionnaires, les
mouvements physiques UN restent entiers.

La protection continue est un plancher projeté, pas une consommation :
`S = max(quantité fixe source, débit prévisionnel × durée de sécurité)`.
049371 conserve 888 kg et 40 jours ouvrés ; 333362 conserve 110 000 UN et 10 jours
ouvrés. Les jours sont convertis selon lundi–vendredi : respectivement 54–56 et
12–14 jours calendaires selon la date. Cette conversion ne représente pas à elle
seule les congés d'août ni un calendrier de fermeture des transports.

Le débit est calculé sur la fenêtre de couverture des besoins planifiés réconciliés.
Le plancher S s'applique dès le lendemain. Au délai de disponibilité fournisseur,
il devient le maximum de S et du complément de couverture historique non déjà
contenu dans les besoins datés. Stocks disponibles et commandes engagées sont
déduits selon leurs dates ; un engagement tardif n'est pas racheté automatiquement.
La réserve peut donc rester temporairement non atteinte. Les standards contraignants
restent arrondis au multiple supérieur, avec les limites de capacité ; les exceptions
non contraignantes 333362 et 338929 sont conservées.

**Les paramètres viennent des sources ; leur combinaison par maximum, le débit
moyen et la persistance du plancher restent des conventions candidates du moteur.**
Ces essais ne démontrent pas la formule exacte de l'ERP. Les stocks initiaux, prix,
jours et quantités de sécurité, offres source et calendriers de demande physique
complémentaire restent préservés. Les offres explicitement fixées sont celles
utilisées dans la référence ; ce n'est pas une politique générale de secours sous
incident. Pour 001893, la nouvelle sélection aligne aussi le délai du planificateur
de 56 à 28 jours : son effet n'est pas isolé de celui de la sécurité.

### Résultats sur les stocks réels de 2025

Erreur absolue moyenne aux dates des photos, comparées à la clôture simulée de la
veille, sans interpolation. Une variation négative signifie un rapprochement.
Le dernier trimestre est montré séparément ; les erreurs de différentes unités
ne sont jamais additionnées. Les autres références sont consultables dans le
tableau cliquable de la comparaison HTML.

| Article | Unité | Référence, année | Besoins industriels, année | Besoins + sécurité, année | T4 : référence / besoins / besoins + sécurité |
|---|---|---:|---:|---:|---:|
| 002612 | KG | 27 386,82 | 27 404,81 (+0,1 %) | 27 408,18 (+0,1 %) | 34 202,69 / 34 261,16 / 34 274,65 |
| 007923 | KG | 12 180,32 | 12 191,12 (+0,1 %) | 12 192,92 (+0,1 %) | 9 168,14 / 9 189,73 / 9 196,93 |
| 016332 | KG | 541,32 | 481,10 (-11,1 %) | 488,13 (-9,8 %) | 599,43 / 515,89 / 604,87 |
| 029313 | KG | 167,21 | 166,84 (-0,2 %) | 128,73 (-23,0 %) | 246,74 / 228,95 / 181,85 |
| 038005 | KG | 22 978,49 | 23 227,76 (+1,1 %) | 18 120,16 (-21,1 %) | 32 299,54 / 32 038,03 / 19 106,82 |
| 039668 | KG | 136,21 | 114,07 (-16,3 %) | 114,14 (-16,2 %) | 229,09 / 228,64 / 228,91 |
| 049371 | KG | 3 814,05 | 3 404,94 (-10,7 %) | 2 243,58 (-41,2 %) | 6 677,18 / 5 858,91 / 1 725,91 |
| 333362 | UN | 308 664,69 | 178 413,10 (-42,2 %) | 189 450,08 (-38,6 %) | 600 875,77 / 221 306,85 / 311 177,08 |

- **Besoins industriels seuls** : 16 écarts annuels diminuent, 11 augmentent, 2 restent identiques, sur 29 couples.
- **Besoins industriels + protection continue** : 16 écarts annuels diminuent, 11 augmentent, 2 restent identiques, sur 29 couples.

Le nombre de références améliorées ne suffit pas à choisir un scénario : il faut
aussi examiner l'ampleur des dégradations, les dates et le service client.
La protection généralisée dégrade notamment 338928 de 52,98 %, 001893 de 15,37 %,
734545 de 13,45 % et 708073 de 13,15 % sur l'erreur annuelle. Le saut initial de
001893 n'est donc pas résolu par cette extension. Les deux variantes restent des
expériences séparées ; les résultats ne justifient pas leur promotion aveugle.
002612 et 007923 avaient déjà les deux règles actives : leurs faibles changements
proviennent ici du couplage avec le reste de la chaîne.

Durées effectives : 72 min 48 s pour les besoins industriels et 79 min 19 s avec
la protection étendue. Les calculs ont tourné en parallèle sur le même poste ;
ces durées ne constituent pas un benchmark ni une amélioration de performance.

| Scénario | PF | Servi en 2025, UN | Jours de reliquat plus élevé en 2025 | Même mesure sur cinq ans |
|---|---|---:|---:|---:|
| Référence | item:268091 | 3 441 853,00 | 0 | 0 |
| Référence | item:268967 | 1 575 985,00 | 0 | 0 |
| Besoins industriels | item:268091 | 3 470 653,00 | 0 | 0 |
| Besoins industriels | item:268967 | 1 575 985,00 | 0 | 0 |
| Besoins + sécurité | item:268091 | 3 499 453,00 | 0 | 0 |
| Besoins + sécurité | item:268967 | 1 575 985,00 | 0 | 0 |

### 333362 : origine du saut de fin d'année

Dans la référence, les fortes réceptions du T4 proviennent surtout de commandes
engagées avant octobre. Le bilan physique ci-dessous distingue donc les commandes
émises pendant le trimestre des réceptions effectivement arrivées. Toutes les
quantités sont en UN ; aucune conversion par 1 000 n'explique le saut.

| Scénario | Ouverture T4 | Reçu au T4 | Consommation propre | Autres consommations | Clôture annuelle | Commandé pendant le T4 | Jours sans disponible |
|---|---:|---:|---:|---:|---:|---:|---:|
| Référence | 213 848,00 | 1 227 674,00 | 13 848,00 | 0,00 | 1 427 674,00 | 83 434,00 | 0 |
| Besoins industriels | 145 162,00 | 733 736,00 | 519 048,00 | 0,00 | 359 850,00 | 79 435,00 | 42 |
| Besoins + sécurité | 58 892,00 | 791 408,00 | 230 630,00 | 0,00 | 619 670,00 | 0,00 | 28 |

Le planificateur daté tient bien compte des stocks PF et des engagements avant
l'explosion BOM des nouvelles propositions. La divergence de référence concerne
les besoins/couvertures projetés et l'exécution dynamique : les réceptions engagées
continuent alors que les fabrications PF s'arrêtent presque au T4. La formule
d'exécution utilise directement le stock usine ; le dépôt agit par ses prélèvements.
Il serait incorrect d'affirmer que le planificateur ignore tous les stocks PF.
Dans l'essai « besoins industriels seuls », à J270, les besoins datés augmentent
de 2 493 247 à 4 794 265 UN, tandis que le complément technique de couverture
diminue de 1 336 851 à zéro. Le débit est réévalué sur une fenêtre de 125 jours.
La colonne diagnostique `target_stock_qty` conserve la cible historique ; elle ne
représente pas ici la cible recalculée localement. La baisse des achats ne signifie
donc pas une simple baisse des besoins industriels.

Le retour des consommations au T4 est aussi un déplacement du programme PF268967 :
la production cumulée avant le trimestre passe de 1 832 600 à 1 185 800 UN, et les
libérations au T4 de 107 800 à 539 000 UN. La production annuelle reste plus faible,
1 724 800 contre 1 940 400 UN. Dans cet essai, 333362 contraint la production pendant
42 jours du T4. **Une courbe de stock plus proche ne suffit pas à valider le
comportement industriel.** Les 22 articles changent ensemble : l'effet sur le
calendrier PF ne peut pas être attribué entièrement au seul changement de 333362.

La première version source 333362 n'a que 17 semaines renseignées : son total ne
peut pas être comparé à une année BOM complète pour prouver une surconsommation.

### Carte, vérification et reproduction

- [Comparaison interactive et tableau par référence](../../resultats/regroupement_001757_20260929/comparaison_mrp_regles_globales.html).
- [Carte complète, accès à la nouvelle comparaison](../../resultats/regroupement_001757_20260929/carte_mrp_regles_globales.html).
- [Oracle indépendant des 29 stocks, du service et des bilans](../../artifacts/testing/mrp_global_rules_20261001/oracle/final_postrun.json).
- [Manifeste des contrôles et empreintes](../../artifacts/testing/mrp_global_rules_20261001/manifest.json).
- [Point de reprise compact](../../config/mrp_global_rules_20261001/README.md).

Les autres panneaux de la carte complète et les deux suivis de lots restent
historiques : seule la comparaison présente ces nouveaux essais. Les qualifications
CSV, les tests ciblés et les contrôles navigateur sont détaillés dans le manifeste ;
ils ne certifient pas la calibration industrielle de chaque article.

## 001893 et 007923 : cohérence des offres et périmètre des règles communes

Étude `mrp_offer_alignment_20261001`, depuis le scénario `total_extension`
sauvegardé dans le commit `32d403792`. Les règles du moteur sont réutilisées
sans modification de leur code. Trois essais séparés sont préparés : aligner
l'offre de 001893, étendre la sécurité et les besoins totaux à 007923, puis
réunir ces deux changements dans un troisième calcul de cinq ans.

**Résultat des trois essais de cinq ans : retenir l'extension 007923 seule ;
écarter l'alignement isolé de 001893 et sa combinaison avec 007923.** La cohérence
du délai ne suffit pas à valider la calibration du stock ni le service.

| Indicateur | Référence | Délai 001893 seul | Règles 007923 seules | Combinaison |
|---|---:|---:|---:|---:|
| Écart moyen absolu annuel 001893, kg | 18 807,90 | 31 749,28 | 18 837,81 | 31 817,64 |
| Même écart au T1, kg | 32 512,91 | 25 297,81 | 32 512,91 | 25 297,81 |
| Même écart au T4, kg | 16 363 | 40 573 | 16 363 | 40 778 |
| Écart moyen absolu annuel 007923, kg | 25 755,51 | 25 951,77 | **12 180,32** | 12 108,73 |
| Même écart au T4, kg | 17 793,21 | 17 649 | **9 168,14** | 9 147 |
| PF268091 servi en 2025, UN | 3 441 853 | 3 384 253 | **3 441 853** | 3 413 053 |

Pour 007923 seule, la baisse de l'écart annuel est de **52,7 %** et celle du
dernier trimestre de **48,5 %**. Les jours sans stock disponible passent de
36 à zéro ; les deux jours sans stock physique disparaissent aussi. Le volume
reçu en 2025 reste de 344 520 kg, engagement initial compris : les dates
changent. Le nouvel achat supplémentaire en fin d'année est destiné à 2026.
Au 29 décembre, le stock passe de 7 819,80 à 26 959,80 kg, contre 39 901,71 kg
source : le résidu de 12 941,91 kg reste explicite.

Sur les 29 stocks comparables, cette extension améliore sept écarts annuels,
en laisse douze identiques et en dégrade dix légèrement, au maximum de 1,051 %.
Le service client n'est pire aucun jour des cinq ans. L'alignement isolé de
001893 dégrade au contraire le service 2025 de 57 600 UN ; sa combinaison le
dégrade de 28 800 UN. Ces variantes restent consultables comme essais écartés.

Un quatrième essai de **365 jours**, sans tronquer l'horizon prévisionnel
glissant de 364 jours, ajoute à 001893 la sécurité persistante et le total I,
en plus de son offre alignée et des règles 007923. Il est également écarté :
son écart annuel 001893 atteint 21 677,53 kg, le T1 34 352,91 kg et le T4
17 836,66 kg ; le pic initial augmente à 119 600 kg. Le service revient au
niveau de la référence, mais ne compense pas cette dégradation. Ce dépistage
ne justifie pas un nouveau calcul de cinq ans et n'est pas présenté comme tel.
Il montre précisément pourquoi ces dernières règles ne sont pas activées
aveuglément sur toutes les matières. Les deux mécanismes restent inchangés dans
le moteur ; les jours source de sécurité restent préservés dans tous les essais.

La version retenue étend donc la protection persistante à **six références**
et le rapprochement du total industriel à **quatre références**, avec l'ajout
de 007923 aux listes ci-dessous. Les 19 calendriers de prévision complémentaire
et les 22 couples d'achats externes au délai source sont conservés.

### Pourquoi le saut initial de 001893 est excessif

Les 26 nouveaux achats de la référence sur cinq ans utilisent VD0910216A,
avec 28 jours de livraison et 24 jours ouvrés de traitement à réception.
Pourtant, le planificateur retient le maximum des offres, 56 jours, auquel il
ajoute le même traitement. Sa référence est ainsi de 88–90 jours contre
60–62 jours réellement exécutés, soit 28 jours d'écart.

Le 5 janvier, les besoins datés (64 185,528570 kg) et la réserve historique
(15 996,367520 kg), moins le disponible (9 561,336800 kg), déclenchent
70 620,559290 kg avant arrondi, puis 71 760 kg commandés. Le 7 janvier,
1 782,611278 kg supplémentaires sont arrondis à 23 920 kg. Ces quantités arrivent
physiquement les 2 et 4 février, avant leur libération les 6 et 10 mars.
Le stock physique atteint 95 680 kg ; la source donne 13 041,120 kg le 10 février.
Ce défaut était déjà présent avant l'extension de sécurité de 001757/002612.

L'alignement réduit le besoin net initial à **53 922,144709 kg**, mais celui-ci
dépasse encore deux standards (47 840 kg) : la première commande reste donc
71 760 kg. Le second achat est reporté de J6 à J44, sa réception de J34 à J72.
Le premier saut n'est pas résolu. Les entrées projetées du premier plan source
en janvier–février totalisent 64 300 kg (`Feuille1!H118:H125`), alors que le
premier nouvel achat simulé n'est disponible que le 6 mars. L'absence de carnet
initial 001893/1810 est une piste importante ; ces projections ne prouvent pas
à elles seules des réceptions exécutées. Les engagements `Extract_En_cours`
lignes 9–13 sont rattachés à 1820, et ne sont pas réaffectés arbitrairement.

L'essai `selected_offer_001893` déclare la même offre pour planifier et exécuter,
sans ajouter de nouvelle protection de sécurité ni changer les besoins.
Cette sélection fixe est une hypothèse de scénario : elle désactive les autres
offres en secours. Elle ne constitue pas une règle universelle sous incident.
Le fournisseur exécuté n'est d'ailleurs pas le moins cher à l'achat :
4,64 €/kg contre 4,40 €/kg pour l'offre à 56 jours. La logique historique trie
notamment les coûts de transport ; il ne faut pas la présenter comme une
sélection automatique au plus faible prix de matière.

### Pourquoi tester les règles existantes sur 007923

007923 ne présente pas cette incohérence de délai : le fournisseur VD0956464A,
utilisé dans les 24 nouveaux achats de cinq ans, est aussi l'offre à délai maximal
(15 jours contre 14). Planification et exécution utilisent 15 jours plus
6 jours ouvrés de traitement à réception. Le standard est 19 140 kg et le prix
FIA normalisé 1,82 €/kg ; l'autre offre porte sur 19 074 kg à 2,18 €/kg.

La référence donne un stock moyen aux photos de 20 039,16 kg, contre
45 627,94 kg source ; l'écart absolu moyen est de 25 755,51 kg en 2025 et
17 793,21 kg au dernier trimestre. Elle comporte 36 jours sans stock disponible.
Au 29 décembre : 39 901,71 kg source contre 7 819,80 kg simulés à la clôture
précédente.

Les 15 jours ouvrés de sécurité source sont présents mais leur protection
persistante n'est pas encore activée dans cette référence. Le complément des
autres usages est estimé à 90,73 % de I, auquel s'ajoutent les besoins propres.
Ce n'est pas une sous-estimation constante de 9,27 % : sur les semaines communes
du premier plan, le total reconstitué vaut 138 487,30 kg contre 146 965,23 kg source,
mais certains plans de fin d'année dépassent I.

L'essai `shared` applique les deux règles déjà présentes pour 001757, 002612
et 055703 : conserver la sécurité dans le stock projeté, puis reconstituer le
complément futur par semaine avec `max(I industriel − besoins propres, 0)`.
Il conserve les besoins propres excédentaires et les périodes non renseignées ;
il ne transforme pas les prévisions H en réceptions exécutées. La demande
physique estimée des autres usages, les jours sources et les offres restent
inchangés. Cet essai ne sépare pas l'effet individuel des deux mécanismes.

### Application effective avant ces essais

| Mécanisme | Périmètre de la référence sauvegardée |
|---|---|
| Prévisions complémentaires actualisées, dernière version connue | 19 couples article/site |
| Protection persistante de la sécurité source et complément de couverture | 055703, 039668, 708073, 001757, 002612 |
| Rapprochement hebdomadaire avec le total industriel I | 055703, 001757, 002612 à Avène |
| Principal et secours explicites | 001848 à Avène ; ne pas remplacer cette règle par une offre fixe |
| Délai fournisseur source et traitement à réception des achats externes | 22 couples réellement actifs dans les commandes de cette référence |

L'audit des **1 779 nouvelles commandes fournisseurs** de la référence retrouve
26 incohérences de délai, toutes sur 001893 (+28 jours). Un achat de secours
001848 a volontairement un délai plus court que le principal (+35 jours de
différence avec sa référence) : ce n'est pas le même défaut. Aucun autre
décalage n'est constaté dans ce calcul, sans généraliser ce constat aux incidents.

Les 19 prévisions ne sont pas les 29 stocks comparés : certaines paires ont
seulement leurs besoins propres, leurs engagements ou leurs transferts. La
comparaison rassemble 33 paires sources, dont 32 avec photos et 29 avec stock
simulé. Les quatre stocks simulés absents sont 007923/1430, 001893/1450,
002612/1450 et 029313/1430. Les intermédiaires 693055 et 773474 restent distincts
des achats externes ordinaires.

Les règles sont communes dans le code, mais leur activation reste déclarée dans
les scénarios. Leur extension n'est pas automatique à un PF, un intermédiaire
fabriqué ou un transfert interne : le total I peut déjà contenir des besoins
propagés par nomenclature. Une généralisation doit vérifier le périmètre de la
demande, les unités, les engagements initiaux et le rôle de chaque site.

[Audit indépendant de 007923](../../artifacts/testing/mrp_offer_alignment_20261001/oracle/007923_source_audit.json)
et [contrôle des entrées candidates](../../artifacts/testing/mrp_offer_alignment_20261001/oracle/candidates_preflight.json).
Les 1 848 lignes I de 007923, dont dix zéros explicites, sont rapprochées des
52 versions Excel. Sources : politique MRP ligne 25, FIA lignes 23–24,
`Extract_En_cours` ligne 19 et MRP `Feuille1!E203` pour le délai de réception.

## Fin 2025 : étendre la protection du stock partagé à 001757 et 002612

**Résultat : amélioration nette de 001757 et 002612, sans ajout de réceptions partielles ni modification des jours de sécurité.** Les deux nouveaux calculs de cinq ans ont terminé avec retour nul et empreintes inchangées (875,063 et 882,907 secondes). La variante `total_extension` est la meilleure des deux sur l'écart annuel de ces matières ; l'ancienne référence reste conservée pour comparaison.

| Écart absolu moyen aux photos 2025, kg | Référence | Sécurité partagée | Sécurité + besoins industriels totaux |
|---|---:|---:|---:|
| 001757 / année entière | 2 504,086 | 1 906,032 | **1 425,327** |
| 001757 / octobre–décembre | 4 276,469 | 2 549,027 | **1 275,801** |
| 002612 / année entière | 58 360,198 | 28 230,845 | **27 365,461** |
| 002612 / octobre–décembre | 68 019,345 | **34 202,691** | **34 202,691** |
| 055703 / année entière | 147,241 | 147,230 | 147,230 |
| 055703 / octobre–décembre | 119,403 | 113,826 | 113,826 |

Les écarts du dernier trimestre diminuent d'environ **70 % pour 001757** et **50 % pour 002612**. Pour ce dernier, le gain vient surtout de la sécurité persistante : le rapprochement du total I améliore légèrement certaines dates antérieures mais n'ajoute pas de gain au quatrième trimestre. Pour 001757, les deux mécanismes contribuent.

| Dernière photo, 29 décembre, stock physique en kg | Source | Référence simulée | Sécurité + besoins totaux |
|---|---:|---:|---:|
| 001757 / Avène | 9 368,378 | 4 498,613 | 7 824,444 |
| 002612 / Avène | 114 339,772 | 22 731,290 | 67 263,578 |
| 055703 / Avène | 933,345 | 979,698 | 960,989 |

Le résidu de **47 076 kg sur 002612** reste important : ces résultats ne justifient pas de déclarer sa calibration achevée ni d'augmenter arbitrairement la sécurité. Pour 055703, aucun paramètre d'achat n'a changé ; les 18,70848 kg supplémentaires consommés par la production expliquent le changement de stock final. L'écart annuel est pratiquement inchangé : ce n'est pas une nouvelle règle de calendrier validée pour cette matière.

### Disponibilité, service et effets sur les autres matières

Pour 002612, les jours à stock physique nul passent de **12 à zéro**, et ceux à stock disponible nul de **166 à zéro**, sur 2025. Le service simulé du PF268091 passe de **3 211 453 à 3 441 853 UN**, soit 230 400 UN de plus ; le reliquat de demande en fin d'année passe de 364 989 à 134 589 UN. La demande et le service du PF268967 sont inchangés. Les scénarios de demandes physiques des autres usages sont identiques ; leur consommation et la production sont contrôlées séparément.

Sur les cinq années simulées, la quantité totale livrée aux clients est identique ; la demande est rattrapée plus tôt. Aucun jour ne présente un arriéré client supérieur à celui de la référence dans les deux variantes.

Sur 29 couples comparables : **11 améliorent leur écart annuel, 12 restent identiques, 6 se dégradent légèrement**. Les six dégradations restent inférieures à 1,1 % sur cet indicateur : 001893/Avène (+158,078 kg de MAE), 029313 (+1,797 kg), 049371 (+36,763 kg), 099439 (+2,333 kg), 693055/Avène (+5,867 kg) et 426331 (+32,327 UN). Les unités ne sont pas additionnées pour fabriquer un score global. Ces effets aval accompagnent la production supplémentaire et restent visibles dans les courbes.

[Comparaison interactive, ouverte sur 001757](../../resultats/regroupement_001757_20260929/comparaison_mrp_securite_partagee.html) · [carte complète avec ce panneau](../../resultats/regroupement_001757_20260929/carte_mrp_securite_partagee.html) · [indicateurs annuels, dernier trimestre et service](../../artifacts/testing/mrp_year_end_20261001/analysis.json). Les autres panneaux et les deux suivis de lots de la carte complète restent historiques ; ils ne représentent pas les nouveaux calculs.

Étude isolée `mrp_year_end_20261001`, depuis la référence conservée du précédent essai. L'objectif est de rapprocher les stocks de fin d'année sans ajouter de réceptions partielles. **Le moteur n'est pas modifié** : deux graphes activent des mécanismes existants, en conservant les commandes et cartes antérieures.

Le premier candidat, `safety_extension`, applique à 001757/Avène et 002612/Avène la protection persistante déjà utilisée pour 055703 : garder la sécurité source dans le solde projeté, sans la consommer comme un besoin supplémentaire. La quantité est calculée avec la moyenne prévisionnelle globale existante et les **20 jours ouvrés sources**, puis combinée par maximum avec le complément de couverture. Cela ne réactive pas la protection sur besoins datés rejetée lors de l'essai précédent. Le second candidat, `total_extension`, ajoute uniquement le rapprochement hebdomadaire des besoins propres avec le total industriel I renseigné, comme pour 055703.

| Paramètre conservé | 001757 / Avène | 002612 / Avène |
|---|---:|---:|
| Fournisseur déjà utilisé par la référence | VD0951020A | VD0910216A |
| Prix FIA normalisé | 5,43 €/kg | 0,82 €/kg |
| Délai fournisseur | 84 jours | 35 jours |
| Traitement à réception | 13 jours ouvrés | 9 jours ouvrés |
| Standard de commande | 100 kg | 22 500 kg |
| Sécurité source | 20 jours ouvrés | 20 jours ouvrés |

La sélection explicite conserve les fournisseurs des 383 achats 001757 et des 42 achats 002612 de la référence sur cinq ans. Elle ne prouve pas une exclusivité industrielle. Les délais, stocks initiaux, hypothèses de demandes physiques des autres produits et nomenclatures restent identiques ; les consommations exécutées peuvent évoluer si la disponibilité permet davantage de production.

### Diagnostic avant essai

Les prévisions ne s'arrêtent pas au 31 décembre : l'horizon simulé reste de 364 jours et les versions MRP connues en automne portent déjà des besoins de 2026. Dans le plan du 28 décembre, I projeté en 2026 totalise 30 720 kg pour 001757, 312 131,346 kg pour 002612 et 2 135,6 kg pour 055703. Les quantités proviennent d'une seule version, jamais de la somme des plans successifs.

La référence ne déclare pas de protection persistante pour les deux premières matières. Le 26 octobre, la sécurité issue du taux global et des 20 jours ouvrés représente environ 2 977 kg pour 001757 et 42 333 kg pour 002612 ; l'exigence complémentaire de réserve du plan vaut respectivement environ 126 kg et zéro. Une partie de la cible est absorbée par les besoins déjà présents dans la couverture : cela ne maintient pas nécessairement cette sécurité disponible au fil du plan. Les champs historiques `safety_floor_qty` et `target_stock_qty` sont ceux du périmètre propre ; ils ne doivent pas être présentés comme toute la protection du stock industriel partagé.

La réconciliation du total I doit être examinée séparément. La quote-part de 72,18 % de 001757 n'est **pas** une preuve de 27,82 % de besoins totaux manquants : les besoins propres s'y ajoutent. Sur les semaines renseignées du plan du 26 octobre, le modèle représente environ 27 752 kg contre 30 480 kg sources ; pour 002612, le rapprochement se situe déjà autour de 100 %. La différence de répartition hebdomadaire peut compter même lorsque le total sur l'horizon est proche.

Pour la dernière photo de 002612, `Stocks!E1393 = 114 339,772 kg`. Dans le plan du 28 décembre, `Feuille1!J52500 = 98 089,772 kg` et `J52501 = 16 250 kg` disponibles plus tard : leur somme égale le stock physique. Les 16 250 kg ne constituent pas une réception future à ajouter. Le stock simulé comparable est de 22 731,290 kg. Pour 001757, la dernière photo vaut 9 368,378 kg contre 4 498,613 kg simulés. Pour 055703, le déficit se concentre sur certaines dates de réception ; le dernier stock simulé de 979,698 kg dépasse légèrement la photo de 933,345 kg.

[Protocole des deux calculs de cinq ans](../../artifacts/testing/mrp_year_end_20261001/plan.json) · [lecture des sources](../../artifacts/testing/mrp_year_end_20261001/source_review.json) · [contrôle indépendant des graphes et des 3 549 lignes I ajoutées](../../artifacts/testing/mrp_year_end_20261001/independent_preflight.json).

Précision d'unité : 002612/Avène est déjà en **KG** dans le Flow MRP ; 001757 et 055703 y sont en **G**. Les lectures appliquent l'unité de chaque ligne. Aucune conversion globale supplémentaire n'est effectuée. Le diagnostic complémentaire 055703 ne permet pas d'identifier une nouvelle règle commune d'anticipation : les occurrences H de 300 kg restent souvent 40 à 50 jours ouvrés avant le manque théorique, mais H, les engagements fermes et le traitement à réception ne sont pas suffisamment distingués pour en déduire une sécurité à augmenter. [Calcul contrefactuel et limites](../../artifacts/testing/mrp_year_end_20261001/source_055703_timing.json).

### Résidu 002612 : les achats ne sont pas l'unique explication possible

Le candidat reçoit 720 000 kg en 2025 et consomme 806 258,059 kg, dont 804 036,427 kg pour les autres usages estimés. Si cette consommation représentait exactement la consommation industrielle, le stock source final impliquerait environ 767 076 kg d'entrées, soit 47 076 kg de plus. C'est une identité **conditionnelle**, pas une mesure de livraisons manquantes.

Les 52 versions montrent 16 apparitions ou augmentations de J futur, en évitant de recompter les répétitions, mais ce registre n'est pas exhaustif : des hausses physiques de 28 991 kg le 25 août, 38 103 kg le 13 octobre et 12 312 kg le 3 novembre ne sont accompagnées d'aucun nouveau J futur visible. La somme J concorde avec 51 photos sur 52 ; le plan du 2 mars présente un désaccord de 13 026 kg avec la photo suivante. Ni le total de J apparus ni les seules hausses de stock ne reconstituent donc toutes les entrées.

Une reconstruction très restrictive du 6 octobre au 29 décembre, sans livraison masquée et avec des lots FIA supposés sur les hausses non expliquées, donnerait 112 917 à 119 367 kg de sorties nettes, contre 157 123 kg consommés dans la simulation. Cela illustre une autre explication possible du résidu : des consommations estimées trop élevées. **Ce n'est ni un intervalle de confiance ni une preuve permettant de réduire la demande physique.** Des entrées masquées par des consommations peuvent invalider ce calcul. Aucun paramètre de consommation n'est ajusté sur cette hypothèse. [Épisodes, cellules, bornes et hypothèses détaillées](../../artifacts/testing/mrp_year_end_20261001/source_002612_balance.json).

Validation de l'essai : les CSV des deux nouveaux calculs et la navigation de la carte complète passent la toolbox. Les preuves de 28 tests ciblés et du doctor existants sont réutilisées après vérification des empreintes, puisque le moteur est inchangé ; elles ne sont pas présentées comme de nouveaux tests exécutés pour cet essai. La contre-vérification indépendante contrôle 3 285 bilans physiques quotidiens, 10 950 contrôles de sécurité et 7 186 fenêtres de rapprochement I. Le navigateur vérifie 4 377 valeurs de stock, 117 valeurs filtrées sur le dernier trimestre et 64 cellules MRP, sans erreur JavaScript. [Contre-vérification](../../artifacts/testing/mrp_year_end_20261001/independent_final_review.json) · [preuves regroupées](../../artifacts/testing/mrp_year_end_20261001/native_final/gate-0b36ba13940f41a99e8c37625671560c/manifest.json).

## Essai de sécurité sur besoins datés et vérification des arrondis

**Résultat : ne pas retenir cette option comme nouvelle référence.** Les trois simulations de cinq ans ont terminé normalement. Le témoin reproduit les 38 CSV précédents à l'octet près. Sur les 29 couples article/site comparables en 2025, aucun n'améliore son écart moyen absolu aux photos ; 055703 se dégrade et les 28 autres restent identiques à cette précision. Les consommations et le service client sont inchangés dans ces essais.

| Écart moyen absolu aux 52 photos hebdomadaires | Référence | Protection par besoins datés |
|---|---:|---:|
| 055703 / Avène | 147,241 kg | 151,025 kg |
| 039668 / Avène | 135,971 kg | 135,971 kg |
| 708073 / Gien | 3 969,257 kg | 3 969,257 kg |

Le stock physique 055703 au 29 juin reste à 879,585 kg dans les trois calculs, contre 1 170,790 kg dans la photo du 30 juin. Dix nouvelles commandes de 300 kg et 3 300 kg reçus dans l'année, engagement initial compris, sont conservés. La nouvelle règle décale quelques commandes sans résoudre l'écart de juin. Pour 039668, la moyenne sur photos masque même deux jours supplémentaires à stock physique nul : trois au lieu d'un. La comparaison hebdomadaire ne suffit donc pas à vérifier tous les effets quotidiens.

Le 6 avril, le nouveau calcul augmente le besoin net à lancer de 22,919911 à 132,985770 kg ; **les deux donnent toujours 300 kg après arrondi**, le même jour. Le complément de couverture vaut zéro sur 361 des 365 jours de 055703 : il n'est pas la cause principale de ce faible effet. Les fenêtres futures intégralement connues sont présentes 226 jours sur 365 ; les 139 autres lendemains conservent explicitement la protection historique. L'essai ne démontre ni que toutes les sécurités datées sont inutiles, ni que la moyenne explique à elle seule le système réel.

[Comparaison interactive de l'essai](../../resultats/regroupement_001757_20260929/comparaison_mrp_securite_besoins_dates.html) · [résultats numériques](../../artifacts/testing/mrp_dated_safety_20261001/analysis.json) · [reproduction du témoin](../../artifacts/testing/mrp_dated_safety_20261001/baseline_equivalence.json). L'option reste expérimentale, désactivée dans la référence conservée. Les anciens panneaux et suivis de lots de la carte complète gardent leurs données historiques ; seuls les panneaux de comparaison présentent ces trois nouveaux calculs.

Contrôles exécutés : 28 cas ciblés en mémoire, qualification des CSV des trois calculs et navigation hors ligne de la carte complète. La contre-vérification indépendante contrôle notamment 7 300 décisions quotidiennes et 75 920 niveaux de protection reconstruits sans les helpers de production. Le rapprochement navigateur porte sur 4 377 valeurs de stock, 90 cellules du tableau de sécurité et 2 190 points des nouvelles courbes, sans erreur JavaScript. Ces contrôles vérifient le calcul et son affichage ; l'essai reste négatif pour la calibration industrielle. [Contre-vérification](../../artifacts/testing/mrp_dated_safety_20261001/independent_final_review.json) · [rapport navigateur détaillé](../../artifacts/testing/mrp_dated_safety_20261001/view_2ea73c62/report.json).

Protocole `mrp_dated_safety_20261001` : trois calculs distincts de 1 825 jours à partir du dernier candidat 055703 utilisant tout le besoin MRP renseigné. Le témoin conserve la protection par moyenne ; le deuxième modifie uniquement 055703/Avène ; le troisième applique la même modification à 055703/Avène, 039668/Avène et 708073/Gien. Les prévisions de ces deux dernières matières restent celles de la référence : le test ne leur ajoute pas simultanément le total industriel. [Protocole et commandes](../../artifacts/testing/mrp_dated_safety_20261001/plan.json).

Pour chaque clôture projetée `t`, l'option `dated_requirements_with_coverage` protège :

`P(t) = max(quantité fixe de sécurité source, somme des besoins datés dans ]t ; t + N jours ouvrés sources])`.

Le calendrier lundi–vendredi détermine la borne finale ; les besoins alloués aux samedis et dimanches à l'intérieur de cette fenêtre ne disparaissent pas. La protection débute le lendemain de la décision. Les besoins propres sont propagés par la BOM avant le rapprochement avec le total industriel et avant ce calcul de protection. Il n'y a ni consommation supplémentaire, ni cumul de la protection de chaque jour comme s'il s'agissait de nouvelles sorties.

La fenêtre doit être intégralement renseignée dans les prévisions connues à la décision. Les valeurs nulles explicites comptent comme renseignées ; une période absente, une version encore inconnue ou une fin d'horizon ne devient pas un besoin industriel nul. Dans ces cas, l'option conserve explicitement le plancher historique. Le complément historique de couverture reste activé à sa date précédente ; son maximum avec P(t) est utilisé, jamais leur somme. Les métadonnées et les traces distinguent fenêtres renseignées et retour à la moyenne.

### L'arrondi au multiple supérieur existe déjà pour les commandes

Dans la voie d'achat agrégée de 055703, le moteur déduit d'abord stocks et engagements du besoin. Les propositions futures peuvent encore être au besoin net exact ; lors du lancement, la somme à émettre est arrondie au standard supérieur, dans la limite de la capacité représentée. Avec une capacité suffisante et un standard de 300 kg :

| Besoin net à commander | Commande émise |
|---:|---:|
| 299 kg | 300 kg |
| 300 kg | 300 kg |
| 305 kg | 600 kg |
| 600 kg | 600 kg |
| 601 kg | 900 kg |

305 kg de besoin **brut** avec 5 kg déjà disponibles, ou engagés et affectés, ne laisse que 300 kg nets : la commande est alors de 300 kg. Les propositions futures de 055703 ne sont donc pas identiques à des commandes déjà émises. Appliquer le multiple dès la proposition serait une expérience distincte ; le présent test de sécurité ne modifie pas cet arrondi. La quantité standard de la FIA ne prouve pas seule qu'un multiple est contractuellement obligatoire : il s'agit de la convention actuelle, compatible avec les lots 055703 représentés. [Audit de l'arrondi](../../artifacts/testing/mrp_dated_safety_20261001/rounding_review.json).

### Les arrondis visibles dans les plans industriels

Lecture des 53 398 lignes de `Flow_Data_MRP_results.xlsx`, versions du 5 janvier au 28 décembre 2025. Les valeurs H de ces trois matières sont exprimées en grammes dans la source et converties ici en kg. **Les comptes ci-dessous sont des cellules dans 52 versions successives, pas des commandes distinctes ni des achats annuels.** Toutes les semaines projetées des versions 2025 sont incluses, y compris celles de 2026.

| Matière | Standard FIA | Quantités positives H dans les plans |
|---|---:|---|
| 055703 / Avène | 300 kg | 187 cellules à 300 kg ; 2 à 450 kg ; 52 inférieures à 300 kg |
| 039668 / Avène | 450 kg | 55 cellules à 450 kg ; 24 à 300 kg ; 54 autres inférieures à 450 kg |
| 708073 / Gien | 5 000 kg | 32 cellules à 5 000 kg ; 209 à 10 000 kg |

Pour 055703, **chacune des 52 versions comporte exactement une dernière entrée positive inférieure au standard**. Exemples : `Feuille1!H494`, plan du 5 janvier, semaine du 15 juin, 101,564999 kg ; `H52811`, plan du 28 décembre, semaine du 21 juin 2026, 135,254979 kg. Les exceptions à 450 kg se trouvent en `H1441` et `H3470`. Pour 039668, la dernière entrée positive est également inférieure à 450 kg dans les 52 versions, mais 26 autres entrées inférieures précèdent ces dernières entrées. Pour 708073, les 108 cellules positives visant une semaine de 2025 sont toutes de 10 000 kg, soit deux standards.

Cela justifie d'étudier séparément le regroupement des besoins, l'arrondi des commandes émises et le traitement du dernier approvisionnement projeté. Le motif de fin de plan est observé ; son mécanisme ERP reste à établir. H représente des entrées hebdomadaires prévues et agrégées, pas des réceptions exécutées. Des multiples ne prouvent pas à eux seuls un `ceil(besoin net / standard)` sans reconstruire l'état connu à la décision. [Audit source avec cellules, fournisseurs, prix, délais et empreintes](../../artifacts/testing/mrp_dated_safety_20261001/source_rounding_review.json).

## 055703 : distinguer consommation et calendrier des réceptions

Cette contre-analyse utilise le candidat `mrp_055703_full_needs_20261001` sans le modifier ni recalculer une nouvelle trajectoire. Elle reprend directement les deux classeurs sources, les 53 photos (ouverture incluse), les 52 versions MRP et les registres du calcul. [Calcul reproductible](../../artifacts/testing/mrp_055703_balance_20261001/audit.py) · [résultats détaillés](../../artifacts/testing/mrp_055703_balance_20261001/analysis.json) · [preuves et limites](../../artifacts/testing/mrp_055703_balance_20261001/manifest.json).

**Le résidu de juin indique surtout un décalage des approvisionnements, pas une consommation physique à majorer de 81 % à 100 %.** Les sources présentent sept hausses importantes avant le 30 juin, chacune accompagnée de 300 kg en J futur dans le même plan : matière déjà présente, en attente de disponibilité. Sur l'année, onze épisodes sont corroborés. La petite hausse de 0,22 kg au 29 décembre ne constitue pas une livraison standard.

Ces épisodes permettent une reconstruction conditionnelle, pas une identification certaine de chaque livraison. Sous l'hypothèse d'un arrivage de 300 kg par épisode et sans mouvement supplémentaire masqué :

`sorties nettes reconstituées = stock initial + réceptions reconstituées − stock photographié`

Les sorties nettes peuvent inclure consommation, transfert, perte ou correction. La colonne H des plans reste une prévision et n'est jamais utilisée comme preuve de réception exécutée.

| Cumul au 30 juin, simulation à la clôture du 29 juin | Sources / reconstruction conditionnelle | Simulation |
|---|---:|---:|
| Stock initial | 569,805 kg | 569,805 kg |
| Réceptions physiques | 2 100 kg, sept épisodes | 1 800 kg, six réceptions |
| Sorties nettes / consommations | 1 499,015 kg | 1 490,220 kg |
| Stock physique final | 1 170,790 kg | 879,585 kg |

Ainsi, `291,205 kg de différence de stock = 300 kg de différence d'entrées − 8,795 kg de différence de sorties`. L'écart de sorties représente environ 0,59 % des sorties nettes reconstituées. La proximité est un indice fort, mais dépend de l'hypothèse d'arrivages et ne prouve pas l'absence de mouvements masqués.

À la dernière photo du 29 décembre, les réceptions cumulées reconstituées et simulées sont toutes deux de 3 300 kg. Les sorties nettes sources sont de 2 936,460 kg, contre 2 890,107 kg consommés en simulation ; les stocks valent respectivement 933,345 et 979,698 kg. L'écart de sorties est d'environ 1,58 %. Les volumes cumulés annuels sont donc proches, tandis que la répartition des réceptions au cours de l'année reste différente.

### Ce que signifie réellement la part de 81,07 %

La part provient du premier plan connu : 1 799,35 kg de besoins industriels sur l'horizon commun et 340,5691212 kg de besoin théorique déduit de la prévision du PF et de la BOM. Le résidu vaut 1 458,7808788 kg, soit 81,0726583933 %. C'est une **hypothèse de répartition des usages**, pas un paramètre de l'ERP ni une mesure de consommation. L'horizon commun contient des semaines sans ligne : il ne faut pas présenter cette fraction comme une mesure annuelle exhaustive.

Depuis la correction précédente, les futurs achats de 055703 utilisent le total industriel renseigné, réconcilié avec les besoins propres. Les sorties physiques des autres usages gardent cette estimation et la sélection causale des versions. Le présent bilan ne justifie pas de les remplacer mécaniquement par 100 % de I : cela augmenterait les sorties alors que leur cumul est déjà proche de la reconstruction source.

### Disponibilité : une semaine n'est pas une date d'exécution exacte

`J25530` place les 300 kg du plan du 29 juin dans **la semaine commençant le 6 juillet**. Le 6 juillet ne prouve pas une libération exactement ce jour-là. L'ancien commentaire « 6 juillet contre 14 juillet » donnait une précision quotidienne excessive. Le modèle libère le 14 juillet après réception le 25 juin et treize jours lundi–vendredi. Avec la convention de buckets dimanche–samedi, une réception industrielle le 24 juin suivie de treize jours ouvrés aboutirait au 11 juillet, dans le bucket source. Les photos hebdomadaires ne donnent pas le jour exact de réception.

La convention de treize jours est aussi cohérente avec l'engagement initial `Extract_En_cours.xlsx`, ligne 69 : réception prévue le 17 janvier, disponibilité prévue le 5 février. Les autres épisodes annuels sont compatibles avec treize jours ouvrés pour au moins une date de réception dans leur intervalle photographique. **Aucune correction automatique du délai qualité à sept jours n'est justifiée.**

### Deux précautions sources importantes

- Plan du 2 mars : `J8465 + J8467 = 1 006,945002 kg`, contre 746,790002 kg sur la photo du 3 mars (`Stocks!E1374`). Le total MRP correspond à la photo du 10 mars. Ce décalage de 260,155 kg reste signalé ; le lot de 300 kg n'est pas compté deux fois. Les 51 autres rapprochements hebdomadaires concordent.
- Les photos des 28 juillet, 4 août, 11 août et 18 août restent à 786,625001 kg, alors que I en semaine courante conserve 65,6 kg. Un besoin MRP courant n'est donc pas une consommation exécutée. Cette période est cohérente avec une activité réduite ou arrêtée ; elle ne permet pas, seule, d'identifier chaque mouvement.

La prochaine correction du modèle doit porter sur le déclenchement daté des achats et être testée contre ces cumuls, en conservant les consommations et les sécurités sources. Le bilan ne justifie pas d'ajouter arbitrairement un lot ni d'injecter les réceptions reconstituées comme commandes fermes.

### Piste de déclenchement identifiée, encore à tester

Le simulateur transforme les trente jours ouvrés de sécurité en une quantité calculée avec une **moyenne prévisionnelle sur 120 jours**. Cette moyenne peut masquer la concentration des besoins à court terme. Le 16 mars (J74), une révision fait passer la protection d'environ 491,77 kg au 12 mars à 372,84 kg, alors que le total des besoins industriels sur l'horizon exporté augmente d'environ 1 876,65 à 2 182,64 kg. Ces deux mesures ne portent pas sur la même fenêtre : la baisse de la moyenne proche n'est donc pas, en soi, une erreur de somme.

Le 5 avril, la protection reste à 372,01 kg et ne déclenche pas d'achat. Le 6 avril, une nouvelle version fait passer le taux moyen de 9,0733 à 10,2762 kg/jour et la protection à 411,05 kg. Un besoin net de 22,9199 kg déclenche alors une commande standard de 300 kg, reçue le 27 avril. Or le plan industriel du 16 mars porte déjà une entrée H de 300 kg pour la semaine du 23 mars (`Feuille1!H10460`). Cette entrée demeure une prévision, pas un ordre identifié.

**Hypothèse commune à éprouver ensuite :** préserver les trente jours ouvrés sources, mais comparer la protection fondée sur une moyenne à une protection calculée sur les besoins réellement datés de la fenêtre concernée. Le scénario industriel et le simulateur n'ont déjà plus le même stock à ces dates : cette observation ne suffit pas à démontrer que la moyenne sur 120 jours est l'unique cause, ni que sa suppression améliorera les autres matières. Aucune modification de cette règle n'est appliquée dans le présent diagnostic.

## 055703 : utiliser le total industriel dans la planification des achats

Demande utilisateur : prendre en compte **100 % des besoins MRP sources de 055703 à Avène**. La règle commune est activée pour ce seul couple dans l'essai `mrp_055703_full_needs_20261001`, à partir du scénario de couverture conservée précédent. Il s'agit des besoins prévus colonne I, pas d'ordres industriels injectés dans le modèle.

Pour chaque semaine renseignée de la version connue à la date du calcul, après propagation de nos besoins de fabrication :

`complément de planning = max(total industriel I − besoins propres déjà datés, 0)`

`besoins retenus = besoins propres + complément de planning`

Le complément remplace les futurs besoins « autres usages » estimés sur cette semaine. Il ne s'ajoute pas à leur ancienne quote-part de 81,0726583933 %. Ainsi, un total source de 100 kg et 30 kg de besoins propres donnent 70 kg de complément et **100 kg à planifier**, pas 130 ou 180 kg. Lorsque nos besoins propres dépassent le total industriel, ils sont conservés et le dépassement reste visible. Ce cas n'est pas présenté comme une égalité à la source.

Les périodes sont rapprochées **par semaine**, pas par maximum quotidien : un besoin propre de 100 kg concentré sur un seul jour est déjà inclus dans une semaine source de 100 kg. La partie restante d'une semaine est proratisée selon la répartition uniforme existante ; le fichier ne donne pas le calendrier quotidien réel. La semaine courante reste figée, les révisions remplacent les prévisions futures et aucune version future n'est utilisée avant sa date de connaissance. Une semaine absente conserve les besoins reconstruits précédents ; une valeur I égale à zéro reste une donnée distincte. Pour 055703, le contrôle direct du classeur compte **52 versions, 1 725 lignes futures I, dont 10 zéros explicites**.

La moyenne de besoins utilisée pour calculer sécurité et couverture suit le plan ainsi réconcilié. Les jours et quantités fixes de sécurité, prix, fournisseurs, standards de commande, délais FIA et stocks initiaux restent inchangés. Les arriérés physiques déjà dus restent comptés séparément ; leur éventuelle inclusion dans I n'est pas identifiable dans ces extractions.

**La correction porte sur les besoins de planification, pas sur une consommation physique supplémentaire.** Les fabrications consomment leurs composants et les autres usages suivent leur scénario documenté. Transformer le complément de planning en sortie physique créerait un double compte ou modifierait le périmètre sans preuve. Les effets sur stocks et surstock doivent donc être mesurés par la simulation, même si les courbes de besoins sont désormais cohérentes avec les sources.

### Résultats de la correction sur 2025

[Comparaison interactive](../../resultats/regroupement_001757_20260929/comparaison_mrp_055703_besoins_complets.html) · [carte complète](../../resultats/regroupement_001757_20260929/carte_mrp_055703_besoins_complets.html) · [protocole reproductible](../../artifacts/testing/mrp_055703_full_needs_20261001/plan.json).

| Indicateur 055703 / Avène | Avant | Besoins industriels complets |
|---|---:|---:|
| Écart absolu moyen aux 52 photos de stock physique | 205,14 kg | **147,24 kg** |
| Stock simulé à la clôture du 29 juin, pour la photo du 30 juin | 579,59 kg | **879,59 kg** |
| Écart à la photo du 30 juin : 1 170,79 kg | −591,20 kg | **−291,20 kg** |
| Réceptions physiques annuelles, engagements initiaux inclus | 3 300 kg | 3 300 kg |
| Stock physique simulé au 31 décembre | 979,70 kg | 979,70 kg |

L'écart moyen diminue de **28,22 %**. Le gain provient du calendrier des réceptions, sans augmentation du volume annuel reçu. Les consommations 2025 restent identiques : 70,1568 kg pour le produit étudié et 2 819,950287 kg pour les autres usages estimés. Le service client est inchangé. Sur les 29 couples comparables, seul l'écart de 055703 change ; les 28 autres restent identiques.

Le lot de 300 kg qui explique le gain de juin est lancé le **4 juin au lieu du 11 juin**, reçu physiquement le **25 juin au lieu du 2 juillet**, et disponible le **14 juillet au lieu du 21 juillet**. Les 300 kg supplémentaires à la clôture du 29 juin sont donc en attente de disponibilité qualité. Les achats nouveaux restent **10 commandes de 300 kg**, soit 3 000 kg commandés et reçus sur 2025, auxquels s'ajoute une réception de 300 kg issue des engagements initiaux. Le calendrier de disponibilité reste imparfait : la source situe 300 kg déjà présents au 29 juin comme disponibles dans la semaine commençant le 6 juillet, sans date d'exécution quotidienne certaine.

Validation : 14 tests ciblés en mémoire, deux simulations de cinq ans qualifiées, oracle indépendant sur 1 825 décisions et 1 772 fenêtres hebdomadaires, puis navigateur hors ligne (2 918 valeurs de stock et 294 valeurs du graphique de projection rapprochées des exports). Dans 162 fenêtres, les besoins propres dépassent I : le maximum est conservé et ce désaccord reste explicite. [Bilan des preuves et limites](../../artifacts/testing/mrp_055703_full_needs_20261001/manifest.json).

Le stock de juin est mieux reproduit, mais il manque encore environ **291 kg** par rapport à la photo source. Reprendre tout le besoin prévisionnel ne démontre pas que toutes les conventions industrielles de déclenchement, d'engagement et de réception sont retrouvées. L'essai reste distinct du nominal. Les deux calculs de 1 825 jours ont terminé avec un code retour nul, en environ 58 minutes chacun sur cette exécution ralentie ; cela n'est pas un benchmark de performance comparable au passage précédent. Les 38 CSV du témoin sont identiques octet par octet à la référence conservée.

## Essai suivant : conserver la couverture en maintenant la sécurité

La protection de sécurité seule avait supprimé une partie de la couverture historique et retardé les achats de 708073. Le nouvel essai `mrp_coverage_floor_20261001` teste donc une règle commune sur 055703/Avène, 039668/Avène et 708073/Gien : **conserver le plus grand des deux niveaux, sans les additionner**. Il reste un candidat explicite, pas une règle ERP démontrée ni un remplacement du nominal.

Au jour du calcul `d`, le complément historique `C` est la cible de couverture moins les besoins physiques déjà représentés jusqu'à `d + couverture`, avec un minimum de zéro. La sécurité `S` conserve les jours ouvrés et la quantité fixe sources. Elle s'applique dès `d + 1` ; le complément historique garde son échéance `d + délai`. Après activation des deux, le niveau protégé est `max(S, C)`. Avant, seul le niveau déjà activé s'applique. Le calcul déduit une seule fois le stock disponible et les engagements ; cette protection ne devient jamais une consommation de matière.

Le témoin reproduit l'ancien essai à protection seule sur les trois couples. Les deux nouveaux calculs durent 1 825 jours, avec les mêmes prévisions, parts des usages partagés, stocks, sécurités, offres fournisseurs, délais FIA fixes et arrondis de commande. Le seul changement des graphes est le mode de protection des trois couples. La validation industrielle reste limitée aux photos et plans 2025 ; les années après les dernières prévisions ne valident pas une calibration sur cinq ans.

[Nouvelle comparaison interactive](../../resultats/regroupement_001757_20260929/comparaison_mrp_couverture_securite.html) · [carte complète](../../resultats/regroupement_001757_20260929/carte_mrp_couverture_securite.html) · [protocole et commandes](../../artifacts/testing/mrp_coverage_floor_20261001/plan.json).

Résultats 2025, écart absolu moyen du stock physique aux 52 photos, clôture de la veille :

| Article / site | Couverture historique (kg) | Sécurité seule, essai précédent (kg) | Couverture conservée et sécurité (kg) |
|---|---:|---:|---:|
| 055703 / Avène | 308,34 | 205,14 | 205,14 |
| 039668 / Avène | 141,27 | 135,97 | 135,97 |
| 708073 / Gien | 3 969,26 | 6 177,34 | 3 969,26 |

La régression de 708073 est corrigée : **35 à 0 jours de stock disponible nul**, réceptions annuelles **20 000 à 25 000 kg**, consommation propre **13 677,664 à 15 387,372 kg**. Au 4 avril (J93), le stock disponible est inchangé à 4 416,778811 kg ; la sécurité est 2 000 kg, le complément historique 4 406,584316 kg, activé à J128. Un besoin net de 706,787243 kg retrouve une commande standard de **5 000 kg**, avec réception physique à J121 et disponibilité à J128. Le service des PF reste identique.

**Aucun progrès supplémentaire sur l'écart moyen aux photos de 055703 ou 039668** avec cette correction. Les trajectoires de 055703 sont identiques ; pour 039668, une réception avance d'un jour (J99 à J98), ce qui modifie trois clôtures quotidiennes sans changer cet indicateur. Le creux de juin de 055703 reste présent : son complément historique est déjà inférieur à la sécurité à cette période. Le présent résultat répare la perte de couverture de 708073, sans démontrer une meilleure reconstruction des achats industriels sur toutes les matières. Le témoin conserve ses **38 CSV strictement identiques** à l'essai précédent.

Le contrôle ne se limite pas aux trois articles : parmi les **29 couples comparables**, trois écarts de stock diminuent, sept augmentent et dix-neuf restent identiques par rapport à la sécurité seule. La reprise des consommations de 708073 modifie la production et les stocks liés, sans changer le service client annuel. Par exemple, l'écart de 268967 au dépôt passe de 318 449 à 413 811 UN ; celui de 344135/Gien, de 420 596 à 564 996 UN. Les améliorations concernent 708073, 734545 et 773474. **La restauration de la couverture n'est donc pas une amélioration générale de calibration** ; conserver cet essai séparé, et ne pas additionner des erreurs exprimées dans des unités différentes.

### Autre cause identifiée sur 055703 : besoins projetés incomplets à court terme

Les besoins « autres produits » représentent une fraction fixe du besoin industriel, estimée sur le premier plan : **81,0726583933 %** pour 055703. La différence est censée être apportée par les fabrications de 268091. Or, après déduction des stocks et engagements de PF, notre planning ne place aucun besoin propre sur les fenêtres suivantes. La projection matière reste donc inférieure au total industriel, même lorsque la consommation cumulée passée est proche.

Comparaison sur les mêmes semaines, de la semaine suivante à sept semaines après la date du plan, semaine courante exclue :

| Plan connu | Besoins MRP sources (kg) | Besoins projetés du simulateur (kg) | Cellules sources |
|---|---:|---:|---|
| 4 mai 2025 | 613,200 | 497,138 | Feuille1!I17536:I17542 |
| 18 mai 2025 | 602,400 | 488,382 | Feuille1!I19530:I19536 |
| 1er juin 2025 | 684,200 | 554,699 | Feuille1!I21539:I21545 |
| 29 juin 2025 | 381,800 | 309,535 | Feuille1!I25530:I25533 ; semaines sans ligne omises |

Ces valeurs proviennent du `run_transfer` conservé de l'essai précédent et de `Flow_Data_MRP_results.xlsx`. La fraction initiale vient de `1458,7808788 / 1799,35`, avec 340,5691212 kg théoriques attribués au PF étudié. Son statut reste `hypothesis_only`. Une fraction correcte sur l'horizon initial ne garantit pas une répartition correcte à chaque date.

La source confirme aussi une réception physique avant fin juin : le plan du 29 juin porte 870,790001 kg immédiatement disponibles (`J25529`) et 300 kg déjà présents mais disponibles le 6 juillet (`J25530`). Leur total, **1 170,790001 kg**, correspond à la photo du 30 juin (`Stocks!E417/H417`). Dans l'ancien essai, le lot commandé le 11 juin arrive physiquement le 2 juillet et devient disponible le 21 juillet. Une réception prévue H n'est pas une preuve de commande ferme identifiée ; les révisions successives de H ne permettent pas d'affirmer qu'il s'agit du même ordre.

La prochaine hypothèse à éprouver porte donc sur la **réconciliation des besoins industriels agrégés avec les besoins propres et les autres usages**, en séparant prévision d'achat et consommation physique. Ne pas augmenter les jours de sécurité ni ajouter une seconde consommation pour compenser cette différence. Le présent essai de couverture ne modifie pas cette décomposition.

Contre-vérification sur les mêmes quatre fenêtres de mai/juin : 039668 ne reconstitue que **82,8575466251 %** des besoins sources et 708073 **38,6267607778 %**, exactement leurs parts fixes « autres produits ». Aucun besoin BOM propre ne complète ces fenêtres. Au plan du 1er juin, cela donne respectivement **322,482 / 389,200 kg** (`Feuille1!I21470:I21476`) et **1 483,849 / 3 841,504 kg** (`Feuille1!I21914:I21918`). Ce constat est commun aux trois références ; il ne démontre pas que leur sécurité est insuffisante.

Une règle candidate serait de rapprocher, à chaque semaine et millésime, le besoin industriel total du besoin propre simulé : complément de **planning** `max(0, total industriel − propre simulé)`. Elle n'est pas encore appliquée. Lorsque le besoin propre dépasse le total industriel, le désaccord doit rester visible ; aucune consommation négative ne doit être créée. Utiliser ce total pour acheter tout en conservant des consommations physiques plus basses pourrait créer du surstock : la cohérence entre le périmètre des prévisions et celui des consommations doit être testée conjointement. Les H restent des résultats de comparaison, sans injection dans les achats simulés.

## Choix courant : délai prévisionnel fournisseur fixe

Décision utilisateur : suspendre l'estimation des avances/retards et retenir le **délai prévisionnel FIA du fournisseur choisi**, sans tirage Erlang ni décalage empirique pour les nouvelles livraisons fournisseurs du MRP daté. Le traitement à réception reste une étape séparée ; les sécurités sources sont conservées.

Pour poursuivre cette étude, reprendre la commande `commands.source` du [plan reproductible](../../artifacts/testing/empirical_delivery_20261001/study/plan.json), avec `--supplier-delivery-mode source` et un nouveau dossier de sortie. Le calcul `study/source` existe déjà sur 1 825 jours : il constitue la base retenue pour la suite. Les anciens scénarios et le défaut historique du moteur ne sont pas modifiés par cette décision documentée. La couverture de planification conserve encore sa convention précédente ; ce choix porte sur le délai physique fournisseur, pas sur une révision des autres règles MRP.

Les analyses de variabilité ci-dessous restent des travaux exploratoires conservés ; leur loi empirique n'est plus la règle retenue pour poursuivre la comparaison.

## Essai général : actualiser les besoins complémentaires des 19 couples concernés

[Comparaison interactive de toutes les références](../../resultats/regroupement_001757_20260929/comparaison_mrp_revisions_generalisees.html) · [carte complète](../../resultats/regroupement_001757_20260929/carte_mrp_revisions_generalisees.html) · [plan reproductible](../../artifacts/testing/mrp_all_revisions_20261001/plan.json).

À la demande utilisateur, la règle d'actualisation des besoins futurs a été appliquée aux **quinze couples restés figés**, en conservant les quatre séries déjà révisées. Le candidat contient 19 séries versionnées et aucune ligne complémentaire fixe. Les 478 anciennes lignes des quinze couples sont remplacées par 780 versions / 27 072 lignes futures, toutes rapprochées directement du fichier MRP. Prix, sécurités, stocks initiaux, fournisseurs, standards, engagements initiaux et délais prévisionnels fixes restent identiques. **Cet essai ne remplace pas automatiquement le point de départ.**

La règle reste commune : dernière version connue pour le futur, semaine courante figée selon la dernière version antérieure, horizon de planification de 52 semaines. Les parts estimées des autres usages restent celles du premier plan. Pour 021081, la part conserve la déduction initiale de 276 421,84455 kg de besoins induits en aval ; aucune seconde déduction n'est appliquée. Les rapports entre usages peuvent toutefois évoluer : conserver cette fraction ne démontre pas qu'elle reste exacte toute l'année.

L'unique extension du code de préparation concerne `revision_series` : elle accepte aussi UN. Le besoin hebdomadaire fractionnaire estimé est conservé dans la provenance, puis arrondi une fois selon `floor(q + 0.5)`, comme l'estimation initiale ; le calendrier répartit ensuite des quantités journalières entières. Les parcours KG/G sont conservés, les conversions masse/UN sont refusées. Aucun changement du moteur physique n'est introduit.

### Résultats sur les quinze couples directement modifiés

L'indicateur ci-dessous est l'écart absolu moyen du **stock physique total** aux photos 2025, simulation à la clôture de la veille. Une baisse est une amélioration de proximité des stocks, pas une preuve de meilleure disponibilité.

| Article / site | Unité | Avant | Essai général | Évolution de l'écart |
|---|---|---:|---:|---:|
| 002612 / Avène | kg | 68 694,19 | 58 360,20 | −15,0 % |
| 007923 / Avène | kg | 25 537,80 | 25 811,46 | +1,1 % |
| 016332 / Avène | kg | 480,05 | 558,41 | +16,3 % |
| 021081 / Gaillac | kg | 233 299,65 | 260 232,01 | +11,5 % |
| 029313 / Avène | kg | 113,29 | 165,17 | +45,8 % |
| 038005 / Gien | kg | 25 626,69 | 22 978,49 | −10,3 % |
| 042342 / Gien | UN | 36 180 055,21 | 24 890 781,02 | −31,2 % |
| 049371 / Avène | kg | 3 877,99 | 3 774,79 | −2,7 % |
| 055703 / Avène | kg | 463,40 | 308,34 | −33,5 % |
| 099439 / Avène | kg | 2 672,11 | 2 398,93 | −10,2 % |
| 426331 / Avène | UN | 7 160,35 | 7 703,88 | +7,6 % |
| 693055 / Avène | kg | 722,74 | 925,99 | +28,1 % |
| 708073 / Gien | kg | 4 056,13 | 3 969,26 | −2,1 % |
| 734545 / Gien | UN | 2 347,44 | 2 259,38 | −3,8 % |
| 773474 / Gien | kg | 11 592,64 | 11 886,90 | +2,5 % |

**Huit améliorations, sept dégradations parmi les quinze.** Sur l'ensemble des 29 couples comparables, y compris les effets indirects, 11 écarts diminuent, 17 augmentent et un reste identique. La baisse de 344135/Gien est négligeable (3 UN sur environ 565 000 UN d'erreur) ; elle reste comptée comme variation numérique, pas comme progrès industriel significatif. Quatre couples restent non comparables dans le payload. Ne pas additionner les écarts exprimés dans des unités différentes.

Les effets indirects touchent aussi les références déjà actualisées : l'écart de 001848/Avène augmente de 14,7 %, celui de 039668 de 3,0 %, tandis que ceux de 001757 et 001893 diminuent légèrement. Leurs séries de prévisions n'ont pas été modifiées ; leurs trajectoires peuvent changer via la production et les autres composants.

### Disponibilité et production : raison de conserver l'essai séparé

Pour 268091, les quantités servies en 2025 passent de **3 499 453 à 3 211 453 UN**, soit **288 000 UN de moins**, avec un retard final passant d'environ 76 989 à 364 989 UN. Le service de 268967 est inchangé. Les quantités totales servies sur cinq ans restent identiques, mais les années après les dernières prévisions ne permettent pas de conclure à une amélioration industrielle.

Le registre `production_constraint_daily.csv` identifie pour 268091 à Avène :

- 001893 limitant sur 45 jours dans les deux scénarios ;
- 002612 limitant sur **81 jours** dans le candidat, contre aucun dans la référence ;
- 693055 limitant sur 28 jours contre 65 ;
- 029313 limitant sur six jours, et 049371 sur un jour, dans le candidat.

Ces jours signalent un manque par rapport au plan de lot ; ils ne sont ni un décompte d'ordres perdus ni une attribution causale exclusive des 288 000 UN. Les stocks physiques nuls passent notamment de 0 à 12 jours pour 002612, de 0 à 50 pour 029313 et de 101 à 182 pour 693055/Avène. Le cas 002612 montre qu'un stock moyen plus proche des photos peut coexister avec une disponibilité moins bonne. La prochaine analyse doit rapprocher les réceptions engagées au démarrage, leurs dates de disponibilité, le dimensionnement des achats et l'estimation des autres usages ; augmenter arbitrairement une sécurité ne résout pas ce diagnostic.

### Vérifications et limites

Simulation normale **1 825 jours, retour 0, 418,954 secondes**. Code et entrées inchangés pendant le calcul. Les dix tests ciblés en mémoire passent, ainsi que la qualification des exports. L'oracle indépendant contrôle 5 475 demandes journalières, les unités physiques entières et les quinze bilans matière (résidu maximal inférieur à 0,00005 kg). La comparaison autonome est vérifiée hors ligne sur 29 couples et 2 918 valeurs affichées, sans erreur JavaScript. La carte complète passe aussi sa revue ; une première tentative avait expiré pendant la navigation et reste conservée dans les preuves. Le [manifeste de livraison](../../artifacts/testing/mrp_all_revisions_20261001/manifest.json) regroupe la contre-vérification indépendante, les preuves natives et la revue de la carte ; les [chiffres par couple et service](../../artifacts/testing/mrp_all_revisions_20261001/analysis.json) et le [diagnostic de contraintes](../../artifacts/testing/mrp_all_revisions_20261001/production_diagnostic.json) restent consultables.

Les I projetés restent des hypothèses de consommation physique complémentaire. Les semaines absentes ne sont pas des consommations réelles nulles démontrées : 042342 n'a ainsi que 231 jours 2025 couverts. Les 19 séries ne se répètent pas après leurs dernières périodes fournies, situées en 2026 ; aucune prévision 2027–2029 n'est inventée. Certaines phrases du champ `assumptions`, hérité du graphe historique et conservé pour contrôler les différences, parlent encore de répétition annuelle ou d'autres articles inchangés : **elles ne décrivent pas cet essai**. Les séries effectives, le plan d'exécution et la présente documentation font foi pour son périmètre. Les autres vues de la carte et les deux suivis de lots restent historiques.

## Essai 055703 : fournisseur cohérent, protection datée et vérification sur deux autres matières

Étude isolée du 1er octobre 2026 : [comparaison interactive, ouverte sur 055703](../../resultats/regroupement_001757_20260929/comparaison_mrp_protection_055703.html) · [carte complète avec ce panneau](../../resultats/regroupement_001757_20260929/carte_mrp_protection_055703.html) · [plan des quatre simulations](../../artifacts/testing/mrp_055703_policies_20261001/plan.json).

**Décision : conserver les résultats comme expériences ; ne pas généraliser ni remplacer automatiquement la référence.** La protection améliore 055703, mais ne résout pas son écart de juin et dégrade nettement 708073. Une meilleure courbe sur un article ne démontre pas une règle commune du MRP industriel.

### Règle expérimentale et différences contrôlées

Une option générique `meta.supplier_planning_policy` permet de déclarer l'offre fournisseur utilisée à la fois pour les dates du plan et pour les nouveaux achats. Le mode facultatif `protection_mode: dated_stock_floor` maintient un niveau disponible projeté : `max(stock de sécurité source, taux global des besoins connus × durée calendaire correspondant aux jours ouvrés de sécurité)`. La durée est recalculée à la date de décision ; 30 jours ouvrés ne valent pas toujours 42 jours calendaires. La protection persiste après les consommations prévues, sans être elle-même consommée. Elle remplace, dans ce candidat, l'ancienne réserve complémentaire de couverture ; **elle ne s'y ajoute pas**.

Sans option, le moteur conserve son comportement. La déclaration exige une offre existante issue de FIA, une unité compatible et une provenance ; elle refuse les politiques concurrentes de sourcing ou de regroupement. Aucun article n'est codé en dur dans cette extension. Les autres offres restent dans le graphe ; les engagements historiques ne sont pas réaffectés. La sélection est exclusive pour les nouveaux achats de cet essai : aucun secours hypothétique n'est ajouté. La fenêtre historique servant au calcul de couverture n'est pas unifiée avec le nouveau délai.

Quatre calculs de **1 825 jours**, mêmes prévisions et parts des autres usages, stocks initiaux, prix, standards et sécurités sources :

1. Référence : nouvelle option absente, recalcul du scénario à dix-neuf prévisions actualisées.
2. Délai : offre 055703/VD0914320A à 21 jours utilisée au plan comme à l'exécution, puis 13 jours de réception selon le calendrier candidat lundi–vendredi.
3. Protection : même sélection, avec les **30 jours ouvrés sources** interprétés comme un plancher disponible daté.
4. Vérification sur d'autres matières, choisies **avant les résultats** : même règle aussi sur 039668/Avène (7 jours, stock fixe nul) et 708073/Gien (10 jours, stock fixe 2 000 kg), chacun avec son fournisseur unique et ses paramètres propres.

### Résultats et cause de la non-généralisation

Écarts absolus moyens du stock physique en kg, aux 52 photos après ouverture, clôture simulée de la veille :

| Article / site | Référence | Délai seul sur 055703 | Protection sur 055703 | Même règle sur les trois matières |
|---|---:|---:|---:|---:|
| 055703 / Avène | 308,34 | 462,34 | **205,14** | 205,14 |
| 039668 / Avène | 141,27 | 141,27 | 141,27 | **135,97** |
| 708073 / Gien | 3 969,26 | 3 969,26 | 3 969,26 | **6 177,34** |

Pour 055703, raccourcir le délai de planification retarde les commandes : la première passe de J39 à J64. Le dernier achat est physiquement reçu en J378, hors de 2025 ; le stock final tombe de 679,698 à 379,698 kg. Avec protection, l'écart moyen diminue de **33,47 %** par rapport à la référence et le stock final atteint **979,698 kg**, contre 933,345 kg dans la dernière photo source. Les jours sans disponible valent respectivement 0, 4 et 0. Mais **le 30 juin reste à 579,585 kg simulés contre 1 170,790 kg sources**, pour la référence comme pour la protection : l'amélioration annuelle ne corrige pas toute la cadence d'approvisionnement.

Pour 039668, le gain reste modeste (environ 3,8 %) ; les jours sans disponible passent de 6 à 4. Pour 708073, l'écart moyen augmente d'environ 55,6 % et les jours sans disponible passent de **0 à 35**, dont 15 jours sans stock physique. Les réceptions 2025 passent de **25 000 à 20 000 kg**.

Le contre-exemple 708073 est identifié **avant toute divergence de consommation** : au J93 (4 avril), les deux scénarios ont 4 416,778811 kg de stock disponible et les mêmes besoins physiques projetés, 44 847,667827 kg. La référence ajoute une réserve de couverture de **4 406,584316 kg**, tandis que le candidat la remplace par un plancher de **2 000 kg**. La référence demande un lancement immédiat de 706,787243 kg, arrondi au standard de 5 000 kg ; le candidat n'en demande aucun. Le premier lancement passe ainsi du **4 avril au 26 mai**, la réception physique du **2 mai au 23 juin**, et la disponibilité du **9 mai au 30 juin**. La règle candidate réduit ici une protection existante plus élevée : elle n'est donc pas une amélioration universelle.

Le service annuel et son retard cumulé restent identiques dans les quatre calculs : 3 211 453 UN servies pour 268091, 1 575 985 UN pour 268967. Cela n'annule pas la dégradation matière de 708073 : sa consommation par la production représentée baisse de 15 387,372 à 13 677,664 kg, et des stocks intermédiaires/finis peuvent absorber des écarts. Aucun gain de service n'est attribué à cette expérience.

La suite pertinente consiste à comprendre comment articuler **couverture existante, protection datée et anticipation des engagements**, sans remplacer aveuglément la première par un plancher plus bas, ni additionner deux fois la même sécurité. Les jours sources restent inchangés. Aucun achat industriel n'est injecté pour forcer la courbe.

### Vérifications, reproduction et limites

Les quatre simulations terminent avec code retour 0, code moteur et entrées stables : 518,172 s / 519,032 s / 505,328 s / 520,859 s. Deux calculs ont tourné simultanément au maximum : ces temps ne constituent pas un benchmark de performance. La [contrepreuve de référence](../../artifacts/testing/mrp_055703_policies_20261001/baseline_equivalence.json) rapproche **38 CSV récursifs identiques octet pour octet** (37 dans `data`, un dans `reports`) au calcul antérieur.

Les **16 tests ciblés de calcul en mémoire** et les quatre qualifications CSV passent. L'oracle indépendant confronte directement les photos Excel aux stocks, les bilans des trois matières, les prévisions et les disponibilités calculées. Les scénarios conservent les mêmes 34 675 lignes de demande complémentaire et de provenance, sans création de consommation de protection. Les quantités physiques UN restent entières. [Chiffres affichés et service](../../artifacts/testing/mrp_055703_policies_20261001/analysis.json) · [manifeste de livraison et preuves](../../artifacts/testing/mrp_055703_policies_20261001/manifest.json).

La comparaison autonome passe la revue hors ligne sur **5 836 valeurs aux photos**, les quatre scénarios, les onglets et le zoom. La carte complète passe également son parcours natif, sans erreur JavaScript. Deux premières tentatives de ce parcours restent conservées comme refusées : attente du panneau, puis manipulation du très gros nœud contenant le JSON. Le panneau est désormais chargé par une URL Blob au lieu d'un attribut `srcdoc` volumineux ; le contrôleur lit le JSON dans la page et ne retourne que l'article sélectionné. Les données embarquées restent identiques. La fermeture et la réouverture réutilisent la même iframe et sont vérifiées. Ce correctif de chargement ne réduit pas la taille des données ni ne démontre une limite précise du navigateur.

La [recette](../../artifacts/testing/mrp_055703_policies_20261001/study.py) et les commandes exactes du plan décrivent les quatre calculs ; les sorties existantes ne doivent pas être écrasées. Les HTML antérieurs sont conservés. Dans la carte complète, les autres onglets et les deux suivis de lots restent ceux du scénario historique ; les nouveaux résultats figurent dans le panneau comparatif. Seule l'année 2025 est confrontée aux photos sources. Les prévisions s'arrêtent en 2026, sans répétition artificielle : exécuter cinq ans ne constitue pas cinq ans de calibration industrielle. Les propositions à dates futures conservent par ailleurs le délai scalaire calculé au jour de décision, hors des parcours disposant d'un calendrier futur spécifique.

## Diagnostic 055703 à Avène — après généralisation des prévisions révisées

Analyse du 1er octobre 2026, première année 2025 de `mrp_all_revisions_20261001/run`, comparée à `mrp_001893_revisions_20260930/run`. Aucun paramètre, moteur ou HTML modifié pour ce diagnostic. [Comparaison existante, sélectionner 055703 / Avène](../../resultats/regroupement_001757_20260929/comparaison_mrp_revisions_generalisees.html).

### Paramètres et cohérence des sources

| Donnée | Valeur vérifiée | Source |
|---|---|---|
| Fournisseur utilisé | VD0914320A : 20,35 EUR/kg, 21 jours, standard 300 kg | `268091.xlsx/FIA!A16:H16` |
| Autre offre | VD0964290A : 49,20 EUR/kg, 42 jours, standard 300 kg | `FIA!A17:H17` |
| Nomenclature 268091 | 81,2 g pour 1 000 PF | `268091.xlsx/BOM!C10:F10` |
| Sécurité | 30 jours ouvrés, quantité fixe nulle | Inventory, `Politique de stock MRP!E10:G10` |
| Traitement à réception | 13 jours dans les 52 versions ; calendrier lundi–vendredi candidat | Flow MRP, `Feuille1!E473` et versions suivantes |
| Engagement initial | 300 kg, livraison prévue le 17 janvier, disponibilité le 5 février | `Extract_En_cours.xlsx/Sheet1!A69:I69` |

Le fournisseur utilisé est moins cher **et** plus rapide : l'autre n'est pas un secours rapide démontré. L'ancien stock initial (569,805000976563 kg) et le nouveau (569,805001 kg) concordent à l'arrondi près ; l'ancienne sécurité vaut également 30 jours. Aucune anomalie g/kg identifiée. La valorisation comptable des photos est de 18,99 EUR/kg : elle ne constitue pas un prix d'achat FIA supplémentaire.

### Ce qui s'améliore et ce qui reste différent

L'écart absolu moyen du stock physique aux 52 photos après ouverture passe de **463,40 à 308,34 kg (−33,5 %)**. Dans l'essai général, 2 819,950287 kg sont consommés par les autres usages estimés et 70,1568 kg par la production représentée, soit **2 890,107087 kg**. Les achats physiquement reçus passent de quatre à dix lots de 300 kg, engagement initial inclus : **1 200 → 3 000 kg**. La part complémentaire de 81,07 % reste une estimation issue du premier plan, pas une ventilation industrielle démontrée.

Les photos sources montrent onze hausses importantes (plus de 100 kg), les 27 janvier, 17 février, 10 mars, 31 mars, 5 mai, 26 mai, 30 juin, 1er septembre, 27 octobre, 17 novembre et 15 décembre. Toutes sont compatibles avec 300 kg reçus moins les sorties de la semaine. Les espacements varient de 21 à 63 jours : ce n'est pas un calendrier fixe établi.

**Reconstruction conditionnelle**, sans autre entrée ni ajustement masqué : onze réceptions de 300 kg donnent `569,805001 + 3 300 − 933,345021 = 2 936,459980 kg` de sorties nettes jusqu'à la dernière photo. C'est 46,352893 kg de plus que la consommation simulée, soit environ 1,6 %. Ce rapprochement ne transforme pas les photos en registre exact des réceptions ou consommations.

| Date de photo | Stock source kg | Stock simulé kg | Entrées sources reconstituées kg | Entrées simulées kg | Sorties sources reconstituées kg | Consommation simulée kg |
|---|---:|---:|---:|---:|---:|---:|
| 31 mars | 1 124,790 | 571,592 | 1 200 | 600 | 645,015 | 598,213 |
| 30 juin | 1 170,790 | 579,585 | 2 100 | 1 500 | 1 499,015 | 1 490,220 |
| 29 décembre | 933,345 | 679,698 | 3 300 | 3 000 | 2 936,460 | 2 890,107 |

Flux cumulés depuis l'ouverture ; simulation à la clôture de la veille. Au 30 juin, environ **591 kg d'écart** correspondent à **600 kg d'entrées en moins**, compensés par environ 9 kg de consommation en moins, sous l'hypothèse précitée. Fin décembre, **253,647 kg d'écart** correspondent à 300 kg d'entrées en moins, compensés par 46,353 kg de consommation en moins. Le stock simulé final contient déjà **300 kg présents mais indisponibles jusqu'au 7 janvier 2026** ; cette quantité est bien incluse dans les 679,698 kg physiques.

### Précautions sur les versions MRP et piste commune

Le premier H de 300 kg est présent en `H474` puis `H1435`, reporté en `H2442`, puis se retrouve vraisemblablement dans le J futur de `J3468`. Le 26 janvier, `J3467 + J3468 = 396,280001 + 300 = 696,280001 kg`, exactement la photo du 27 janvier (`Stocks!E744`). C'est vraisemblablement un même approvisionnement reporté puis disponible plus tard, pas plusieurs achats. Les quatre H de 300 kg du premier plan ne prouvent pas quatre engagements fermes : certaines versions suivantes proposent 450 kg et déplacent les échéances. Ne pas injecter arbitrairement tous les H initiaux comme commandes fermes.

Sur 52 versions, 51 sommes J concordent avec la photo suivante. Exception : le 2 mars, J vaut 1 006,945002 kg contre 746,790002 kg sur la photo du 3 mars ; la photo du 10 mars vaut justement 1 006,945002 kg. Ce décalage apparent reste signalé, sans correction arbitraire. Les J futurs répétés et les 14 H positifs de semaine courante ne sont pas des décomptes de commandes annuelles.

La piste prioritaire est **l'anticipation et le déclenchement des lots, avec la protection du stock partagé**. Dans le contrôleur actuel, une réserve complémentaire est calculée après déduction des besoins déjà présents dans l'horizon (`plan_component_network`) ; elle n'est pas automatiquement équivalente à un minimum de stock conservé à chaque date. Une réserve complémentaire nulle ne signifie donc pas, à elle seule, que la sécurité est ignorée. L'interprétation des 30 jours doit être testée comme règle commune, sans augmenter cette valeur source ni ajouter artificiellement un lot pour ajuster la courbe.

Le facteur de sécurité de cet essai vaut explicitement 1. Exemple de différence entre conventions : au jour 330, le disponible vaut 356,939 kg, contre `9,971982 kg/j × 42 jours calendaires = 418,823 kg` pour un plancher calculé sur les 30 jours ouvrés et les besoins globaux connus. Les 300 kg complémentaires sont encore indisponibles. Cela ne prouve pas que le MRP industriel applique ce plancher. Dans les traces, `target_stock_qty` reste une cible du périmètre du produit étudié (190,080 kg ce jour-là), tandis que `dated_global_target_rate_qty` inclut les autres usages : ne pas présenter ces deux indicateurs comme une même cible globale.

Autre incohérence de convention identifiée : sans politique de sourcing explicite pour ce couple, le planificateur retient le maximum des deux délais fournisseurs, soit 42 jours plus réception (59–61 jours au total), tandis que les achats sont exécutés avec le fournisseur à 21 jours plus réception (38–40 jours). À échéance de besoin identique, cet écart avance le lancement calculé de 21 jours par rapport à un délai cohérent avec le fournisseur retenu ; il n'explique pas directement un stock trop bas. Il faut isoler son effet avant toute généralisation.

Contrôles exécutés : relecture indépendante des Excel et du code ; **730 bilans physiques journaliers** et décompositions disponible/bloqué/réservé rapprochés des CSV des deux calculs, sans erreur au seuil 0,0001 kg. [Calcul reproductible en lecture des entrées](../../artifacts/testing/mrp_all_revisions_20261001/audit_055703.py) · [chiffres, achats, photos et empreintes des entrées](../../artifacts/testing/mrp_all_revisions_20261001/audit_055703.json). Aucune nouvelle simulation ni qualification globale lancée : ces contrôles ciblés expliquent les résultats existants et ne certifient pas encore une nouvelle règle industrielle.

## Diagnostic 001893 à Avène — base au délai fournisseur fixe

Périmètre : `empirical_delivery_20261001/study/source`, première année 2025, article `item:001893`, site `M-1810`. Analyse seule ; aucun paramètre ni résultat de simulation modifié.

**Fin décembre, l'écart de stock porte presque entièrement sur le stock déjà présent mais disponible en janvier.** Le plan du 28 décembre donne 37 157,928 kg dans la semaine courante (`Flow_Data_MRP_results.xlsx/Feuille1!J52451`), 20 900 kg disponibles le 4 janvier 2026 (`J52452`) et 44 820 kg le 25 janvier (`J52455`). Leur somme, 102 877,928 kg, correspond exactement à la photo du 29 décembre (`Flow_Data_Inventory_and_Replenishment_rules.xlsx/Stocks!E1183`). Selon la définition confirmée de J, ces 65 720 kg futurs sont déjà physiquement présents, pas des achats restant à recevoir.

À la clôture du 28 décembre (J361), le CSV `production_stock_availability_daily.csv` contient 37 025,088714 kg disponibles et physiques, sans indisponible. L'écart au total source est donc 65 852,839286 kg, dont 65 720 kg de disponibilité future source ; l'écart au seul disponible source est 132,839286 kg. Cette proximité ponctuelle du disponible ne valide pas toute la trajectoire : le 3 février, la photo vaut 14 623,304 kg, contre 71 760 kg physiques simulés à la clôture précédente, tous encore indisponibles.

Le registre `mrp_orders_daily.csv` contient six achats externes lancés et physiquement reçus en 2025 : 71 760 kg puis cinq fois 23 920 kg, soit **191 360 kg**, tous auprès de VD0910216A, à 28 jours de livraison puis 24 jours ouvrés de traitement à réception. La première commande part le 5 janvier, arrive le 2 février et devient disponible le 6 mars. Aucun ordre initial 001893/1810 n'est importé : les cinq lignes 001893 du carnet (`Extract_En_cours`, lignes 9–13) concernent 1820 et ne doivent pas être réaffectées sans preuve.

Le bilan physique simulé 2025 se ferme : 9 783,5 kg initiaux + 191 360 kg reçus − 164 118,411286 kg consommés = 37 025,088714 kg finaux (écart inférieur à 0,00001 kg en additionnant les exports arrondis). Les consommations comprennent 155 454,046486 kg estimés pour les autres produits et environ 8 664,365 kg pour les produits représentés. Les 53 photos sources donnent 253 974,674 kg de hausses positives cumulées, soit 62 614,674 kg de plus que toutes les réceptions simulées. C'est un cumul de hausses nettes, pas une mesure exhaustive des livraisons : consommations simultanées, transferts ou corrections éventuelles restent à distinguer.

**Défaut d'entrée identifié : les besoins partagés restent figés au premier plan du 5 janvier pour cette référence.** Ses 40 lignes (`Feuille1!118:157`) s'arrêtent au 19 octobre, sans besoin renseigné en novembre/décembre. L'estimation des autres usages retient 82,7728 % des besoins futurs de ce premier plan ; cette part est une hypothèse, pas une nomenclature industrielle complète. Les versions sources ultérieures contiennent bien des besoins de fin d'année et de 2026. Dans le calcul, l'achat suivant n'est lancé qu'à J369 (5 janvier 2026), pour réception à J397. La priorité est de présenter au planificateur les versions connues et leurs besoins futurs, avant de calibrer davantage les regroupements.

Les trois offres FIA (`FIA268091`, lignes 5–7) sont 4,40 €/kg / 56 jours / 22 800 kg ; 4,64 €/kg / 28 jours / 23 920 kg ; 5,105 €/kg / 42 jours / 20 900 kg. La sécurité source reste 15 jours ouvrés, stock de sécurité fixe nul. Les projections H ne se réduisent pas aux multiples de 23 920 kg : 950 kg est fréquent au début, puis 19 000, 20 900, 22 800 et 23 920 kg apparaissent. Une quantité projetée ne suffit pas à identifier un fournisseur, une commande ou une palette. Le choix fournisseur et le fractionnement des réceptions restent à rapprocher des données, sans multiplier arbitrairement la sécurité.

Contrôles : lectures des CSV du calcul conservé, rapprochement direct et indépendant des cellules Excel, fermeture du bilan matière. Aucune nouvelle simulation ni qualification globale exécutée pour ce diagnostic.

### Essai séparé : prévisions 001893 révisées sur un horizon de 52 semaines

[Comparaison interactive](../../resultats/regroupement_001757_20260929/comparaison_001893_revisions.html) · [carte complète](../../resultats/regroupement_001757_20260929/carte_001893_revisions.html) · [plan reproductible](../../artifacts/testing/mrp_001893_revisions_20260930/plan.json).

Règle commune appliquée : **à chaque publication d'un plan MRP, remplacer les besoins futurs par la dernière version connue, sans additionner les versions ni réécrire la semaine en cours**. Le mécanisme existant est réutilisé pour 001893/1810 : 38 lignes complémentaires fixes sont remplacées par 52 versions, soit 2 023 lignes futures. La part initiale estimée de 82,7728067775 % reste inchangée. Prix, choix fournisseur, standards, stocks initiaux, délais fixes et sécurités sont strictement identiques au point de départ. Le moteur n'a pas été modifié ; ce résultat reste un scénario séparé, reproductible avec `study.py prepare`, puis `study.py run` dans le dossier de preuves (les fichiers existants sont protégés contre l'écrasement).

| Indicateur 001893/Avène, 2025 | Point de départ | Besoins révisés |
|---|---:|---:|
| Écart absolu moyen du physique aux 52 photos | 37 355,43 kg | **18 953,16 kg (−49,26 %)** |
| Écart absolu moyen du disponible au J de la semaine courante | 19 641,19 kg | **15 350,47 kg (−21,85 %)** |
| Nouveaux achats lancés | 6 / 191 360 kg | 17 / 454 480 kg |
| Réceptions physiques dans l'année | 191 360 kg | 430 560 kg |
| Consommation complémentaire estimée exécutée | 155 454,05 kg | 342 599,25 kg |
| Consommation des produits représentés | 8 664,36 kg | 8 664,36 kg |
| Jours de stock physique nul / disponible nul | 15 / 47 | 15 / 47 |

La comparaison du disponible utilise ici le J courant du plan, pas le stock total des photos. Sur 45 des 52 semaines, la somme des J datés concorde exactement avec la photo voisine ; les sept autres gardent leur écart de source/date. Ce rapprochement n'identifie pas des consommations observées.

**Rapprochement du 29 décembre, à clôture simulée du 28 décembre :** le physique passe de 37 025,09 à **65 159,89 kg**, contre 102 877,93 kg en source. Le candidat se décompose en 41 239,89 kg disponibles et 23 920 kg indisponibles, contre respectivement 37 157,93 et 65 720 kg dans le MRP source. Il reçoit 23 920 kg supplémentaires **le 30 décembre**, et termine le 31 à 89 079,89 kg physiques, dont 47 840 kg indisponibles. Cette valeur du 31 ne doit pas être présentée comme une comparaison à date identique avec la photo du 29.

La correction rétablit des besoins et achats de fin d'année mais ne résout pas les ruptures initiales ni tous les décalages de réception. Les 17 achats restent tous sur VD0910216A : 71 760 kg une fois puis 23 920 kg seize fois, livraison fixe 28 jours puis traitement de réception 24 jours ouvrés. Le rapprochement fournisseur/fractionnement reste ouvert : les H source peuvent être des échéances regroupées ou fractionnées et ne prouvent ni un quota d'achat ni un fournisseur exécutant. Aucune quantité standard source ni règle de sélection n'a été ajustée pour améliorer la courbe.

Les métriques de stock 2025 des autres couples représentés sont inchangées, comme le service PF 2025. Sur cinq ans, les quantités servies totales sont identiques ; le cumul des retards de 268091 change, ce qui ne constitue pas une validation industrielle des années sans nouvelles données. Les autres onglets de la carte et les deux suivis de lots conservent leur scénario historique ; seul le panneau de comparaison contient cet essai.

**Vérification :** exécution normale de 1 825 jours terminée en 429,734 s, retour 0, seize fichiers moteur/calcul et toutes les entrées inchangés. Quatorze tests ciblés en mémoire passent, ainsi que la qualification des exports. La [contre-vérification indépendante](../../artifacts/testing/mrp_001893_revisions_20260930/validation/independent.json) rapproche directement les 2 023 cellules Excel, les 365 demandes journalières, les dates de livraison/disponibilité et le bilan des lots (résidu inférieur à 0,00002 kg). La [revue ciblée de la comparaison](../../artifacts/testing/mrp_001893_revisions_20260930/view_001893_4899dfa9/report.json) vérifie hors ligne six onglets, les deux scénarios, 208 valeurs aux dates des photos, les bases physique/disponible et le zoom, sans erreur JavaScript. Les preuves sont regroupées dans le [manifeste de livraison](../../artifacts/testing/mrp_001893_revisions_20260930/manifest.json).

Limites conservées : les I projetés restent une hypothèse de consommation physique ; la part des autres usages n'est pas une nomenclature industrielle complète. Les prévisions de cet article ne sont pas répétées artificiellement après leur fin, le 7 novembre 2026. En 2025, 329 jours sont couverts ; les périodes 1–11 janvier, 27 juillet–16 août et 28–31 décembre restent non fournies, pas des demandes industrielles nulles démontrées. La simulation de cinq ans vérifie l'exécution ; elle ne calibre pas les besoins industriels de 2027–2029.

## Bilan annuel des avances et retards fournisseurs — toutes les données 2025 disponibles

Le [rapport annuel](../../artifacts/testing/supplier_delivery_dates_20261001/annual_final/rapport_annuel.md) étend le rapprochement aux **douze mois et 52 versions MRP**, au-delà du carnet initial. Les dernières photos datent du **29 décembre 2025** : aucune arrivée du 30–31 décembre n'est inventée. Le périmètre d'origine externe FIA + carnet couvre **23 couples article/site, 1 146 intervalles et 300 hausses nettes**.

**278 hausses ont une prévision historique candidate ; 44 rapprochements sont retenus pour une statistique conditionnelle**, sur **16 références**, avec au moins un cas chaque mois. La sélection n'est pas un recensement de toutes les livraisons : consommations masquant une entrée, regroupements, révisions, corrections et identités manquantes limitent le rapprochement. Les 300 fenêtres et tous leurs motifs restent dans le [tableau détaillé](../../artifacts/testing/supplier_delivery_dates_20261001/annual_final/annual_arrival_windows.csv).

La référence de date est **G du carnet initial** lorsqu'un lien unique est possible (3 cas retenus), sinon la **première prévision suivie entrant dans l'horizon du délai fournisseur FIA** (41 cas). Ce franchissement est une convention d'estimation commune, pas une date de commande observée. Pour plusieurs délais fournisseurs possibles, les références alternatives sont conservées sans inventer le fournisseur exécutant. Le suivi des versions privilégie une date cible stable ; un changement de date n'est lié par quantité que si celle-ci est unique dans les deux versions. Les quantités modifiées après la référence, traces partagées et références trop récentes restent hors statistique principale. Les révisions avant la référence figée restent documentées sans invalider automatiquement le rapprochement.

| Résultat sur les 44 fenêtres retenues | Nombre |
|---|---:|
| Intervalle entièrement après la prévision : retard reconstitué | **8** |
| Intervalle recouvrant la période prévue : signe indécidable | **36** |
| Intervalle entièrement avant la prévision | **0** |

La moyenne des **milieux d'intervalle** est **+2,75 jours**, médiane **+1,5 jour**, écart-type descriptif **9,72 jours**. Avec les bornes possibles des dates, la moyenne peut aller de **−3,55 à +9,05 jours** : ce n'est pas un intervalle de confiance. Les centres de 36 cas sont dans ±7 jours, mais seuls trois intervalles complets y tiennent. **Ni 36/44 ni 8/44 ne sont un taux de ponctualité/retard de tous les fournisseurs.** Zéro avance entièrement identifiable ne signifie pas zéro arrivée anticipée ; 12 centres d'intervalle sont négatifs.

Les retards reconstitués incluent **042342 : 30–43 jours**, **333362 : 37–50 jours puis 16–29 jours**, et cinq cas de **2–15 jours** pour 001848, 007923 et 333362. Les deux grands retards ont été relus dans les versions successives et les photos : les H persistent en étant reportés, puis disparaissent autour d'une hausse compatible. Il n'est pas démontré qu'ils correspondent à des commandes individuelles inchangées.

La partition des 300 fenêtres est complète : **44 retenues**, **8 sans H contemporain**, **14 sans référence historique exploitable**, puis, par priorité de motif, **59 avec hausse supérieure au H**, **60 avec trace partagée**, **64 avec quantité révisée après référence**, **51 avec référence trop récente**. Les motifs détaillés peuvent se cumuler ; cette partition n'en compte qu'un par fenêtre. Une analyse plus restrictive excluant les références déjà dans l'horizon au premier point connu conserve **17 cas**, dont **5 retards**, moyenne centrale **+3,09 jours** ; la composition de l'échantillon change.

Livrables : [par mois](../../artifacts/testing/supplier_delivery_dates_20261001/annual_final/statistiques_mensuelles.csv), [par article](../../artifacts/testing/supplier_delivery_dates_20261001/annual_final/statistiques_articles.csv), [traces et cellules sources](../../artifacts/testing/supplier_delivery_dates_20261001/annual_final/annual_results.json), [preuve indépendante](../../artifacts/testing/supplier_delivery_dates_20261001/annual_final/validation/report.json). Le calcul arithmétique et la relecture ne certifient pas une loi industrielle ; aucune simulation ni distribution du moteur n'est modifiée par ce bilan.

## Avance/retard des livraisons fournisseurs : ancrage dans les engagements sources

**Question métier : date d'arrivée physique repérée dans les stocks moins date de livraison prévue par les sources.** Ce calcul est distinct de la concordance générale entre les hausses de stock et les H MRP de la section suivante. Aucun résultat simulé n'est utilisé ici.

Le [nouvel audit fournisseur](../../artifacts/testing/supplier_delivery_dates_20261001/results.json) relit le carnet `Extract_En_cours`, les photos et les plans MRP. Le carnet fournit **82 achats externes** AVICDE/ECHCDE, avec fournisseur, quantité et **date physique prévue G** ; **66** ont des photos au même article/site (15 couples, dates prévues janvier–mai). La colonne **I** est une disponibilité prévue après traitement de réception et ne mesure jamais une arrivée réelle. Le délai FIA est renseigné lorsque le fournisseur du carnet est retrouvé ; il n'est pas confondu avec le traitement de réception. Sans date d'émission de commande, le délai complet réellement écoulé depuis l'achat reste inconnu.

Le périmètre annuel des origines externes est l'union **FIA + carnet**, pas FIA seule : **23 couples avec photos, 1 146 intervalles, 300 hausses nettes**. Cela ajoute **001848/Gien**, fournisseur VD0951020A explicitement renseigné en ligne 7 du carnet. Pour **734545**, le carnet ligne 104 cite **VD0525906A**, tandis que la FIA cite VD1095770A : une seule offre FIA n'établit pas l'identité de toutes les livraisons réelles. L'identifiant fournisseur affecté aux anciens rapprochements est donc une attribution par catalogue, pas une preuve d'exécution.

Chaque engagement est comparé à **toutes** les hausses voisines, avec trois fenêtres de recherche ±21, ±42 et ±84 jours pour rendre visible la dépendance au rayon. Un candidat corroboré exige une hausse ne dépassant pas la quantité de l'engagement et un H de même quantité dans l'une des deux dernières versions connues à la photo, sur une semaine recouvrant la hausse. Aucun I prévisionnel n'est transformé en consommation réelle. Aucun candidat n'est retenu parce qu'il est simplement le plus proche de la date prévue. Les liens uniques dans les deux sens restent conditionnels : achats non listés, fractionnements/regroupements, révisions et corrections de stock peuvent les invalider.

Exemples de fenêtres **conditionnelles** trouvées à ±21 jours (pas un histogramme industriel) :

| Article/site | Fournisseur du carnet | Quantité prévue | Livraison prévue G | Photos encadrant la hausse | Écart possible |
|---|---|---:|---|---|---|
| 001757/Avène | VD0951020A | 2 000 kg | 5 mars | 10–17 mars | +5 à +12 jours |
| 001757/Avène | VD0951020A | 4 000 kg | 28 janvier | 27 janvier–3 février | −1 à +6 jours |
| 001848/Avène | VD0951020A | 6 000 kg | 20 février | 17–24 février | −3 à +4 jours |
| 038005/Gien | VD0520132A | 10 000 kg | 7 avril | 24–31 mars | −14 à −7 jours |
| 055703/Avène | VD0914320A | 300 kg | 17 janvier | 20–27 janvier | +3 à +10 jours |
| 734545/Gien | VD0525906A | 6 400 unités | 6 janvier | 6–13 janvier | 0 à +7 jours |

Les bornes sont les dates des photos, sans précision inventée sur l'heure de prise. Pour 001848, le H de 6 000 kg reste dans les sept versions du 5 janvier au 16 février, semaine cible du 16 février, puis disparaît du plan du 23 février ; la hausse réelle est 5 819,8 kg. Pour 055703, H=300 kg est reporté de la semaine du 12 à celle du 19 janvier, puis disparaît au 26 janvier ; la hausse est 222,09 kg. Ces traces renforcent les hypothèses sans identifier une transaction exécutée.

**La statistique globale de retard fournisseur n'est pas identifiée par cette sélection.** À ±21 jours, seuls 6 engagements sur les 66 couverts ont un lien corroboré unique (2 fenêtres tardives, 1 précoce, 3 compatibles avec la date prévue). À ±42 jours, 4 restent uniques ; à ±84 jours, 3. Les ensembles changent, et la moyenne des centres passe de +1,83 à +10,50 puis +12,83 jours : cela démontre l'instabilité de l'appariement, pas une mesure du retard moyen industriel. Les cas ambigus ne sont pas des livraisons à l'heure. Le carnet initial ne couvre pas les nouveaux achats du reste de 2025.

Les [300 hausses du périmètre externe](../../artifacts/testing/supplier_delivery_dates_20261001/annual_stock_rises.csv) et [tous les candidats, sources et motifs](../../artifacts/testing/supplier_delivery_dates_20261001/candidates.csv) restent consultables. Aucune loi du moteur n'a été recalibrée avec ces résultats.

## Reprise exhaustive des variations de stock et des plans MRP 2025

**Statut : analyse des données sources, sans changement du moteur ni de la loi de livraison. La loi à quatorze rapprochements ci-dessous reste expérimentale ; elle ne représente pas une distribution industrielle validée.**

Le [rapport exhaustif](../../artifacts/testing/stock_mrp_exhaustive_20261001/rapport.md) couvre les **1 646 photos**, **32 couples article/site** et **1 614 intervalles** : **411 hausses**, **846 baisses**, **357 périodes stables**. Les **53 398 lignes MRP** sont rapprochées directement des Excel par un validateur indépendant. Le MRP possède 33 couples : 029313/Gien n'a pas de photo ; 344135/Gien n'en possède que trois. La dernière photo est datée du 29 décembre 2025.

Avec la convention dimanche début de semaine et la dernière version connue au début de chaque semaine cible, **410/411 hausses** sont couvertes par des lignes MRP : **388** rencontrent une entrée H dans les semaines recouvrantes, **22** aucune. **52 hausses dépassent même tout le H possible de ces semaines** ; ce décompte inclut les 22 sans H. Ces nombres sont des concordances de calendrier et de quantité, pas des taux de ponctualité. Les bornes de quantité n'imposent pas une répartition journalière uniforme.

Sur une cohorte commune de **253 hausses** dont les quatre anticipations sont disponibles, un H recouvrant existe dans **241 cas** avec le plan récent, **201** à 14 jours, **190** à 28 jours et **193** à 56 jours. Les volumes H possibles suffisent à couvrir la hausse nette dans respectivement **225, 169, 165 et 167 cas**. Cela distingue les révisions des plans d'une comparaison faite sur des populations différentes. Le calendrier alternatif où le dimanche clôt la semaine est également calculé ; aucune convention n'est sélectionnée uniquement pour améliorer le résultat.

Le calcul conditionnel `entrées = variation de stock + I prévu` est effectué pour **toutes les périodes couvertes**, même sans hausse. Il donne **68 résultats négatifs sur 1 583 périodes couvertes** avec le plan récent et **258 sur 1 033** à 14 jours. Ces résultats restent négatifs et signalés ; ils ne sont pas corrigés arbitrairement. Les I, notamment courants, peuvent inclure des besoins reportés et ne prouvent pas la consommation exécutée. Les semaines absentes restent inconnues, jamais zéro.

Le rapprochement cumulé FIFO permet regroupements et fractionnements, conserve les volumes non rapprochés et s'interrompt aux données manquantes ou reconstructions négatives. Les profils temporels ainsi calculés dépendent fortement des volumes et des consommations supposées : **ils ne fournissent pas un taux de retard fournisseur réel ni une loi à réinjecter dans le moteur**. Un contrôle de sensibilité conserve séparément les blocs d'au moins deux périodes où les quantités projetées et reconstituées diffèrent d'au plus 10 % ; ce seuil descriptif n'identifie pas les commandes. KG, UN et M restent séparés.

Contrôle complémentaire : **1 131 égalités / 1 615** rapprochements entre ΣJ du plan du dimanche et photo du lundi, **484 écarts**. J décrit du stock déjà présent et n'est jamais additionné aux réceptions H. Pour **039668**, toutes les cinq hausses sont conservées, dont quatre importantes et **0,030 kg** le 17 novembre ; cette dernière ne prouve pas une réception.

Livrables : [synthèse des 32 références](../../artifacts/testing/stock_mrp_exhaustive_20261001/summary_by_reference.csv), [toutes les périodes et huit conventions](../../artifacts/testing/stock_mrp_exhaustive_20261001/intervals.csv), [bornes H](../../artifacts/testing/stock_mrp_exhaustive_20261001/weekly_bounds.csv), [statistiques et limites](../../artifacts/testing/stock_mrp_exhaustive_20261001/summary.json), [preuve indépendante](../../artifacts/testing/stock_mrp_exhaustive_20261001/validation/report.json). Les **12 912 calculs de périodes**, **6 227 allocations** et **2 056 blocs** ont été contre-vérifiés sans importer les fonctions de l'analyse. Les simulations et cartes précédentes restent inchangées.

## Distribution empirique des décalages de réception — mise en application

Le mode `--supplier-delivery-mode empirical` remplace le tirage Erlang des **nouveaux achats externes agrégés**, dans le parcours MRP daté. Il utilise une politique explicite `meta.empirical_supplier_delivery_policy`. Les références historiques restent reproductibles avec `sampled`, et le témoin `source` conserve le délai FIA fixe. Les transferts internes ne sont pas calibrés avec les réceptions fournisseurs. La loi ne change ni les quantités standard, ni les sécurités sources, ni les engagements initiaux, ni le délai de traitement de réception. La couverture de planification conserve sa convention précédente afin d'isoler l'effet physique ; ce mode n'est donc pas une suppression de toute convention Erlang à tous les niveaux du modèle.

**Ce que mesure la loi :** un décalage estimé entre une semaine de réception projetée H et une fenêtre de remontée du stock physique. Elle ne mesure pas directement le délai entre émission d'une commande identifiée et réception. Son application sous la forme `délai FIA + décalage` est une hypothèse commune explicite, autorisée pour cette reconstitution. Les incertitudes d'identification, de périmètre, de calendrier et de consommation ne disparaissent pas avec le tirage.

### Rapprochement conservateur et traçable

Le module [empirical_delivery.py](../../simulation/experiments/empirical_delivery.py) rapproche les sources déjà auditées des photos Excel relues directement. Il vérifie leurs empreintes ; il refuse les données modifiées au lieu de réutiliser silencieusement une ancienne extraction. Le calcul conserve les motifs d'exclusion et les cellules d'origine.

1. Couple article/site avec une origine externe unique renseignée par la FIA ; fournisseurs multiples, origine interne et absence de photos exclus de l'estimation.
2. Deux photos de stock espacées d'au plus sept jours, avec hausse nette positive. Quantités G converties en kg, ZUN traitées comme unités.
3. Dernier plan connu **au moins quatorze jours avant le début** de cette fenêtre, jamais le plan publié après la remontée. Une seule entrée H positive dans le voisinage de recherche ±21 jours ; sinon rapprochement ambigu.
4. Hausse nette entre 50 % et 102 % du H candidat ; différence `H − hausse − I prévu sur la fenêtre` inférieure ou égale à 25 % de H. Les I sont proratisés sur les seuls jours couverts et les semaines absentes entraînent un rejet. Ces seuils sélectionnent des cas compatibles, pas des commandes industrielles certaines.
5. Un H daté ne peut expliquer deux remontées. Déduplication chronologique : un nouvel événement ne retire jamais rétroactivement une observation déjà connue. J, y compris futur, n'est jamais une nouvelle réception.

Les photos encadrent la réception possible entre le lendemain de la première et la seconde. Le H est représenté par sa semaine dimanche–samedi, convention explicite. On conserve l'intervalle complet du décalage et on utilise son milieu arrondi pour le tirage ; les bornes ne sont pas présentées comme des dates mesurées. Une autre orientation de la semaine déplacerait les estimations de six jours. La distinction H arrivée physique/disponibilité reste à confirmer et peut affecter l'interprétation.

### Loi obtenue et utilisation sans connaissance du futur

**14 événements compatibles, six couples article/site** : 029313, 039668, 338928, 426331 à Avène ; 708073 et 734545 à Gien. Chaque événement pèse une fois, sans prétendre qu'il correspond à une commande unique.

| Décalage central estimé | Événements dans le pool complet |
|---|---:|
| −12 jours | 1 |
| −5 jours | 4 |
| +2 jours | 8 |
| +9 jours | 1 |

La moyenne de ces valeurs vaut −0,5 jour et leur écart-type de population environ 5,03 jours. Ce ne sont pas la moyenne et l'écart-type des délais fournisseurs réels. Les hausses visibles favorisent les réceptions peu masquées par consommation ; la fenêtre de recherche tronque les décalages extrêmes. Aucun taux de ponctualité industriel ni loi individuelle fournisseur n'est déduit de quatorze cas.

À chaque commande, le moteur ne retient que les événements dont la photo finale est déjà connue (`known_day <= decision_day`). Avant cinq événements, il conserve le **délai FIA fixe, sans tirage**, plutôt qu'un retour à Erlang. Le cinquième devient connu **le 21 avril 2025, J110**. Ensuite, un événement admissible est tiré uniformément ; le délai vaut FIA + son décalage, avec minimum physique d'un jour et valeur avant bornage tracée. Les bornes Erlang historiques ne sont pas appliquées à cette loi. Le traitement de réception E intervient ensuite, selon son calendrier propre. Le mode empirique refuse actuellement un préchauffage non nul pour éviter de décaler implicitement les dates de connaissance.

Les colonnes `empirical_sample_id`, `empirical_known_day`, `empirical_pool_size`, `empirical_delta_days`, `empirical_status`, `empirical_unclipped_lead_days` permettent de vérifier chaque achat exécuté. Elles n'apparaissent que dans les sorties du mode empirique, afin de conserver le format des références. Le résumé enregistre la politique complète et ses limites. Après 2025, le pool acquis reste connu ; aucun nouvel historique industriel n'est inventé.

Pour **039668**, deux événements sont retenus (juin et décembre). **Mars est exclu de l'apprentissage** : les 300 kg de l'ancien plan sont incompatibles avec une hausse nette de 426,115 kg selon le critère fixé. La première commande simulée de mars utilise donc les 35 jours FIA par repli, pas une valeur ajustée pour forcer la photo du 31 mars.

### Reproduction et contrôle

La [politique finale](../../artifacts/testing/empirical_delivery_20261001/calibration/final/empirical_policy.json) et les [exclusions](../../artifacts/testing/empirical_delivery_20261001/calibration/final/excluded_intervals.json) sont produites par `python -B -m etudecas.simulation.experiments.empirical_delivery --output etudecas/artifacts/testing/NOUVEAU_DOSSIER`. La commande utilise l'extraction détaillée `mrp_full_flow_audit_20260930/flows/results.json` et vérifie les Excel associés ; cette extraction reste une entrée nécessaire à la recalibration.

Le [protocole comparatif](../../artifacts/testing/empirical_delivery_20261001/study/plan.json) conserve les prévisions révisées de 039668 dans **les trois calculs de 1 825 jours** : Erlang, FIA fixe, empirique. Il ne mélange pas la correction des prévisions et celle des délais. Les graines et l'appariement par liaison/date sont conservés ; des décisions différentes peuvent néanmoins changer les dates et donc les tirages correspondants. Le témoin Erlang doit reproduire la variante révisée précédente. Les photos sources ne portent que sur 2025 ; les années suivantes vérifient la propagation et la stabilité, sans validation industrielle pluriannuelle.

L'oracle indépendant a vérifié directement les Excel, les conversions, les quatorze rapprochements et les différences autorisées des graphes : [130 contrôles des entrées](../../artifacts/testing/empirical_delivery_20261001/validation/inputs.json). Les rapprochements chronologiques et le tirage sans données futures sont également couverts par les tests ciblés en mémoire. Une bonne cohérence technique ne démontre pas que cette petite loi conditionnelle reproduit toute la variabilité industrielle.

### Résultats des trois simulations terminées

[Carte complète](../../resultats/regroupement_001757_20260929/carte_delais_empiriques.html) · [comparaison directe](../../resultats/regroupement_001757_20260929/comparaison_delais_empiriques.html). Les autres vues et les deux suivis de lots restent historiques. Le panneau de comparaison contient les trois nouveaux calculs et l'onglet Gaillac. Dans « Entrées / sorties », **Pourquoi ce délai fournisseur ?** détaille chaque achat empirique : taille du pool connu, décalage, événement et date de connaissance, ou repli fixe.

| 039668 / Avène, 2025 | Erlang, mêmes prévisions révisées | FIA fixe | Loi empirique |
|---|---:|---:|---:|
| Première commande | 5 mars | 5 mars | 5 mars |
| Première livraison physique | 14 mai | 9 avril | 9 avril |
| Première disponibilité | 15 mai | 10 avril | 10 avril |
| Écart absolu moyen aux 52 photos, kg | 178,27 | 137,12 | 140,21 |
| Clôtures à stock physique nul | 29 jours | 2 jours | 4 jours |
| Nouveaux ordres émis en 2025 | 4 × 450 kg | 4 × 450 kg | 4 × 450 kg |
| Réceptions physiques pendant 2025 | 1 350 kg | 1 350 kg | 1 350 kg |

La première réception avance de **35 jours** grâce au repli FIA fixe avant acquisition de l'historique suffisant. La photo source remonte dès le 31 mars : l'écart restant d'environ neuf jours jusqu'à la livraison du 9 avril ne doit pas être masqué par un ajustement supplémentaire de la distribution. Il reste à expliquer le besoin daté et le lancement du 5 mars. Les quatre délais empiriques de 039668 valent **35, 37, 30 et 37 jours** ; les livraisons de la dernière commande tombent en janvier 2026. Le cas fixe explique que la réduction de dispersion fait l'essentiel du progrès sur cette référence ; la distribution estimée n'optimise pas sa courbe.

Sur les **29 couples comparables**, la variante empirique améliore l'écart absolu moyen aux stocks sources pour **19**, le dégrade pour **8**, le conserve pour **2**. Le témoin fixe donne 16/8/5. Le couple partiel 001848/Gien, représenté seulement par engagements initiaux, figure parmi les inchangés ; aucune somme des kg, mètres et UN. Exemples : 001848/Avène passe de 2 323,62 à 2 114,05 kg ; 338929/Avène de 1 006 918,69 à 909 712,04 UN. En revanche, 001757/Avène passe de 2 634,33 à 2 639,49 kg. Ces résultats sont propres au scénario et à la graine testés, pas une preuve de supériorité statistique générale.

Les **385 achats externes lancés en 2025** sous loi empirique comprennent 157 replis fixes et 228 tirages depuis les observations déjà connues. Les décalages effectivement tirés cette année vont de −5 à +9 jours ; le −12 devient connu en décembre et n'a pas été tiré sur ces commandes. L'écart absolu moyen aux FIA tombe à 2,10 jours, avec 365/385 achats dans ±7 jours. Une partie de cette faible dispersion provient nécessairement du repli fixe : ce n'est pas un taux de ponctualité industriel observé. Le témoin Erlang avec ces mêmes prévisions compte 391 achats, écart absolu moyen 24,05 jours, 85 dans ±7 jours.

**Contrepartie réseau à conserver dans le bilan :** les deux variantes servent 28 800 UN de moins de 268091 pendant 2025 (3 499 453 contre 3 528 253), avec reliquat de fin d'année 76 989 au lieu de 48 189 UN. Le cumul quantité × jours de retard 2025 augmente également (304 797 contre 153 684 UN·jours). Cela ne permet pas d'attribuer la différence au seul composant 039668 : les délais de tous les achats externes ont changé. Sur cinq ans, le total servi reste identique ; le cumul de retard de 268091 diminue de 495,07 millions d'UN·jours à 460,94 millions en empirique, ou 452,25 millions en fixe. Le service de 268967 reste identique. Une amélioration des stocks d'un composant ne démontre donc pas une amélioration générale du service.

Le décompte limité aux **28 couples disposant de 52 photos** donne 18 améliorations, huit dégradations et deux inchangés pour l'empirique. Le 29e couple, 344135/Gien, n'a que trois photos ; son amélioration explique le total 19 ci-dessus. Le périmètre physique partiel de 001848/Gien reste une autre limite, distincte du nombre de photos.

Les trois exécutions se terminent avec code retour nul et moteur inchangé, en environ 11,5 minutes chacune sur ce poste, lancées en parallèle. Les 19 tests ciblés en mémoire et les trois qualifications physiques passent. La [contre-vérification finale](../../artifacts/testing/empirical_delivery_20261001/validation/outputs.json) passe 202 contrôles : 37 CSV Erlang strictement identiques à la référence révisée, 6 229 achats sur cinq ans contrôlés, tirages empiriques sans données futures, quantités UN entières, réceptions et disponibilités, champs exportés dans la carte et écarts de stock recalculés. Les [résultats détaillés](../../artifacts/testing/empirical_delivery_20261001/analysis.json) et le [manifeste de livraison](../../artifacts/testing/empirical_delivery_20261001/manifest.json) distinguent la cohérence technique de la calibration industrielle limitée. La loi est appliquée au nouveau scénario ; l'Erlang historique reste conservé comme référence.

## Dispersion des délais : sources et simulation — 30 septembre 2026

**La dispersion physique du modèle est une hypothèse non calibrée sur les commandes industrielles.** L'import FIA prend le délai source comme moyenne d'une loi Erlang à quatre étapes et fixe la borne haute à `max(délai + 14, 2 × délai)` (`update_supply_graph_from_case_data.py`, fonction d'application FIA). Seule la moyenne est renseignée par la FIA ; les quatre étapes et la borne sont des conventions. Le mode courant est `erlang`, avec délais stochastiques activés. Pour une référence de 35 jours, l'écart-type théorique avant arrondi et plafonnement vaut 17,5 jours et le plafond 70 jours. Une option nommée `industrial` existe, mais sa docstring précise également qu'elle est une approximation sans historique de commandes ; son nom ne constitue pas une validation industrielle.

Mesure sur la référence de cinq ans `gaillac_039668_20260930/study/reference`, nouveaux achats externes uniquement, hors carnet initial, transferts et apports amont simplifiés. Les groupes annuels suivent la **date de lancement**, même si la livraison intervient l'année suivante. Le délai mesuré va du lancement à la réception physique ; le traitement de réception avant disponibilité est exclu.

| Référence de délai | Achats lancés en 2025 | Délais physiques simulés min–max | Écarts par rapport à la référence |
|---|---:|---:|---:|
| 35 jours, quatre couples article/site | 35 | 10–70 jours | −25 à +35 jours |
| 42 jours, 338929/Avène | 30 | 11–80 jours | −31 à +38 jours |
| 84 jours, 001757/Avène | 147 | 6–168 jours | −78 à +84 jours |

Sur les **389 nouveaux achats externes lancés en 2025**, 84 sont dans ±7 jours de la référence (21,6 %), 242 s'en écartent de plus de 14 jours (62,2 %). L'écart absolu moyen est 24,10 jours, mais il mélange des délais de référence de 15 à 154 jours et donne un poids identique à chaque commande. Sur les **2 093 achats des cinq ans**, ces compteurs sont respectivement 477, 1 245 et 24,49 jours. Les 389 tirages 2025 utilisent tous quatre étapes Erlang. Les deux achats 039668 de la référence reçoivent 56 et 21 jours ; les quatre achats du scénario révisé reçoivent 70, 33, 27 et 52 jours. Ces valeurs ne sont pas des délais industriels mesurés.

**Dans les données sources, la mesure identifiable est différente : la stabilité des prochaines entrées projetées.** Pour chacun des 22 couples munis d'offres externes, on compare deux versions hebdomadaires consécutives et la première semaine H positive de chacune. On exclut le roulement normal lorsque l'ancienne échéance est déjà atteinte à la nouvelle version, ainsi que l'absence de H positif. Sur 1 087 transitions : 617 exclues pour échéance atteinte, sept sans prochaine entrée ; **463 comparaisons retenues**. Les dates sont inchangées dans 360 cas (77,8 %), se déplacent d'au plus sept jours dans 432 cas (93,3 %), d'au plus quatorze dans 448 (96,8 %). Les quantités restent identiques dans 417 cas ; elles changent dans 46. Les cibles incluent 2026 dans 67 comparaisons. La sélection concerne la prochaine entrée, pas toutes les réceptions, et n'identifie pas une même commande entre versions. Les décalages extrêmes, de −126 à +91 jours, peuvent notamment refléter suppressions, substitutions et modifications du plan ; ils ne doivent pas devenir une distribution de retards fournisseurs.

Pour **039668**, 46 comparaisons : 27 dates stables, onze avances de sept jours, six reports de sept jours, un de quatorze et un de vingt-huit. Exemple recoupé directement : `Feuille1!H398` annonce 300 kg le 13 avril dans le plan du 5 janvier ; `H5395` les situe au 30 mars dans celui du 9 février ; `H11417` au 6 avril dans celui du 23 mars ; `H12443` porte 450 kg au 30 mars dans celui du 30 mars. Les photos `Stocks!E1272` et `E1047` passent de 132,725 kg le 24 mars à 558,840 kg le 31 mars. Cette hausse corrobore une entrée fin mars ; elle n'identifie ni la date de commande ni un délai fournisseur réellement exécuté de 35 jours.

Le carnet initial ne contient pas non plus la date de création des commandes. Son intervalle livraison→disponibilité porte sur le traitement de réception : 99 dates sur 104 sont expliquées par les jours ouvrés et fériés dans l'audit précédent ; ce n'est pas une statistique de ponctualité du fournisseur. **Les 93,3 % de stabilité des plans et les 21,6 % de délais simulés proches de la référence ne sont donc pas deux mesures comparables directement.** Les sources ne justifient actuellement ni la forte dispersion Erlang du nominal ni, inversement, une nouvelle hypothèse arbitraire « fournisseurs toujours à ±7 jours ».

Aucun moteur ni résultat de simulation n'a été modifié pour cette analyse. La prochaine comparaison causale doit séparer délai FIA déterministe pour identifier les décisions MRP, traitement de réception documenté et scénario d'incertitude distinct. La variabilité empirique des fournisseurs reste à estimer avec des rapprochements explicitement qualifiés.

Preuves : [mesures simulées](../../artifacts/testing/gaillac_039668_20260930/delivery_variation.json), [révisions des plans et lignes sources](../../artifacts/testing/gaillac_039668_20260930/delivery_source_revision.json). Le parent et un agent en lecture seule retrouvent indépendamment les compteurs sources. L'agent a également contre-vérifié les 2 093 identités délai = réception physique − lancement, l'unicité des ordres et les statistiques simulées indiquées ci-dessus : 2 130 contrôles, aucun écart ; les percentiles accessoires du JSON ne sont pas inclus dans cette contre-vérification. Cette analyse de fichiers existants n'est pas une nouvelle qualification de simulation.

## Livraison Gaillac et diagnostic 039668 — 30 septembre 2026

La [carte complète](../../resultats/regroupement_001757_20260929/carte_gaillac_039668.html) conserve les vues historiques et leurs deux suivis de lots. Son bouton « Gaillac et 039668 · comparaison » ouvre les deux nouveaux calculs ; la [comparaison directe](../../resultats/regroupement_001757_20260929/comparaison_gaillac_039668.html) présente les mêmes données. Les références précédentes sont conservées. Les autres onglets historiques ne sont pas présentés comme les résultats du nouvel essai.

### Gaillac : représentation livrée et limites physiques

Le site actif `SDC-1450` reste une usine et porte désormais explicitement les fonctions réception, stockage, fabrication et expédition. Son nom devient « Gaillac — fabrication et stockage (D-1450) ». Aucun stock, procédé ni transport n'est créé par ce changement. Le nœud vide `DC-1450` était déjà absent de la carte compacte historique ; il ne s'agit pas d'un nouvel entrepôt supprimé.

L'onglet **Gaillac · fabrication et stockage** présente les cinq articles sources, la date de photo sélectionnable, les stocks disponible, indisponible et réservé, et les mouvements simulés séparés : achats, production, transport, consommation et libération. 001893 et 002612 y restent explicitement hors simulation physique. Le réapprovisionnement agrégé de 693055 apparaît comme « apport amont simplifié », sans le transformer en fabrication démontrée. Les liens des articles ouvrent leurs courbes.

Un tableau convertit quatre positions distinctes en **équivalent théorique de PF 268967** : 021081 à Gaillac, 773474 à Gaillac et à Gien, 268967 au dépôt. Les BOM donnent 8,94 kg de matière par kg intermédiaire et 0,009654718 kg intermédiaire par PF. Les résultats ne constituent pas une couverture industrielle : stocks potentiellement partagés, absence d'allocation, transit, encours et PF en usine exclus. Un stock ou un facteur absent donne une valeur absente, jamais zéro. L'objectif d'un an sur la chaîne ne devient pas un an de sécurité par site.

Deux simulations de **1 825 jours** sont terminées. La référence reproduit tous les résultats physiques antérieurs : **36 CSV identiques octet pour octet ; dans le 37e, seul le nom de Gaillac change sur trois lignes**. Le moteur est resté identique pendant les deux exécutions. La comparaison industrielle concerne uniquement 2025.

### 039668 : sources recoupées

| Paramètre | Valeur et provenance |
|---|---|
| Usage dans 268091 | 40,6 g pour 1 000 PF, soit 0,0000406 kg/PF ; `268091.xlsx/BOM!A8:F8`, `demand_PF.xlsx/BOM` ligne 40 |
| Fournisseur renseigné | VD1096202A ; `268091.xlsx/FIA!A14:H14` |
| Prix | 12,21 EUR/kg |
| Délai fournisseur de référence | 35 jours calendaires, `FIA!F14` |
| Quantité standard | 450 kg, `FIA!G14:H14` ; ne prouve pas un multiple obligatoire pour chaque ordre |
| Réception | 1 jour, E du flux MRP, constant dans les 52 versions |
| Sécurité | 7 jours ouvrés ; stock de sécurité fixe nul, sans supprimer la protection temporelle ; politique source ligne 18, ancienne politique ligne 10 |
| Stock initial | 459 695 g = 459,695 kg ; ancienne feuille Stocks ligne 15, nouvelle ligne 1045 |
| Valeur initiale | 5 612,87595 EUR = 459,695 × 12,21 ; nouvelle feuille Stocks F1045 |

Ces rapprochements ne montrent pas d'erreur d'un facteur 1 000. Aucun ordre initial de 039668 n'est repris du carnet. Les photos hebdomadaires concernent tout le stock Avène ; la BOM étudiée ne couvre que 268091.

**Premier défaut identifié : le complément de besoins pour les autres produits est figé sur janvier.** La référence conserve 34 périodes futures issues du premier plan, totalisant 823,065439 kg, et aucune période après le 25 octobre. Cette absence est une limite du scénario, pas une consommation industrielle nulle démontrée. Le plan initial contient 993,35 kg de besoins futurs, ou 1 026,35 kg en incluant la semaine courante. La part complémentaire estimée est 82,8575466 % ; ce n'est pas une allocation industrielle connue.

L'essai isolé réutilise le mécanisme commun de prévisions versionnées : 52 versions, 1 773 lignes futures, uniquement les versions connues à la date de décision, semaine courante figée. Il conserve la part initiale estimée, les quantités standard, prix, sécurité et politiques de délai. Il n'utilise ni les stocks futurs ni H/K pour ajuster cette part. Les I restent des besoins prévus, non des consommations exécutées observées.

### Résultats de l'essai — référence conservée

| Indicateur 039668 / Avène en 2025 | Référence | Prévisions révisées |
|---|---:|---:|
| Écart absolu moyen aux 52 photos, kg | 175,27 | 178,27 |
| Biais moyen simulé − source, kg | −150,44 | −92,66 |
| Nouveaux ordres lancés | 2 × 450 kg | 4 × 450 kg |
| Quantité physiquement reçue pendant 2025 | 450 kg | 1 350 kg |
| Consommation simulée pour 268091 | 46,7712 kg | 46,7712 kg |
| Consommation complémentaire estimée | 823,0654 kg | 1 657,3995 kg |
| Jours de clôture avec stock physique nul | 15 | 29 |
| Stock physique au 31 décembre | 39,8584 kg | 105,5243 kg |

Les photos sont rapprochées de la clôture simulée de la veille, ouverture exclue. Le 29 décembre, la source indique **479,795 kg** : ce n'est pas une photo au 31 décembre. La variante réduit le biais, mais dégrade l'écart absolu moyen de 1,71 % et augmente les jours de stock physique nul ; **elle ne remplace pas la référence**. Les améliorations de juillet et novembre ne compensent pas les dégradations d'avril et octobre. Sur les 29 couples comparables : 7 écarts moyens diminuent, 8 augmentent, 14 sont inchangés ; aucune somme entre unités. L'un des couples inchangés, 001848/Gien, n'a qu'un périmètre partiel d'engagements initiaux.

Le service client 2025 est identique dans les deux essais. Sur cinq ans, les quantités servies restent identiques ; le cumul quantité × jours de retard de 268091 diminue, de 542,33 à 495,07 millions d'UN·jours. Ce résultat ne valide pas une calibration industrielle sur cinq ans : les versions sources disponibles s'arrêtent en 2025.

**Deuxième problème à isoler : les délais tirés ne sont pas appariés entre les commandes des deux calculs.** Dans la référence, la première commande part le 23 mars, reçoit un délai fournisseur de 56 jours au lieu des 35 jours de référence, arrive le 18 mai et devient disponible le 19 mai. Dans l'essai, elle part le 5 mars, mais reçoit 70 jours : arrivée le 14 mai, disponibilité le 15 mai. À graine égale, une décision modifiée ne garantit pas les mêmes tirages par commande ; cet essai ne mesure donc pas l'effet pur du seul calendrier des besoins. Les délais tirés des quatre commandes de l'essai sont 70, 33, 27 et 52 jours, toujours pour une référence de 35 jours.

Les H de la semaine courante des plans du 30 mars, 22 juin, 26 octobre et 7 décembre portent respectivement **450, 450, 250 et 399,85 kg** (`Feuille1!H12443`, `H24453`, `H43135`, `H49534`). Des hausses de stocks proches suivent dans les photos. Cela corrobore des entrées à ces périodes, sans identifier quatre commandes exécutées ni leurs dates de création. Même avec 35 jours fixes après un lancement le 23 mars, la disponibilité tomberait le 28 avril : le tirage aléatoire n'explique donc pas à lui seul le décalage par rapport à la hausse source de fin mars.

**Suite commune à tester :** conserver la reconstruction des versions connues, mais comparer d'abord deux essais avec délais de référence déterministes pour isoler le déclenchement. Vérifier ensuite, pour chaque besoin daté, le stock utilisable, les engagements attendus, la sécurité et la taille standard au moment où une proposition devient nécessaire. Confronter les dates et quantités obtenues aux semaines H et aux photos, puis tester cette même règle sur d'autres matières. Ne pas ajouter de coefficient propre à 039668, forcer une réception sur une photo, ni considérer toutes les variations de I comme des consommations industrielles certaines.

Preuves : [protocole de référence](../../artifacts/testing/gaillac_039668_20260930/study/plan.json), [protocole de la variante](../../artifacts/testing/gaillac_039668_20260930/study/revisions_plan.json), [analyse des résultats](../../artifacts/testing/gaillac_039668_20260930/analysis.json), [97 contrôles indépendants](../../artifacts/testing/gaillac_039668_20260930/validation/final.json), [manifeste de livraison](../../artifacts/testing/gaillac_039668_20260930/manifest.json). Les contrôles arithmétiques ne certifient pas les règles industrielles absentes des sources.

## Gaillac : fabrication et stockage — revue du 30 septembre 2026

**Gaillac doit être traité comme un site assurant plusieurs fonctions : réception, stockage, fabrication et expédition.** Le stockage est déjà partiellement représenté ; le défaut principal est son périmètre incomplet, puis la représentation incomplète de la fabrication de 693055. Cette revue ne modifie pas le moteur, les flux ni les simulations de référence.

Le rapprochement porte sur le graphe effectivement utilisé par les derniers témoins (`artifacts/testing/mrp_delivery_rules_20260930/study/graph.json`), les sources Excel et les [plans MRP déjà audités](../../artifacts/testing/mrp_full_flow_audit_20260930/flows/results.json). Les quinze entrées enregistrées de cet audit ont été relues et leurs empreintes sont inchangées. Deux analyses indépendantes ont couvert les sources et le modèle ; aucun nouveau test, navigateur ou calcul physique n'a été lancé pour cette revue.

### Cinq stocks industriels, trois dans le modèle

Quantités en **kg**, y compris 693055 et 773474 convertis depuis les grammes sources. Les valeurs de fin sont les **photos du 29 décembre**, pas une clôture inventée au 31 décembre. Chaque article dispose de 53 photos, ouverture du 1er janvier comprise.

| Article à Gaillac | Stock au 1er janvier 2025 | Stock au 29 décembre 2025 | Représentation actuelle |
|---|---:|---:|---|
| 001893 | 1 094 | 979,5 | Stock source présent, absent du périmètre physique simulé |
| 002612 | 414 | 277,5 | Stock source présent, absent du périmètre physique simulé |
| 021081 | 1 142 100 | 1 534 614 | Stock représenté ; matière de la fabrication de 773474 |
| 693055 | 1 800 | 10 | Stock et transfert vers Avène représentés ; fabrication amont agrégée |
| 773474 | 9 600 | 35 200 | Stock, fabrication locale et transfert vers Gien représentés |

Provenance : `Flow_Data_Inventory_and_Replenishment_rules.xlsx/Stocks`, colonne E pour la quantité et H pour la date. Lignes initiale/finale respectives : 001893 **1406/845**, 002612 **1435/817**, 021081 **1576/579**, 693055 **1051/1474**, 773474 **209/1528**. Les deux stocks absents du modèle figuraient déjà dans `Extract_Données_Complémentaires.xlsx/Stocks`, lignes 5 et 7 : ce ne sont pas de nouveaux stocks apparus seulement dans le fichier hebdomadaire.

### Fonctions et routes prouvées, sorties restant à attribuer

`demand_PF.xlsx/Acteurs!A7:K7` décrit Gaillac comme fabricant de **693055 et 773474**. Les ordres `O.Proc` du carnet initial, `Extract_En_cours.xlsx/Sheet1`, lignes **103 et 105**, portent respectivement 600 kg et 3 200 kg de ces produits à Gaillac.

- **021081 → 773474 à Gaillac** : BOM de `773474.xlsx`, ligne 2, 8,94 kg de matière pour 1 kg de produit intermédiaire.
- **773474 : Gaillac → Gien** : `demand_PF.xlsx/Relations_acteurs`, ligne 9, et `268967.xlsx/FIA`, ligne 9. Les 10 jours FIA sont un délai d'approvisionnement interne ; ils ne prouvent pas dix jours de trajet routier.
- **693055 : Gaillac → Avène** : `demand_PF.xlsx/Relations_acteurs`, ligne 36, et `268091.xlsx/FIA`, ligne 22. Même distinction pour les 70 jours indiqués. Le BOM amont de 693055 manque ; le moteur représente actuellement son réapprovisionnement agrégé par 600 kg avec une convention de délai, pas sa fabrication physique complète.
- **001893 et 002612 à Gaillac** : le stockage et des besoins MRP sont prouvés, mais les sources examinées ne donnent pas de route Gaillac → Avène pour ces matières. Les routes renseignées vers Avène viennent de fournisseurs externes. Les ordres du carnet en division **1820** ne doivent pas être réaffectés à 1450 ou 1810 sans correspondance explicite.

Pour le plan du 5 janvier, les sorties I de Gaillac comprennent **607,103 kg de 001893** le 23 février et le 13 juillet (`Feuille1!I115`, `I117`), puis **1 300 et 245 kg de 002612** les 23 février et 16 mars (`I160`, `I161`). Le rapprochement exploratoire de toutes les versions, sur les cibles 2025, trouve **zéro égalité de quantité** entre ces I à Gaillac et un H à Avène la même semaine ou la suivante : 92 occurrences positives examinées pour 001893, 215 pour 002612. Ce sont des occurrences dans des plans révisés, pas des commandes annuelles. L'absence de correspondance directe ne prouve pas l'absence de transferts fractionnés, regroupés ou décalés ; elle interdit simplement de présenter un routage vers Avène comme déjà reconstitué.

### Correction à préparer sans inventer les flux

1. **Un seul site physique Gaillac, plusieurs fonctions.** Le graphe porte `SDC-1450`, type `factory`, avec les trois stocks actifs, et un `DC-1450` vide, isolé. Ce second nœud ne représente pas un second entrepôt industriel démontré. Conserver l'identifiant actif et réconcilier les alias avant de retirer le doublon d'affichage ; ne pas dupliquer les quantités.
2. **Présenter les cinq stocks dans la vue site**, avec les deux matières manquantes explicitement marquées « stock source ; flux non représentés ». Leur future intégration physique exige d'attribuer leurs entrées et sorties ; ajouter un stock initial immobile ne reproduirait pas leur gestion réelle.
3. **Séparer les opérations** : achat externe, fabrication locale, transfert interne, consommation et libération du stock déjà détenu. Le passage indisponible → disponible conserve la quantité physique. Exemple 773474 au 5 janvier : 6 400 kg disponibles + 3 200 kg disponibles plus tard = 9 600 kg déjà présents (`Feuille1!J968`, `J970`), pas 3 200 kg de nouvelle réception.
4. **Séparer les calendriers et les limites** : fermeture de production, réception, libération et expédition ne sont pas interchangeables. Aucune capacité maximale d'entreposage documentée n'est actuellement portée par le graphe. Le maximum de stock observé n'est pas une capacité d'entrepôt ; les limites de lots de fabrication n'en sont pas une non plus. Les coûts d'entreposage actuels sont des conventions, et ceux des deux PFI ne disposent pas d'un taux exploitable : un coût nul par défaut ne signifie pas stockage gratuit.
5. **Calculer la couverture de 268967 sur toute la chaîne** : convertir les stocks distincts de 021081, de 773474 et des PF en équivalent PF avec les BOM et rendements applicables, en distinguant disponible, indisponible et transit. L'objectif utilisateur d'environ un an concerne le total de la chaîne, pas une année de sécurité ajoutée à chaque site ; il ne s'applique pas automatiquement à 001893, 002612 ou 693055. Une matière déjà consommée ne doit plus figurer simultanément en stock amont et dans le produit fabriqué.

**Décision de cette revue :** rôle mixte Gaillac confirmé ; routages PFI confirmés ; rôle de réserve des deux autres matières pour Avène non établi. Priorité à compléter la vue des stocks et à expliquer leurs mouvements, avant de modifier le pilotage MRP ou de créer des transferts. Les soldes nets des photos et les H/I prévisionnels ne suffisent pas à attribuer chaque mouvement exécuté.

## Essai du calendrier de réception dans le moteur — 30 septembre 2026

Une option **désactivée par défaut** accepte désormais des dates non ouvrées explicites dans chaque politique de réception fournisseur : `nonworking_dates`, `calendar_id`, `calendar_status`, `calendar_source`. L'opérateur commun compte les jours lundi–vendredi après la livraison G, en excluant les dates renseignées, jusqu'à atteindre E jours de réception. E = 0 conserve G. Les dates sont absolues : aucune répétition annuelle n'est déduite d'une liste 2025.

Le calendrier intervient aux trois endroits du parcours d'achat externe daté : délai de référence au jour de décision, calendrier des offres principal/secours, disponibilité I des nouveaux ordres lancés. Les dates G/I du carnet initial, J détenu initialement, le délai fournisseur FIA, la sécurité, les fabrications et les transferts internes ne sont pas recalculés par cette option. Les 39 cas ciblés en mémoire passent ; le comportement historique sans dates supplémentaires reste couvert.

Le [protocole comparatif](../../artifacts/testing/mrp_receipt_calendar_20260930/study/plan.json) prévoit deux simulations de **1 825 jours**, mêmes paramètres et aléas configurés. `reference` conserve le graphe précédent ; `calendar` ajoute seulement les fériés métropolitains 2025 aux **22 couples d'achats externes concernés**, plus la fermeture du 4 au 17 août pour le seul couple 021081/Gaillac. Cette portée reste une hypothèse conditionnelle de calendrier de réception, pas un arrêt généralisé de l'entreprise. La comparaison industrielle porte uniquement sur 2025 ; les années suivantes testent la stabilité et la propagation, sans calendrier annuel extrapolé.

**Point de contrôle causal :** la référence n'a aucun nouvel achat de 021081 en 2025 ; le premier est au jour 554, le 9 juillet 2026. Les engagements initiaux ont déjà leurs dates G/I renseignées. On n'attend donc aucun effet direct de la fermeture 2025 sur les nouvelles réceptions de ce composant ; un changement à Gaillac peut venir indirectement du reste du réseau. L'expérience ne doit pas être présentée comme une correction des 23 commandes initiales.

**Limite du planificateur :** hors sourcing explicite, les propositions futures utilisent encore un délai entier recalculé au jour de décision. Chaque ordre réellement lancé recalcule sa disponibilité exacte depuis sa livraison et son calendrier ; le calendrier des offres principal/secours est également daté. Une résolution exacte de toutes les dates futures de proposition relève d'un changement distinct. Les comparaisons H/K des plans restent diagnostiques, notamment parce que H source et les entrées simulées ne sont pas forcément datés au même stade physique/disponible.

Les preuves sources et le différentiel des graphes sont contre-vérifiés dans [input_check.json](../../artifacts/testing/mrp_receipt_calendar_20260930/validation/input_check.json). Les deux simulations de 1 825 jours sont terminées, avec le moteur inchangé pendant les calculs. Sans activation du calendrier, les 37 CSV du témoin reproduisent ceux de la référence précédente à l'identique. Les invariants des deux calculs et le recalcul indépendant des dates G/E/I, des stocks tenus et des lots passent ; voir [la contre-vérification](../../artifacts/testing/mrp_receipt_calendar_20260930/validation/runs_check.json) et [le manifeste de cette passe](../../artifacts/testing/mrp_receipt_calendar_20260930/manifest.json). La même graine aléatoire est conservée ; après une modification des décisions, cela ne garantit pas un tirage identique pour chaque commande correspondante.

### Résultat et décision

**Le calendrier est mieux explicité, mais cette variante ne constitue pas une amélioration générale de calibration. Elle reste optionnelle et ne remplace pas la référence.** Sur les 28 couples article/site avec stock représenté dans le graphe et photos comparables, l'écart absolu moyen aux stocks sources diminue pour 14, augmente pour 11 et reste identique pour 3. Le 29e couple comparable, 001848/Gien, n'est représenté que par les engagements initiaux ; son résultat inchangé est compté séparément. Les unités ne sont pas additionnées entre articles.

L'écart ci-dessous compare le stock physique simulé (disponible + réservé + indisponible) en clôture de la veille aux photos du lundi de 2025. La photo initiale n'entre pas dans cette moyenne et les données absentes ne sont pas remplacées par zéro.

| Article / site | Unité | Écart moyen de référence | Avec calendrier | Lecture |
|---|---|---:|---:|---|
| 001757 / Avène | kg | 2 637,03 | 2 802,79 | Dégradation de 165,75 kg |
| 001848 / Avène | kg | 2 325,64 | 2 321,37 | Amélioration faible |
| 002612 / Avène | kg | 70 412,23 | 69 066,11 | Amélioration, écart encore important |
| 038005 / Gien | kg | 26 458,01 | 28 752,57 | Dégradation |
| 042342 / Gien | UN | 35 955 023,48 | 36 242 836,54 | Dégradation ; périmètre partagé toujours à considérer |
| 338929 / Avène | UN | 1 005 257,15 | 1 004 517,35 | Amélioration faible |
| 021081 / Gaillac | kg | 233 299,65 | 233 299,65 | Aucun effet, conformément au contrôle causal |

Le **service client 2025 reste identique** : 3 528 253 UN servies pour 268091, avec environ 48 189 UN en attente en fin d'année ; 1 575 985 UN servies pour 268967, avec un reliquat prévisionnel inférieur à une unité. Sur les cinq ans, les quantités totales servies et le cumul quantité × jours de retard sont également identiques. Cela ne démontre pas une correspondance avec le service industriel réel.

À dates de livraison G, délais E et quantités de commande du témoin fixés, l'ajout du calendrier reporte la disponibilité de **79 nouveaux ordres sur 389 lancés en 2025**, de 1 à 5 jours calendaires ; les 310 autres restent identiques. Ce calcul isole l'effet direct sur les dates et n'est pas une troisième simulation. Dans la simulation complète, les décisions peuvent ensuite changer : 001757 passe de **147 à 141 nouveaux ordres**, pour **34 700 kg commandés dans les deux cas** ; 001848 conserve quatre ordres et 22 000 kg, dont trois ordres au principal et un au secours. Ces compteurs excluent les engagements initiaux et ne sont pas des nombres de commandes industrielles déduits des versions hebdomadaires MRP.

Les projections MRP ne donnent pas non plus une amélioration uniforme. Pour 001757, l'écart moyen de K projeté passe de 2 947,41 à 3 104,19 kg. Pour 693055/Gaillac, il reste proche de 1 387 kg. Les comparaisons de H restent diagnostiques tant que les dates physiques et disponibles ne sont pas strictement alignées ; les versions successives d'un plan ne sont pas additionnées comme des flux exécutés.

**Suite prioritaire :** expliquer le déclenchement et le regroupement des propositions à partir des besoins datés, du stock disponible, des engagements et de la sécurité. Utiliser 001757 pour identifier une règle candidate, puis la confronter à 001848, 693055 et aux autres articles sans coefficients ajustés par période. Le calendrier testé est une brique métier distincte, pas une justification pour modifier les quantités de sécurité ou forcer les courbes de stock.

Résultats complets : [comparaison par couple](../../artifacts/testing/mrp_receipt_calendar_20260930/stock_comparison.csv), [flux, service et projections](../../artifacts/testing/mrp_receipt_calendar_20260930/comparison.json). Les durées des calculs parallèles sont d'environ 618 et 623 secondes ; ce ne sont pas des mesures isolées de performance. Aucune nouvelle carte HTML n'a été générée dans cette passe.

## Complément : fermeture d'août 2025 — 30 septembre 2026

L'utilisateur indique une fermeture de l'entreprise pendant les **deux ou trois premières semaines d'août**. Les dates exactes et le périmètre (sites, production, réception, contrôle/libération) ne sont pas encore précisés. Cette information justifie une passe ciblée sur les calendriers et les signatures de stock ; elle ne transforme pas toutes les semaines sans mouvement en fermetures démontrées.

Quatre interprétations calendaires ont été fixées avant le calcul, sans recherche automatique des dates donnant le meilleur ajustement. Toutes conservent lundi–vendredi et les jours fériés métropolitains 2025, puis suspendent le compteur du délai de réception pendant l'intervalle candidat. Les dates de livraison G, durées H et disponibilités I des **104 lignes du carnet initial** sont relues directement.

| Fermeture candidate, bornes incluses | Dates I reproduites | Écarts restants |
|---|---:|---|
| Aucune fermeture estivale, jours fériés seulement | 99/104 | Cinq lignes de 021081/Gaillac |
| **4–17 août : deux premières semaines complètes** | **104/104** | Aucun |
| 4–24 août : trois premières semaines complètes | 99/104 | Les cinq dates sont prédites sept jours trop tard |
| 1–14 août : quatorze premiers jours calendaires | 99/104 | Les mêmes cinq lignes restent décalées |
| 1–21 août : vingt et un premiers jours calendaires | 99/104 | Les cinq dates sont prédites sept jours trop tard |

**Les neuf jours supplémentaires sont expliqués par les 4–8 et 11–14 août**, le vendredi 15 août étant déjà exclu comme férié. Exemple `Extract_En_cours/Sheet1!G23:I23` : livraison le 16 avril, temps de réception 75 jours, disponibilité indiquée le **21 août**. Le calcul donne le 7 août sans fermeture estivale, **le 21 août avec fermeture 4–17 août**, et le 28 août avec fermeture 4–24 août. Autre exemple, ligne 25 : livraison le 20 mai, disponibilité le **19 septembre**, reproduite par la même règle, sans coefficient propre à l'article ou au mois.

**Portée de la preuve :** seules cinq lignes (23, 25, 30, 39 et 42), toutes sur 021081 à Gaillac, permettent de départager les candidats. Les 99 autres restent identiques dans tous les essais ; deux des cinq lignes partagent les mêmes dates. Le résultat étaye donc fortement ce **calendrier de réception/disponibilité à Gaillac parmi les hypothèses testées**, mais ne démontre pas deux semaines de fermeture pour toutes les usines et toutes les fonctions. Une fermeture de production de trois semaines peut coexister avec une disponibilité qualité reprenant plus tôt. Les dates du carnet sont des dates documentées, pas la preuve de leur exécution industrielle ultérieure.

La règle candidate se formule ainsi : **date disponible = avancer depuis la date de livraison du nombre de jours de réception renseigné, en utilisant le calendrier applicable à la fonction et au site**. Elle ne change ni le délai fournisseur FIA, ni les jours de sécurité, ni les dates déjà explicites du carnet. L'intégration dans le moteur reste à qualifier séparément ; aucune modification du nominal n'est faite par cette passe.

Cette hypothèse suspend le **décompte des jours de réception pendant la fermeture** ; il ne suffit pas de déplacer au jour de reprise une disponibilité qui tomberait pendant les congés. La ligne 25 le montre : sans fermeture, le calcul donne le 8 septembre, déjà hors août ; le carnet donne le 19 septembre. Le décompte suspendu retrouve le 19 septembre. Cela ne démontre pas que tous les phénomènes physiques ou chimiques sont suspendus, seulement que ce calendrier explique le délai de gestion représenté par les dates du carnet.

### Croisement avec les photos et les plans de l'été

La passe complémentaire couvre tous les couples dans les plans de juin à septembre. Le tableau indique le nombre de références dont la quantité physique photographiée est **strictement identique entre les deux lundis**. Les références sans deux photos sont exclues, pas remplacées par zéro.

| Site | 28 juillet → 4 août | 4 → 11 août | 11 → 18 août | 18 → 25 août |
|---|---:|---:|---:|---:|
| Avène | 15/15 | 15/15 | 15/15 | 0/15 |
| Gaillac | 5/5 | 5/5 | 5/5 | 4/5 |
| Gien | 3/9 | 2/9 | 9/9 | 5/9 |
| Dépôt Muret | 0/2 | 0/2 | 0/2 | 0/2 |

À Avène, les 15 stocks changent également du 21 au 28 juillet : le plateau commun est donc borné par les photos **28 juillet–18 août**, soit trois intervalles hebdomadaires, puis tous changent du 18 au 25 août. À Gaillac, les cinq stocks étaient déjà stables du 21 au 28 juillet ; on ne peut pas y dater le début de fermeture à partir de ce seul plateau. Gien montre des changements plus tardifs et le dépôt continue à varier. C'est compatible avec des calendriers différents selon le site ou la fonction. Une photo inchangée peut aussi refléter des mouvements compensés ou une photo reconduite : elle ne démontre pas à elle seule l'absence de tout flux brut.

Deux exemples expliquent pourquoi il faut séparer les flux :

- **001757/Avène**, plans des 27 juillet, 3 et 10 août : H = 2 000 kg et I = 1 200 kg sont reconduits, avec J courant = 3 855,020 kg et J futur = 1 975 kg. Les photos restent à 5 830,020 kg. Les I répétés ne constituent pas une preuve de consommations réalisées pendant la fermeture (`I29064/I30080/I31120`).
- **021081/Gaillac**, plans des 17 et 24 août : J courant passe de **455 560 à 955 320 kg**, J futur de **1 319 640 à 819 880 kg**, mais le total reste **1 775 200 kg**, égal aux photos correspondantes. Les 499 760 kg passent du stock détenu disponible plus tard au stock courant (`J32433`, puis `J33461`) : ce n'est pas une nouvelle livraison physique de 499 760 kg.

Ces observations ne justifient pas un blocage unique de tout le réseau pendant trois semaines. La suite doit distinguer les calendriers de **fabrication, réception physique, mise à disposition et expédition**, ainsi que le report des besoins non exécutés. Le calendrier fournisseur et le calcul de sécurité ne doivent pas être modifiés par propagation implicite de la fermeture de l'usine. Les années autres que 2025 nécessitent leur propre calendrier ou une convention explicitement déclarée.

Les détails de cette passe sont dans [les rapprochements été](../../artifacts/testing/mrp_august_closure_20260930/flows/results.json) et [la contre-vérification des photos](../../artifacts/testing/mrp_august_closure_20260930/validation/august_stock_check.json).

Preuves : [calcul des candidats](../../artifacts/testing/mrp_august_closure_20260930/calendar.json), [oracle indépendant](../../artifacts/testing/mrp_august_closure_20260930/validation/closure_check.json), [manifeste de cette passe](../../artifacts/testing/mrp_august_closure_20260930/manifest.json). La conclusion de l'audit antérieur « cinq dates restent inexpliquées » est désormais précisée par cette nouvelle information utilisateur et cette hypothèse testée ; ses preuves historiques restent conservées.

## Audit exhaustif des flux et des stocks 2025 — 30 septembre 2026

**Conclusion : les données permettent un rapprochement beaucoup plus précis, mais il serait faux de dire que toutes les règles industrielles sont déjà respectées par la simulation.** Les conversions BOM sont cohérentes ; les stocks détenus et disponibles sont distingués ; les principales incertitudes concernent les calendriers de réception, les usages partagés, les catalogues fournisseurs et le déclenchement des achats/fabrications. Cet audit ne change ni le moteur, ni les Excel, ni le nominal, ni les cartes conservées.

La preuve courante est [le manifeste de cet audit](../../artifacts/testing/mrp_full_flow_audit_20260930/manifest.json). Il rassemble une extraction exhaustive, une lecture du code et une contre-vérification indépendante. Les simulations utilisées sont les calculs existants `mrp_delivery_rules_20260930/study/reference` et `fia_fixe`, exécutés sur 1 825 jours ; **seule leur première année, 2025, est rapprochée ici**. Aucune nouvelle simulation ni campagne de tests artificiels n'a été exécutée pour cet audit en lecture seule.

### Périmètre et sens des données

- **53 398 lignes MRP**, 26 articles, 33 couples article/site, quatre sites et 52 dates de plan globales ; **1 637 plans article/site**. Tous les couples n'ont pas 52 versions : 029313/Gien en a huit, 344135/Gien en a 17, à partir du 7 septembre.
- **1 646 photos de stock sur 32 couples**, dont 31 photos au 1er janvier et 1 615 photos du lundi. 029313/Gien n'a pas de photo ; 344135/Gien n'en a que trois.
- **104 lignes du carnet initial** : 53 `AVICDE`, 29 `ECHCDE`, 22 `O.Proc`. Ce sont des éléments existants, pas un historique des commandes créées pendant toute l'année ; aucun identifiant d'ordre ni date de création n'est ajouté par l'audit.
- **35 offres FIA**, dont 33 externes et deux approvisionnements internes, pour 24 couples. Six couples ont plusieurs offres. Le détail des prix, bases, devises, standards, délais et cellules se trouve dans le [catalogue fournisseurs](../../artifacts/testing/mrp_purchase_parameters_20260930/extraction/purchase_offers.csv), dont les 12 empreintes Excel ont été revérifiées.
- **24 lignes de nomenclature industrielle**, normalisées et rapprochées des anciens classeurs et du graphe réellement simulé : [détail BOM](../../artifacts/testing/mrp_full_flow_audit_20260930/bom_crosswalk.csv).

Dans `Flow_Data_MRP_results/Feuille1`, **H = entrées projetées**, **I = besoins**, **J = stock déjà détenu, ventilé selon sa disponibilité**, **K = solde projeté**. La colonne E contient le temps de réception, pas le délai fournisseur FIA. Les unités G sont converties en KG ; ZUN en UN ; M reste en mètres. Toutes les lignes sont lues, y compris masquées.

Les 53 398 bilans `K = K précédent + J + H − I` concordent, sans doublon de clé. Cela vérifie la cohérence arithmétique de l'export, pas sa réalisation physique. **19 359 semaines internes ne sont pas renseignées**, dans 1 480 plans ; 1 492 plans s'arrêtent avant la borne de 364 jours. Aucun besoin ni flux brut n'est déclaré nul dans ces semaines par l'audit. Un bilan net inchangé entre deux lignes ne permet pas de séparer les entrées et sorties absentes.

### Quantités et fréquence, pour chacun des 33 couples

Le tableau donne les échéances 2025 du **premier plan disponible par couple** : 5 janvier, sauf 344135/Gien au 7 septembre. « Sem. H+ » compte les semaines où une entrée est projetée : **ce n'est pas le nombre de commandes individuelles réellement passées**. Les semaines absentes sont exclues, sans annualisation. Le [CSV complet](../../artifacts/testing/mrp_full_flow_audit_20260930/flows/summary.csv) ajoute les besoins, tailles médianes, intervalles entre entrées et une seconde lecture des semaines courantes des versions successives ; cette seconde lecture reste un ensemble de prévisions, pas un historique exécuté.

La dernière colonne mesure l'écart absolu moyen entre les stocks physiques de la simulation de référence et les photos réelles de 2025, dans l'unité de la ligne. La clôture simulée de la veille est comparée à chaque photo du lundi ; 52 photos par couple, **sauf 344135 : trois seulement**. « Absent » signifie pas de comparaison, jamais stock nul. Les quatre absences sont trois couples hors du registre physique simulé et 029313/Gien sans photo. Les périmètres industriels partagés restent à considérer : une erreur de stock ne mesure pas à elle seule la qualité de la règle MRP.

Sites : 1810 Avène ; 1430 Gien ; 1450 Gaillac ; 1920 dépôt Muret. E est le temps de réception déclaré dans le flux MRP.

| Article/site | Unité | Sem. renseignées | Sem. H+ | Quantité H projetée | E jours | Écart moyen stock référence |
|---|---|---:|---:|---:|---:|---:|
| 001757/1810 | KG | 32 | 10 | 18000.000 | 13 | 2637.0 |
| 001848/1430 | KG | 48 | 14 | 98000.000 | 26 | 23408.3 |
| 001848/1810 | KG | 30 | 2 | 9331.160 | 13 | 2325.6 |
| 001893/1450 | KG | 5 | 2 | 700.000 | 5 | absent |
| 001893/1810 | KG | 40 | 32 | 188308.217 | 24 | 37166.9 |
| 002612/1450 | KG | 4 | 2 | 2500.000 | 5 | absent |
| 002612/1810 | KG | 40 | 10 | 210505.604 | 9 | 70412.2 |
| 007923/1430 | KG | 1 | 0 | 0.000 | 0 | absent |
| 007923/1810 | KG | 38 | 6 | 114510.000 | 6 | 25951.4 |
| 016332/1810 | KG | 36 | 21 | 6892.960 | 1 | 484.4 |
| 021081/1450 | KG | 35 | 14 | 1320000.000 | 75 | 233299.7 |
| 029313/1430 | KG | 1 | 0 | 0.000 | 0 | absent |
| 029313/1810 | KG | 31 | 3 | 859.175 | 1 | 138.2 |
| 038005/1430 | KG | 39 | 15 | 160000.000 | 14 | 26458.0 |
| 039668/1810 | KG | 35 | 2 | 572.655 | 1 | 175.3 |
| 042342/1430 | UN | 24 | 8 | 240000000.000 | 14 | 35955023.5 |
| 049371/1810 | KG | 29 | 8 | 21600.000 | 9 | 3891.3 |
| 055703/1810 | KG | 35 | 5 | 1301.565 | 13 | 451.4 |
| 099439/1810 | KG | 37 | 24 | 38257.258 | 1 | 2792.1 |
| 268091/1920 | UN | 48 | 48 | 4450277.000 | 10 | 491987.6 |
| 268967/1920 | UN | 52 | 30 | 1594134.000 | 15 | 388933.9 |
| 333362/1430 | UN | 18 | 9 | 1346000.000 | 5 | 338282.1 |
| 338928/1810 | UN | 41 | 32 | 4431930.000 | 6 | 605222.6 |
| 338929/1810 | UN | 39 | 23 | 3055636.000 | 6 | 1005257.2 |
| 344135/1430 | UN | 3 | 2 | 331537.000 | 4 | 564999.0 |
| 426331/1810 | UN | 41 | 10 | 108560.000 | 1 | 7251.0 |
| 693055/1450 | KG | 26 | 16 | 11400.000 | 28 | 856.9 |
| 693055/1810 | KG | 39 | 17 | 10800.000 | 7 | 708.4 |
| 708073/1430 | KG | 37 | 3 | 30000.000 | 5 | 3873.6 |
| 730384/1430 | M | 13 | 3 | 261000.000 | 5 | 152343.4 |
| 734545/1430 | UN | 41 | 6 | 38400.000 | 1 | 2240.8 |
| 773474/1430 | KG | 27 | 12 | 73600.000 | 6 | 11636.2 |
| 773474/1450 | KG | 17 | 10 | 64000.000 | 33 | 20307.7 |

Exemple qui interdit de compter chaque H courant comme une nouvelle commande : pour **001757**, les versions des 27 juillet, 3 août et 10 août reprennent H = 2 000 kg, I = 1 200 kg, J courant = 3 855,020 kg et J futur = 1 975 kg. Les photos des 28 juillet, 4 août et 11 août restent toutes à **5 830,020 kg**. Références MRP : H29064/H30080/H31120 et J29066/J30082/J31122 ; inventaire : E1583/E1381/E612. Additionner H donnerait 6 000 kg sans preuve de trois nouveaux achats. Cela reste compatible avec des propositions/engagements reconduits, sans identification certaine d'une même commande.

Dans la simulation, les identifiants permettent en revanche un vrai décompte : la référence a lancé en 2025 **147 achats de 001757 pour 34 700 kg**, quatre de 001848 pour 22 000 kg, six de 002612 pour 135 000 kg et 30 de 338929 pour 2 151 600 UN. Ce sont les nouveaux achats externes par année de lancement, hors carnet initial et hors transferts ; pas les réceptions de l'année. Tous les couples et la variante FIA fixe figurent dans [simulation_2025.csv](../../artifacts/testing/mrp_full_flow_audit_20260930/simulation_2025.csv).

### Ce que l'évolution réelle des stocks apporte

La comparaison de **la somme J du seul plan courant** à la photo du lundi suivant donne **1 131 égalités sur 1 615 rapprochements**, soit environ 70 %. Comparer seulement J immédiatement disponible ne donne que 890 égalités : le stock déjà détenu mais disponible plus tard est indispensable. Les 484 écarts restants ne sont pas tous des erreurs de quantité : statuts exclus, réservations et différence d'horodatage restent des explications à départager.

- 001757, 001848/Avène, 002612/Avène, 007923/Avène et 338929 concordent **51 semaines sur 52** ; le 2 mars concentre 29 écarts parmi les couples, ce qui invite à traiter cette version commune avant d'inventer 29 règles différentes.
- 042342/Gien présente un écart de **−1 500 000 UN sur 42 semaines** entre J total et la photo. 002612/Gaillac présente **−19 kg sur 51 semaines** ; 693055/Gaillac **−10 kg sur 51 semaines**. Ce sont des différences de périmètre/statut possibles, pas des coefficients de consommation établis.
- Les deux PF au dépôt ne concordent jamais exactement entre J et le stock total : cette différence doit être conservée dans le rapprochement des stocks disponibles, réservés et physiques.
- La source actuelle contient bien **1 250 kg** pour 002612/Gaillac le 6 janvier (`Stocks!E946`). L'ancienne anomalie à 1 250 414 ne doit plus être utilisée comme valeur du fichier courant. J vaut 395 kg dans le plan du 5 janvier (`Feuille1!J158`) : cet autre écart reste visible.
- L'ancien inventaire au 1er janvier se raccorde au nouveau sur 31 couples : 28 concordances au seuil de 0,000001 unité ; écarts de +0,00328125 kg pour 002612/Avène, −0,000172 kg pour 038005/Gien et +1 UN pour 042342/Gien. 344135 n'a pas de photo récente au 1er janvier. Ces petites différences ne justifient pas les grands écarts ultérieurs.

Le [rapprochement hebdomadaire](../../artifacts/testing/mrp_full_flow_audit_20260930/stock_2025_bridge.csv) conserve **1 583 intervalles de sept jours**. Il compare le changement réel de stock à H−I de la semaine suivante annoncé par le plan précédent ; une semaine source absente reste vide. Ce rapprochement repose sur une hypothèse d'alignement temporel déclarée : son résidu ne permet pas d'identifier séparément les réceptions exécutées, les prélèvements, les ajustements et les transferts. J futur n'est jamais ajouté comme une nouvelle arrivée physique.

### Délais : une nouvelle hypothèse commune étayée

Il faut traiter séparément **délai fournisseur FIA**, **réception/disponibilité** et **sécurité**. La FIA ne précise pas le calendrier de son délai ; le simulateur le traite comme calendaire. Les jours de sécurité suivent la convention utilisateur lundi–vendredi. Le carnet donne des dates G de livraison et I de disponibilité, ainsi qu'un nombre H de jours de réception.

Sur **toutes les 104 lignes du carnet** :

| Calcul de disponibilité depuis G | Dates I reproduites |
|---|---:|
| Ajouter H jours calendaires | 3/104 |
| Ajouter H jours lundi–vendredi | 70/104 |
| Ajouter H jours lundi–vendredi en excluant les jours fériés métropolitains 2025 | **99/104** |

Le calendrier candidat reprend la [liste officielle des jours fériés 2025](https://calendrier.api.gouv.fr/jours-feries/metropole/2025.json), consultée le 30 septembre 2026. La [preuve de calcul](../../artifacts/testing/mrp_full_flow_audit_20260930/receipt_calendar.json) conserve toutes les dates candidates, les 104 prédictions et les écarts. Les cinq restants concernent **021081/Gaillac**, lignes 23, 25, 30, 39 et 42 : chaque intervalle contient **neuf jours ouvrés non fériés de plus** que les 75 jours indiqués. Fermeture estivale ou autre indisponibilité commune est une hypothèse ; les dates exactes de fermeture ne sont pas identifiées. Ce calcul rétrospectif n'active aucun nouveau calendrier et ne modifie pas la sécurité.

Le champ E du MRP est constant pour chaque couple, mais diffère du carnet sur huit couples : 001848/Gien 14→26 ; 002612/Avène 8→9 ; 049371/Avène 8→9 ; 333362/Gien 4→5 ; 338929/Avène 4→6 ; 693055/Gaillac 21→28 ; 734545/Gien 0→1 ; 773474/Gaillac 26→33. Ne pas additionner deux valeurs concurrentes d'un même temps de réception.

Exemple 002612/Avène : fournisseur retenu FIA **35 jours**, réception MRP **9 jours**, sécurité **20 jours ouvrés**. Dans la référence, les six nouveaux achats reçoivent des délais de livraison simulés de **24 à 70 jours** ; ce sont des tirages du moteur, pas des retards industriels mesurés. La variante FIA fixe applique 35 jours, puis la réception ; elle conserve la couverture prudente antérieure. Cela n'établit pas que l'industriel utilise cette couverture.

### BOM, tailles, prix et catalogues : correspondances et limites

Les **24 coefficients BOM** correspondent au graphe simulé et à `demand_PF.xlsx`. `Data_poc.xlsx` n'en couvre que 22 : il utilise encore 693710 à la place de 007923 pour 268091 et ne porte pas la recette 021081→773474. Ces deux écarts sont déjà résolus dans le graphe courant. Pour 1 000 PF 268091 : 1,624 kg de 001757, 1,218 kg de 001848, 2,03 kg de 002612, 3,248 kg de 007923 et 1 000 UN de 338929. Pour 1 kg de 773474 : 8,94 kg de 021081. La base 1 000 de la recette n'est pas un lot de production.

Les ratios empêchent d'attribuer automatiquement tous les besoins I aux seuls PF étudiés : dans le premier plan, 001757, 016332 et 049371 représentent chacun **15,813 millions de PF équivalents** par leur coefficient BOM, contre **178,712 millions pour 002612** et **46,728 millions pour 007923**. Les horizons renseignés diffèrent et ce sont des besoins planifiés, pas une production exécutée ; ces valeurs servent à détecter le périmètre, **pas à calculer un diviseur de stock définitif**. Même les emballages 338928/338929, tous deux à un pour un, ont des besoins différents. Les indications utilisateur sur les matières partagées restent une autre source d'information, distincte de ce diagnostic numérique. Les usages partagés et autres conditionnements doivent rester distincts du besoin explosé de nos seuls PF.

La FIA indique une **quantité standard**, sans colonne « multiple obligatoire », minimum d'achat ou maximum. Les quantités projetées fournissent des contre-exemples au multiple imposé partout. Les lots de fabrication sont des paramètres séparés : 268091 minimum 28 800 et maximum 142 485 UN dans la source récente ; avec le multiple de 14 400 retenu par le modèle, le maximum réalisé par campagne est 129 600. 773474 a un lot fixe de 3 200 kg et 693055 de 600 kg après conversion depuis G, unité retrouvée dans les autres sources.

Sur les premières versions des 24 couples avec FIA, **277 semaines ont H positif : 110 sont compatibles avec au moins un multiple de standard, 167 ne le sont pas**. Pour 338929, aucune des 23 entrées hebdomadaires initiales n'est un multiple de 5 000 UN ; pour 002612, neuf sur dix sont compatibles avec 22 500 kg, mais H189 indique 8 005,604 kg. Pour 001757, le plan initial est compatible avec des pas de 100 et de 1 000 kg ; les versions ultérieures montrent aussi 1 500 kg (`H4028`) et 500 kg (`H47027`). Cela réfute « chaque H est une commande complète au standard », pas nécessairement un standard contraignant sur chaque commande individuelle : réception partielle et agrégation doivent rester possibles.

Deux catalogues fournisseurs sont incomplets au regard du carnet : **049371/Avène** a onze lignes de 1 800 kg chez VD0518550B (58–68), alors que sa FIA donne VD0520132A, standard 1 600 kg et 147 jours ; **734545/Gien** a 6 400 UN chez VD0525906A (ligne 104), alors que sa FIA donne VD1095770A, standard 6 300 UN et 21 jours. Le carnet peut représenter des conditions antérieures ou d'autres fournisseurs ; leurs prix/délais non renseignés ne sont pas déduits du fournisseur FIA. D'autres lignes concernent la division 1820 hors périmètre MRP fourni ; une offre Avène n'est pas automatiquement une offre au même prix pour Gien.

Les 64 rapprochements tarifaires FIA–relations de l'extraction antérieure concordent après division par la base et conversion d'unité ; leurs sources sont inchangées. Pas de facteur 1 000 sur les prix 002612/338929. Pour 021081, les prix restent en **USD/kg**, sans conversion FX implicite ; un total monétaire multidevise ne doit pas être présenté comme un coût euro validé. Un prix source nul n'est pas une preuve de matière gratuite.

### Les règles de base sont-elles réellement appliquées ?

| Règle | Constat dans la configuration de référence actuelle | Statut |
|---|---|---|
| Sécurité achats lundi–vendredi, facteur 100 % | Conversion quotidienne et facteurs 1 ; `run_first_simulation.py:11055,13781`. | Conforme à la convention, pour les paramètres retenus ; traduction ERP en cible de stock non démontrée. |
| Sécurité pour déclencher la fabrication | `--production-mrp-safety-targets` absent ; contrôleurs `:11841,12754` gardent leur cible historique. Pour 773474 au jour 0, CSV trace : sécurité convertie 28 jours mais activation 0 et cible dédiée 0. | **Sécurité chargée ne signifie pas utilisée dans tous les contrôleurs.** |
| Livraison FIA et délai jusqu'à disponibilité | Champs séparés ; `:14827–14881`. Par exemple 338929 : FIA 42, référence disponibilité 50, livraison tirée 32, disponibilité réalisée 40 jours. | Distinction correcte ; le calendrier et l'aléa fournisseur sont des conventions. |
| Couverture prudente | Erlang 4 étages et marge 1,65 écart-type (`:4654`), ajoutés par le modèle. `fia_fixe` les conserve. | Hypothèse non extraite de l'ERP ; peut augmenter l'anticipation au-delà de FIA + sécurité. |
| Disponibilité des commandes initiales | G/I conservées séparément, stock détenu crédité une fois. | Cohérent ; les dates initiales de création restent inconnues. |
| Calendrier de réception | Nouveaux achats : lundi–vendredi sans fériés. | **La piste 99/104 montre une amélioration à tester**, séparément de la sécurité. |
| Standards et regroupement | Arrondi standard par défaut ; exceptions 338929/333362 ; `procurement_batching` non activé dans le graphe courant. | **Pas encore de règle commune de regroupement validée partout.** |
| Fournisseurs multiples | Politique principal/secours propre à 001848 ; ailleurs classement historique transport/délai et parts prédéfinies. | Règle prix/urgence générale non établie ; catalogues partiels pour deux autres matières. |
| Horizon | 364 jours glissants, dernière version connue à la décision ; pas d'injection de prévision future. | Implémenté ; queues absentes dans les sources et années ultérieures non calibrées. |
| BOM et quantités physiques | 24 coefficients et unités rapprochés ; UN physiques entières. | Cohérent sur le périmètre renseigné ; ne prouve pas tous les usages industriels. |
| Fabrication 693055 | Approvisionnement amont agrégé 600 kg, délai 28 jours issu de E, capacité inconnue. | Convention de frontière, **pas fabrication physique complètement reconstruite**. |

Trois paramètres récents sont bien appliqués au graphe daté : sécurité 426331 = 10 jours, sécurité 268967/DC = 60 jours, minimum 268091 = 28 800. **268091/DC reste à 20 jours alors que la source récente indique 00** : l'étude a interprété l'instruction antérieure « pas d'essai à zéro » comme maintien du nominal (`mrp_rules_integration_20260928/study.py:77–81`). Cette interprétation antérieure doit être distinguée d'une confirmation métier spécifique du 20 ; aucune nouvelle modification n'est faite dans cet audit. Le registre séparé `simulation/lot_policy/engine_adapter.py:59` conserve par ailleurs le minimum historique 14 400, alors que le contrôleur de campagne utilise 28 800 : rapprochement des registres nécessaire.

### Suite prioritaire, selon les preuves

1. Tester **le même calendrier de réception** sur tous les couples, avec les fériés candidats et sans inventer les neuf jours de fermeture résiduels. Conserver les dates G/I explicites du carnet et la sécurité nominale.
2. Réconcilier **stock physique total / stock MRP détenu / stock disponible** et la version commune du 2 mars, avant de modifier les règles de consommation pour compenser ces écarts.
3. Traiter les **paramètres chargés mais non utilisés par la fabrication**, le conflit 268091/DC et les deux registres de minimum de fabrication ; chaque essai reste séparé de la référence.
4. Croiser **fournisseur, standard, prix, engagements et reports** pour reconstruire une règle commune de proposition. Les 52 versions révisées ne doivent pas devenir 52 historiques d'exécution ; les deux fournisseurs absents de FIA restent signalés.
5. Reprendre les essais transférables avec trois jugements distincts : H/I/K planifiés, évolution des stocks physiques 2025 et service PF. Une amélioration de quelques stocks ne suffit pas à accepter une règle si elle détériore le service ou d'autres articles.

## Registre courant des règles communes — 30 septembre 2026

**Point d'entrée pour la suite.** Une règle commune signifie un même calcul utilisant les paramètres du couple article/site/fournisseur et l'état des ordres. Elle ne signifie pas une même quantité ou un même nombre de jours pour tous les articles. Aucune règle différente selon le mois ou selon le morceau de courbe à reproduire n'est admise sans donnée métier correspondante.

Les statuts ci-dessous ont un sens précis : **confirmé** par les données ou l'utilisateur ; **convention du moteur** vérifiée dans le code mais non démontrée comme règle ERP ; **candidat** soumis à comparaison ; **réfuté comme règle universelle** lorsqu'un contre-exemple l'empêche de s'appliquer partout. Les sections historiques suivantes restent conservées pour comprendre les essais et leurs limites.

| Identifiant | Règle commune, en termes métier | Statut et portée | Dans le moteur |
|---|---|---|---|
| MRP-01 | Recalculer à partir de la dernière prévision connue à la date de décision ; ne jamais additionner plusieurs versions comme des besoins exécutés. | Confirmé : 52 versions de plans, distinctes de leur horizon futur. | `ExternalComponentDemandCalendar`, sélection datée des prévisions. |
| MRP-02 | Compter le stock existant une seule fois et respecter sa date de disponibilité. Un stock en qualité n'est pas une future livraison fournisseur. | Confirmé par rapprochement J/photos et confirmation utilisateur. | Stock disponible, `FirmReceipt(state="held")`, registre de disponibilité initiale. |
| MRP-03 | Déduire les quantités déjà engagées avant de proposer un achat supplémentaire ; distinguer reliquat et quantité déjà reçue. | Le rapprochement H/J étaye les réceptions partielles. La conservation de tout engagement même tardif est une convention du moteur, pas une règle ERP entièrement identifiée. | `plan_dated_requirements`, engagements identifiés et allocations tardives exposées. |
| MRP-04 | Une proposition future non lancée peut être recalculée ; une commande engagée n'est pas annulée au seul motif que la prévision change. | Distinction étayée par les révisions. La frontière exacte entre proposition et engagement n'est pas fournie par H. | Propositions révocables jusqu'au lancement ; carnet engagé conservé. Le préfixe FIA du banc reste seulement supposé engagé. |
| MRP-05 | Protéger les besoins futurs datés, sans transformer cette protection en consommation supplémentaire. | Candidat : couvertures 7/7/6/3 semaines étudiées pour 001757/001848/002612/338929. L'opérateur est commun ; sa conversion depuis les durées industrielles reste à établir. | Primitive générique `plan_with_stock_protection` déjà présente. Son activation dans la simulation complète reste limitée et ne doit pas être confondue avec le banc de comparaison. |
| MRP-06 | Regrouper les besoins encore découverts, puis réutiliser le surplus d'arrondi pour les besoins suivants. | Convention explicite ; fenêtre ancrée au premier besoin non couvert. Une fréquence fixe de commande n'est pas déduite de la seule fréquence hebdomadaire de l'export. | `grouping_days`, `ProcurementGroup`, allocation du surplus une fois. |
| MRP-07 | Distinguer quantité standard de référence, minimum, multiple obligatoire, maximum par ordre et contrainte physique de conditionnement. | Les lots fixes de fabrication sont confirmés par la feuille dédiée. La FIA ne prouve pas à elle seule un multiple obligatoire pour chaque entrée hebdomadaire H. | `LotSizing` et arrondi d'exécution `mrp_purchase_order_quantity` ; vérifier les deux niveaux avant de modifier une proposition. |
| MRP-08 | Choisir le fournisseur et dimensionner le secours en tenant compte du manque avant disponibilité du principal. | Principal moins cher/secours plus rapide confirmé pour 001848 uniquement. Pour 002612, les standards 22 500 et 23 750 kg ne suffisent pas à identifier automatiquement le fournisseur choisi. | `plan_sourced_requirements` ; ne pas généraliser une identité fournisseur ou une règle tarifaire sans preuve. |
| MRP-09 | Garder l'horizon prévisionnel après la fin de la période de résultats affichée. | Horizon source jusqu'à 364 jours futurs. Une dernière ligne plus proche n'est pas une preuve de demande nulle ensuite. | `mrp_planning_horizon_days: 364` ; distinguer horizon de décision et durée d'exécution. |
| MRP-10 | Appliquer les jours de sécurité sur lundi–vendredi et conserver intégralement les jours source du dépôt. | Confirmé par l'utilisateur. Le calendrier des autres durées et des fermetures reste à documenter. | Conventions de sécurité conservées ; aucun essai de sécurité à zéro adopté. |
| MRP-11 | Ajuster systématiquement le dernier achat pour terminer à stock nul. | **Réfuté comme règle universelle.** Des soldes finaux positifs, voire négatifs, existent dans les sources. Une fermeture arithmétique du bilan ne prouve pas les bonnes quantités aux bonnes dates. | Aucun plafonnement terminal universel ajouté au nominal. |
| MRP-12 | Respecter les dates possibles de réception ; ne pas confondre réception physique, disponibilité qualité et semaine d'affichage. | Livraison/disponibilité distinctes confirmées. Une anticipation avant fermeture est une piste ; un jour férié ne démontre pas une fermeture industrielle de toute la semaine. | Dates distinctes ; calendrier de réception supplémentaire à qualifier séparément. |
| MRP-13 | Comparer le plan aux délais prévisionnels fournisseurs, puis étudier séparément les aléas de livraison. | Paramètres FIA connus ; distributions des retards industriels non identifiées par ces fichiers. Jours FIA conservés comme calendaires par convention. | `--supplier-delivery-mode source` pour les nouveaux achats externes datés ; mode aléatoire conservé pour les études qui le demandent. |

### Comment une règle passe de l'hypothèse au moteur

Chaque essai doit préciser les cellules sources, l'unité, les dates de décision et d'échéance, les données reprises comme engagements et les semaines absentes. Il compare au minimum les réceptions positives exactes **à la même date et pour la même quantité**, l'erreur de quantité, le solde projeté et la première divergence. Les semaines où les deux calculs donnent zéro ne doivent pas masquer des commandes mal reproduites.

Le banc à entrées identiques utilise les besoins I, le stock J daté et les engagements initiaux supposés. Les H/K ultérieurs ne servent qu'à évaluer le résultat. Il est distinct de la simulation physique, dont les besoins résultent aussi des productions, consommations des articles partagés, disponibilités et transports.

Une intégration doit conserver les sécurités source, les UN physiques entières, les engagements existants et les deux suivis de lots. Elle doit également vérifier que l'exécution ne réarrondit pas une quantité différemment du plan. La réussite du banc n'autorise pas à déclarer la simulation annuelle calibrée : cette dernière exige sa propre comparaison et qualification.

La passe courante et ses preuves sont conservées sous `etudecas/artifacts/testing/mrp_common_policy_20260930`. Le point de reprise précédent est reproductible avec `etudecas/config/mrp_reconstruction_20260930/reproduce.py`.

### Processus itératif : apprendre sur un article, transférer la règle sans retouche

Le protocole du 30 septembre 2026 ajoute une étape obligatoire avant toute nouvelle intégration : **classer plusieurs règles sur un seul article, puis conserver exactement leur formule pour les autres articles**. Une règle commune utilise les paramètres industriels de chaque article ; elle ne choisit pas un nombre de semaines ou un arrondi différent pour mieux suivre chaque courbe. Le [protocole figé](../../artifacts/testing/mrp_rule_transfer_20260930/protocol.json) contient les candidats, les critères et l'ordre de transfert avant l'exécution.

Le premier article est **338929 à Avène**, mono-fournisseur, sur les échéances janvier–juin du plan du 5 janvier. Le transfert porte d'abord sur **001757**, également mono-fournisseur, puis sur **001848 et 002612**, dont le multisourcing ajoute une difficulté distincte. Le plan du 6 juillet teste ensuite juillet–décembre pour les quatre articles. Les 52 versions servent uniquement à vérifier la stabilité : elles ne représentent pas 52 historiques de commandes indépendants. Ces sources ayant déjà été examinées, il s'agit d'une validation rétrospective à paramètres gelés, pas d'un test aveugle.

Sept candidats sont définis. `S` désigne les jours ouvrés de sécurité source, `R` les jours de réception source et `Q` la quantité standard du fournisseur. Le calendrier ouvré de `R` reste une hypothèse, contrairement à celui de `S`. Le fournisseur est l'unique offre ou, à titre de convention commune pour ce banc, l'offre au prix unitaire comparable le plus bas ; les quantités H ne servent jamais à choisir rétrospectivement le fournisseur.

| Candidat | Mécanisme | Quantité proposée |
|---|---|---|
| A | Couvrir les besoins futurs sur `S/5` semaines, arrondi supérieur | Multiple supérieur de `Q` |
| B | Couvrir sur `(S+R)/5` semaines, arrondi supérieur | Multiple supérieur de `Q` |
| C | Couvrir sur `(S+R)/5` semaines, arrondi au plus proche | Multiple supérieur de `Q` |
| D | Même couverture que C | Minimum `Q`, sans multiple imposé |
| E | Même couverture que C | Besoin net, standard seulement indicatif |
| F | Regrouper les besoins encore découverts dans la fenêtre C, à partir du premier manque | Multiple supérieur de `Q` |
| G | Même regroupement que F | Besoin net, standard seulement indicatif |

La formule arrondie de C/E retrouve certains nombres de semaines étudiés auparavant ; cette origine rétrospective est déclarée. F/G isolent le regroupement sans ajouter un plancher de sécurité : ce sont des comparateurs de mécanisme, pas une suppression des sécurités du nominal. Les quantités physiques UN restent entières, y compris lorsque le standard est indicatif. Aucun arrondi au millier n'est introduit spécialement pour 001757.

Les sept candidats utilisent **les mêmes semaines comparables** sur chaque plan. Les H supposés engagés avant le délai fournisseur sont imposés identiquement et exclus des scores ; leur influence sur le stock restant est explicitement reconnue. J est compté une seule fois à sa date. Après ce préfixe, H et K servent uniquement à évaluer les résultats. Les semaines absentes, les fenêtres tronquées et les propositions hors semaine renseignée restent distinguées ; le sous-ensemble sans trou futur n'efface pas l'effet d'éventuels trous antérieurs.

Le classement utilise seulement l'erreur de réceptions de 338929 au premier semestre, puis l'erreur de stock projeté pour départager les candidats. Les règles sont ensuite transférées dans cet ordre sans ajustement. Une réception n'est exacte que si **semaine et quantité** concordent ; les achats manqués, supplémentaires et de mauvaise quantité sont comptés séparément. K reste un stock **projeté**, distinct des photos d'inventaire physique. Un contre-exemple suffit à rejeter l'affirmation de règle commune exacte ; un candidat partiel conserve ses réussites et ses échecs. Moins de trois réceptions positives comparables ne suffisent pas à soutenir une généralisation.

Une nouvelle idée après échec devra être formulée dans une nouvelle version du protocole et rejouée sur tous les articles. Une exception n'est admissible que si elle correspond à une condition métier issue des sources, telle qu'un véritable minimum contractuel ou un état d'engagement, et non au code article ou à une période qui améliore le score. La simulation physique sur cinq ans intervient après ce filtrage, lorsqu'une modification du moteur est effectivement proposée ; le banc seul ne qualifie ni le service client ni les stocks physiques.

**Premier cycle exécuté : sept candidats sur 208 plans, soit 1 456 calculs de planification.** Les résultats sont dans le [tableau CSV](../../artifacts/testing/mrp_rule_transfer_20260930/scores.csv) et la [matrice détaillée avec contre-exemples](../../artifacts/testing/mrp_rule_transfer_20260930/results.json). Les 208 plans sont les quatre articles et leurs 52 versions ; ils ne constituent pas 208 observations industrielles indépendantes. Le programme appelle les fonctions existantes du moteur et ne simule pas d'exécution physique.

Le classement sur le seul apprentissage 338929 est **D/E ex æquo, puis C, B, A, G, F**. D et E donnent exactement les mêmes H/K sur ses semaines scorées : on ne peut donc pas déduire de cet article seul si le standard doit être un minimum. Leurs 11 réceptions positives exactes sur 13 ne suffisent pas non plus à expliquer tous les volumes : leur erreur absolue totale de réceptions représente encore 31,1 % du volume source de la fenêtre.

Réceptions positives retrouvées **à la même semaine et pour la même quantité**, avec les paramètres gelés et les mêmes semaines comparables pour tous les candidats :

| Article à Avène | D : standard minimum, H1 | D, H2 | E : standard indicatif, H1 | E, H2 |
|---|---:|---:|---:|---:|
| 338929, apprentissage H1 | 11/13 | 10/11 | 11/13 | 10/11 |
| 001757, transfert mono-fournisseur | 0/6 | 0/6 | 0/6 | 0/6 |
| 001848, transfert multi-fournisseur | 0/1 | 0/1 | 0/1 | 0/1 |
| 002612, transfert multi-fournisseur | 7/7 | 1/9 | 0/7 | 0/9 |

Le transfert départage donc des mécanismes indiscernables à l'apprentissage : D retrouve toutes les réceptions comparables et K de 002612 en H1, E ne les retrouve pas. Mais D échoue en H2 et sur 001757. Les sept candidats sont écartés **comme explications exactes communes dans les conditions du banc**, sans remplacement du nominal. Les correspondances partielles restent documentées ; aucun paramètre propre à un article n'est ajusté pour sauver le résultat.

Le résultat **7/7 de 002612 en H1** subsiste sur ses **19 semaines sans trou dans la fenêtre future ni dans l'historique**. À l'inverse, pour 338929 en H1, le sous-ensemble aussi strict retrouve huit réceptions sur neuf : même en retirant l'ambiguïté des semaines manquantes, il reste un contre-exemple à la règle proposée.

Trois contre-exemples localisent le prochain travail. Pour **001757**, le 6 avril, D/E proposent 780,328 kg et C arrondit à 800 kg, contre 1 000 kg en `Feuille1!H14` : le standard FIA de 100 kg ne suffit pas à expliquer le regroupement. Pour **001848**, les 3 331,16 kg du 18 mai (`H101`) et les 4 000 kg du 2 novembre (`H26194`) ne sont pas reproduits par un minimum global de 6 000 kg. La seconde quantité est compatible avec le fournisseur de secours connu, mais la compatibilité de quantité ne remplace pas une identité d'ordre. Pour **338929**, D/E calculent 144 616 UN le 13 avril, contre 289 232 en `H719`, puis placent 144 616 la semaine suivante : une règle de date ou de regroupement reste à expliquer. Ajouter un facteur constant à toutes les quantités ne corrigerait pas ces mécanismes différents.

Les limites du jeu de données comptent dans le verdict. En H2 de 002612, le premier écart K du 17 août inclut déjà une proposition de 22 500 kg dans une semaine antérieure absente : ce n'est pas, à lui seul, une réception source explicitement contradictoire. Pour 001757, aucune semaine H2 ne garde une fenêtre future entièrement renseignée ; pour 001757 et 001848, les périodes principales ont toutes des trous antérieurs. Les scores principaux reposent donc sur l'hypothèse déclarée de zéros internes. Les sous-scores stricts sont fournis et ne sont pas remplacés par des zéros quand ils sont vides. Ces limites empêchent de confondre rejet d'une reconstruction exacte et preuve exhaustive du fonctionnement de l'ERP.

La prochaine itération devra séparer **protection des besoins**, **politique réelle de lot de commande** et **sélection fournisseur selon l'état du besoin et des engagements**. Elle devra garder les cas qui concordent et expliquer les contre-exemples ci-dessus avec des conditions métier vérifiables. Il n'est pas justifié à ce stade d'imposer partout un minimum, un multiple du standard, un multiplicateur dix, ni une période de fermeture supposée. Les anciens candidats « stock final systématiquement nul » et « toute semaine fériée fermée » restent rejetés comme règles universelles.

Reproduction : `python -B etudecas/artifacts/testing/mrp_rule_transfer_20260930/study.py --protocol CHEMIN_PROTOCOLE --output DOSSIER_NEUF_SOUS_ARTIFACTS_TESTING`. Le [script unique](../../artifacts/testing/mrp_rule_transfer_20260930/study.py) refuse d'écraser ses résultats ; les candidats restent explicites et les formules nouvelles exigent une implémentation relue. Le protocole et les entrées sont empreintés. Ce cycle n'ajoute aucun fichier au moteur et ne régénère aucune carte.

**Vérification de ce cycle.** Les huit tests ciblés en mémoire des fonctions de couverture et regroupement passent, ainsi que le [contrôle de leurs preuves natives](../../artifacts/testing/mrp_rule_transfer_20260930/native/gate-2d9b74cff7ee4e4992500517b1149570/manifest.json). Un agent distinct a relu directement les quatre classeurs utiles et recalculé les paramètres, les semaines comparables, les scores, les ex æquo et les verdicts. Son [oracle indépendant](../../artifacts/testing/mrp_rule_transfer_20260930/validation/transfer_check.json) n'importe ni les fonctions du moteur ni celles du banc : il reproduit les sept trajectoires sur chacun des 208 plans par une récurrence arithmétique distincte. Les 333 381 rapprochements ne comportent aucun échec ; ils vérifient le calcul livré, pas l'identification de l'ERP. Le [manifeste de ce cycle](../../artifacts/testing/mrp_rule_transfer_20260930/manifest.json) regroupe les empreintes, les preuves et la décision de ne pas intégrer ces candidats comme règle commune exacte.

### Comparaison avec les fonctions réellement utilisées par le simulateur

La [carte des règles communes](../../resultats/regroupement_001757_20260929/carte_regles_communes.html) ajoute un panneau indépendant à la carte de regroupement de référence. Il propose quatre articles, leurs 52 versions et trois calculs : besoins datés seuls, couverture datée, hypothèse calendaire. Les autres onglets et les deux suivis de lots restent ceux de la référence historique. Le candidat calendrier utilise un calcul analytique séparé ; les deux autres variantes appellent les fonctions existantes du moteur.

Le script `compare_engine.py` appelle directement `plan_dated_requirements` et `plan_with_stock_protection`. Sur les 208 plans, ce second helper retrouve les propositions du replay analytique précédent, à la tolérance numérique près. Ce raccord est nouveau ; les scores de la couverture ne constituent pas une nouvelle amélioration par rapport au replay précédent.

| Article | Réceptions positives exactes H1 : daté simple → couverture | Réceptions positives exactes H2 : daté simple → couverture |
|---|---:|---:|
| 001757 | 0/6 → 4/6 | 1/6 → 3/6 |
| 001848 | 0/1 → 0/1 | 0/1 → 0/1 |
| 002612, standard 22 500 kg | 1/7 → 7/7 | 2/9 → 1/9 |
| 338929 | 0/13 → 11/13 | 4/11 → 10/11 |

H1 = échéances janvier–juin du plan du 5 janvier ; H2 = juillet–décembre du plan du 6 juillet. Les préfixes imposés, dates sources absentes et fenêtres de couverture incomplètes sont exclus. Le calcul « daté simple » du banc n'inclut pas la réserve technique du runtime complet, son multisourcing ou l'exécution physique : il ne faut pas attribuer ces scores à la simulation nominale entière.

**Règle de protection testée :** à une date donnée, protéger la somme des besoins bruts des N semaines suivantes. Les quantités J déjà présentes sont fournies une seule fois au planificateur, comme stock disponible ou stock à libérer plus tard. Elles ne sont pas déduites une seconde fois de cette cible. L'enveloppe cumulée des besoins et de la protection déclenche les achats sans compter la protection comme une consommation.

Les paramètres 7/7/6/3 semaines et 1 000/6 000/22 500/1 comme arrondis sont des candidats documentés. La couverture datée améliore plusieurs cas par rapport au helper simple mais ne résout pas le choix fournisseur de 002612 ni le traitement des dernières propositions de 001848. Son intégration générale au runtime nécessite encore de composer proprement protection, sourcing et regroupement : leurs gardes actuelles interdisent certaines combinaisons.

### Paramètres d'achat : prix, délais, standards et choix fournisseur

**Complément du 30 septembre 2026.** Le prix doit être ramené à sa base et à son unité avant toute comparaison : montant / base de prix, puis conversion d'unité si nécessaire. La devise reste explicite. Une quantité standard d'achat n'est ni une quantité minimale démontrée, ni une palette, ni un maximum de fabrication. La FIA identifie l'article et le fournisseur ; elle ne fournit pas à elle seule le site destinataire.

L'inventaire couvre **12 classeurs, 35 feuilles et 35 lignes FIA**, dont 33 offres externes et deux approvisionnements internes, rattachés à 24 couples article/site. Les six couples multisourcing sont 001848, 001893, 002612, 007923 et 055703 à Avène, et 021081 à Gaillac. Les 64 rapprochements de prix FIA/relations concordent après normalisation de la base et de l'unité. Les quatre offres de 021081 sont cependant en **USD/kg** : 12,10 / 12,10 / 12,15 / 15,00, toutes à 120 jours et 20 000 kg de standard. Elles restent séparées des offres EUR ; aucun taux de change industriel n'est ajouté.

Dans les 72 lignes de relations recensées, les champs fréquence, priorité, limite de délai et coût de transport sont vides. Les parts fournisseurs, fréquences de regroupement et coûts transport utilisés par la simulation ne peuvent donc pas être présentés comme provenant de ces cellules. Les différences numériques entre anciennes et nouvelles politiques portent sur trois sécurités — 426331/Avène : 7→10 jours ; 268091/dépôt1920 : 20→0 ; 268967/dépôt1920 : 25→60 — et sur le minimum de fabrication de 268091 : 14 400→28 800 UN. Ce sont des divergences entre fichiers, sans date d'effet explicite ; l'audit ne remplace pas les paramètres du nominal. Les sept différences purement typographiques, comme `07` et `7`, ne sont pas classées comme conflits.

Les huit offres ci-dessous sont lues directement dans `268091.xlsx/FIA`. Le rapprochement avec les relations du graphe et le carnet concerne ici Avène ; les autres sites ne sont pas fusionnés.

| Article | Fournisseur | Prix d'achat normalisé | Délai livraison prévisionnel source, jours | Quantité standard source | Ligne FIA |
|---|---|---:|---:|---:|---:|
| 001757 | VD0951020A | 5,43 EUR/kg | 84 | 100 kg | 2 |
| 001848 | VD0519670A | 4,20 EUR/kg | 21 | 4 000 kg | 3 |
| 001848 | VD0951020A | 1,58 EUR/kg | 56 | 6 000 kg | 4 |
| 002612 | VD0500655A | 1,34 EUR/kg | 28 | 21 600 kg | 8 |
| 002612 | VD0910216A | 0,82 EUR/kg | 35 | 22 500 kg | 9 |
| 002612 | VD0990780A | 1,295 EUR/kg | 35 | 23 750 kg | 10 |
| 002612 | VD1091642A | 1,225 EUR/kg | 35 | 22 500 kg | 11 |
| 338929, étui | VD0914360C | 0,21585 EUR/UN | 42 | 5 000 UN | 20 |

Cellules : A = article, B = fournisseur, C = montant, D = base de prix, E = devise, F = délai, G = quantité standard, H = unité. Ainsi `C9/D9 = 820/1 000 = 0,82 EUR/kg` pour 002612 ; `C20/D20 = 215,85/1 000 = 0,21585 EUR/UN` pour l'étui. Aucun facteur 1 000 erroné n'est constaté sur ces prix dans le graphe de référence examiné. Le calendrier du délai fournisseur n'est pas précisé dans la FIA ; son interprétation en jours calendaires dans le moteur reste une convention distincte des jours de sécurité confirmés.

**001757 : distinguer la source de l'hypothèse de regroupement.** La FIA donne 100 kg. Les 1 000 kg utilisés dans le banc de reconstruction sont un arrondi candidat issu des flux MRP, pas une correction de cette cellule source. Retrouver des entrées hebdomadaires de 1 000 kg ne prouve pas que chaque commande individuelle impose ce minimum.

**002612 : quatre offres, pas seulement deux.** Deux fournisseurs ont le même standard de 22 500 kg. Les deux commandes initiales d'Avène sont explicitement affectées à VD0910216A, le moins cher (`Extract_En_cours.xlsx/Sheet1!D14:D15`). En revanche, les H futurs ne portent pas le fournisseur. Dans les 52 versions, 365 cellules H valent exactement 22 500 kg et 113 valent 23 750 kg ; ces dernières apparaissent dans 49 versions, dès le plan du 19 janvier pour le 23 février (`Feuille1!H2136`). **Ce sont des occurrences dans des projections alternatives, pas 478 commandes exécutées.** Elles contredisent le standard unique de 22 500 kg imposé partout, mais ne prouvent pas à elles seules un changement de fournisseur.

**Délai fournisseur, livraison et disponibilité restent trois informations distinctes.** Sur les sept commandes initiales d'Avène concernant ces quatre articles, les sept quantités correspondent à H dans la semaine de livraison G ; une seule correspond dans la semaine de disponibilité I. Les treize commandes sélectionnées, autres sites compris, ont un intervalle G→I compatible avec le nombre de jours lundi–vendredi indiqué dans leur carnet. Cela ne démontre pas le calendrier de tous les autres ordres : voir la section 18 pour l'analyse incluant les jours fériés.

Des paramètres diffèrent déjà entre sources : réception de 002612/Avène = 8 jours dans `Extract_En_cours!H14:H15`, contre 9 dans Flow MRP ; 338929/Avène = 4 jours en `H101`, contre 6 ; 001848/Gien = 14 jours en `H7`, contre 26. La date de validité d'un changement de paramètre n'est pas fournie. Il faut conserver les dates explicites des engagements initiaux et documenter le paramètre utilisé pour les nouvelles propositions, sans réécrire rétroactivement le carnet.

### Ce que la référence simulée applique effectivement

L'examen porte sur le témoin historique `mrp_policy_20260929/study/reference_figee`, pas sur une nouvelle simulation. Le CSV `data/mrp_orders_daily.csv` est filtré sur les nouveaux achats fournisseurs destinés à Avène, lancés aux jours 0 à 364 ; les ordres d'ouverture sont exclus. Chaque ligne retenue possède un identifiant MRP distinct. Une commande lancée en 2025 peut être livrée en 2026. Ces nombres d'ordres ne se comparent pas directement au nombre de cellules H, qui agrègent les réceptions prévues par semaine.

| Article | Nouveaux ordres lancés | Quantité commandée | Fournisseurs effectivement utilisés |
|---|---:|---:|---|
| 001757 | 147 | 34 700 kg | VD0951020A |
| 001848 | 4 | 22 000 kg | VD0951020A : 3 × 6 000 kg ; VD0519670A : 1 × 4 000 kg |
| 002612 | 6 | 135 000 kg | VD0910216A : 6 × 22 500 kg |
| 338929 | 30 | 2 151 600 UN | VD0914360C |

Pour 002612, le paramétrage multisourcing historique est `legacy`, avec des parts 70/20/5/5 triées selon le coût de transport puis le délai et l'identifiant. Ce n'est pas une politique industrielle démontrée. **Les parts configurées ne sont pas les parts réalisées** : dans ce témoin, arrondis et traitement successif des besoins conduisent aux six achats ci-dessus chez le seul fournisseur à 0,82 EUR/kg. Le choix principal/secours confirmé de 001848 s'applique séparément ; son CSV conserve pourtant `mrp_share=0.3` au principal et `0.7` au secours, champs hérités qui ne représentent pas leurs parts effectivement commandées.

Les délais sont également différents selon ce que l'on mesure. Le témoin utilise des délais aléatoires Erlang : pour les six commandes de 002612, le délai fournisseur source de 35 jours donne des délais tirés de **24, 27, 31, 43, 60 et 70 jours**. Pour 001757, la référence est 84 jours, mais les tirages des 147 ordres vont de 6 à 168 jours. Ces tirages sont des conventions du simulateur, pas des délais industriels mesurés dans les Excel. La recherche de la règle MRP doit comparer d'abord des plans aux mêmes besoins et délais prévisionnels ; les aléas d'exécution se vérifient séparément.

Le standard de 5 000 UN de 338929 est conservé comme donnée source mais explicitement non contraignant dans ce témoin. Cela explique que les achats simulés ne soient pas tous des multiples de 5 000. La source fournit un contre-exemple concret au multiple obligatoire : `Extract_En_cours.xlsx/Sheet1!E101` porte **57 600 UN**, chez le fournisseur identifié VD0914360C (`D101`), alors que 57 600 n'est pas divisible par 5 000. Cette convention est distincte des quantités physiques UN, qui doivent rester entières.

**Points techniques identifiés, sans correction silencieuse pendant l'audit.** L'import FIA (`knowledge_graph/update_supply_graph_from_case_data.py`, `update_edge_from_fia`) met à jour le nom de feuille mais conserve parfois un ancien numéro de ligne : le graphe témoin cite la ligne 8 pour 001757 alors que la FIA le contient en ligne 2. La préparation (`simulation_prep/prepare_simulation_graph.py`) peut aussi réécrire les prix depuis les relations `Data_poc`/`demand_PF`, sans arbitrage explicite de validité ; les quatre prix examinés restent cependant corrects. Enfin, les achats génériques ne contrôlent pas la devise comme le fait la politique spécifique de 001848. Un prix USD ne doit donc pas être comparé ou additionné à un prix EUR sans conversion documentée. Ces constats nécessitent un traitement séparé de la provenance et des conventions économiques ; ils ne prouvent pas une erreur de prix sur les quatre références ci-dessus.

**Suite de l'identification :** confronter pour chaque fournisseur le prix d'achat normalisé, le délai jusqu'à livraison, le temps jusqu'à disponibilité, les engagements existants et le caractère réellement contraignant du standard. Traiter les signatures de quantités comme des indices, pas comme des identifiants fournisseur. Pour 002612, expliquer les 23 750 kg projetés et leurs révisions sans inventer un basculement saisonnier ; pour 001757, expliquer le regroupement des besoins au-delà du standard de 100 kg. Aucun paramètre source ni règle du nominal n'est modifié par cet audit.

Preuves de cette passe : [inventaire des offres](../../artifacts/testing/mrp_purchase_parameters_20260930/extraction/purchase_offers.csv), [contre-vérification des quatre articles](../../artifacts/testing/mrp_purchase_parameters_20260930/validation/purchase_source_check.json), [rapprochement des dates du carnet](../../artifacts/testing/mrp_purchase_parameters_20260930/validation/initial_receipts_check.json), [achats effectivement simulés](../../artifacts/testing/mrp_purchase_parameters_20260930/runtime_purchase_check.json). Le manifeste de livraison regroupe les empreintes et les limites de ces contrôles ; il ne certifie pas l'identification complète du système industriel.

### Intégration du délai fournisseur source : comparaison contrôlée

Le mode `--supplier-delivery-mode source` applique à chaque nouvel achat externe agrégé du MRP daté le délai FIA explicite de sa liaison. Il refuse un délai absent, par défaut ou non entier, plutôt que de l'appeler « donnée source ». Il n'effectue pas de tirage aléatoire pour cette livraison. Les contraintes et incidents explicitement activés restent applicables ; le scénario de comparaison est BASE.

Ce mode conserve les dates G/I des engagements initiaux, les jours de sécurité, la couverture prudente existante, les transferts internes et la frontière de production 693055. Le délai de réception E s'applique toujours après la livraison. Son calendrier lundi–vendredi sans jours fériés reste une convention candidate, distincte des jours de sécurité confirmés. Ainsi, une commande au 1er janvier avec 35 jours FIA est livrée au 5 février ; avec neuf jours lundi–vendredi de réception, elle devient disponible au 18 février.

Le défaut `sampled` permet de reproduire les anciens calculs. L'option globale existante `--no-stochastic-lead-times` fixe aussi les autres délais et change les couvertures prudentes. Pour une liaison Erlang à quatre étapes de moyenne 35 jours, la couverture prudente existante est de 64 jours ; le mode fournisseur `source` ne la supprime pas. Cette différence justifie les trois variantes séparées de la recette `etudecas/artifacts/testing/mrp_delivery_rules_20260930/study.py` : témoin, livraison fournisseur seule fixe, puis délais fixes globaux.

Les constats d'audit suivants ont également été corrigés : les imports FIA conservent désormais leur véritable ligne Excel, et les exports de sourcing explicite affichent une part historique non applicable comme vide avec son motif, au lieu de faire croire à un quota 30/70 exécuté. Les paramètres de prix, standards et décisions physiques ne changent pas du fait de ces corrections de provenance et d'affichage. Les hypothèses de couverture, de regroupement, de calendrier industriel et de sélection fournisseur non démontrées restent séparées ; elles ne deviennent pas des règles générales par cette intégration.

La référence des délais avant correction est vérifiée dans [les six commandes 002612](../../artifacts/testing/mrp_delivery_rules_20260930/validation/deliveries_002612.json) : livraisons après 24 à 70 jours, moyenne 42,5, pour 35 jours FIA ; disponibilité après 35 à 83 jours, moyenne 55,17. Ces dates viennent de la simulation historique, pas de livraisons industrielles observées.

Les trois nouveaux calculs de **1 825 jours** sont terminés. Dans la variante fournisseur fixe, les six nouvelles commandes 002612 lancées en 2025 sont livrées après **35 jours** et disponibles après **48 jours**, une fois les neuf jours de réception lundi–vendredi écoulés. Ce résultat vérifie la convention programmée ; il ne mesure pas la ponctualité réelle du fournisseur. La source ne confirme pas encore le calendrier des jours FIA.

La [nouvelle carte des délais fournisseurs](../../resultats/regroupement_001757_20260929/carte_delais_fournisseurs.html), bouton **Comparaisons 2025**, conserve le témoin et ajoute les deux variantes. Elle ouvre 002612/Avène avec le témoin et la livraison au délai annoncé. Les autres onglets, le panneau « Règles communes MRP » et les deux suivis de lots gardent leurs résultats historiques. Leur contenu extérieur au panneau de comparaison est préservé ; ces vues ne sont pas présentées comme les résultats des trois nouveaux calculs.

Erreur absolue moyenne entre les **52 photos de stock 2025** et le stock physique simulé à la clôture de la veille, sans mélanger kg et unités :

| Article à Avène | Unité | Témoin, délais aléatoires | Livraison au délai fournisseur | Délais fixes globaux, couverture également modifiée |
|---|---|---:|---:|---:|
| 001757 | kg | 2 637 | 2 597 | 2 545 |
| 001848 | kg | 2 326 | 1 999 | 2 256 |
| 002612 | kg | 70 412 | 68 694 | 68 512 |
| 338929 | UN | 1 005 257 | 909 712 | 590 682 |

La seule fixation des livraisons améliore ces quatre erreurs de respectivement **1,5 %, 14,1 %, 2,4 % et 9,5 %**. Cela ne suffit pas à retrouver les stocks industriels : pour 002612, la moyenne simulée reste proche de 41 009 kg contre 105 740 kg dans les photos ; pour 338929, elle reste à 1 359 243 UN contre 521 515 UN. Pour 001848, l'erreur absolue baisse, mais le biais moyen devient plus négatif. L'effet d'une correction se juge donc sur la trajectoire, les volumes et le niveau moyen, pas sur un indicateur seul. La variante globale améliore davantage 338929 tout en étant moins bonne que la variante fournisseur seule sur 001848 ; elle n'est pas adoptée comme règle industrielle universelle.

Sur l'ensemble des **29 couples comparables** du panneau, la variante fournisseur seule réduit l'erreur dans **16 cas**, l'augmente dans **huit** et la conserve dans **cinq** ; quatre autres couples n'ont pas de métrique comparable. Ce comptage vient des métriques exportées, dont le contre-calcul direct Excel/CSV de cette étape porte sur les quatre articles du tableau. La variante globale réduit 17 erreurs, en augmente onze et en conserve une. Les couples n'ont pas tous le même nombre de photos ni le même périmètre représenté ; ce bilan n'est pas un score industriel global.

Les temps de calcul mesurés sont **857,4 s**, **857,9 s** et **930,8 s**, respectivement. Des exécutions indépendantes ont tourné en parallèle : ces durées ne sont pas un benchmark de performance. Les années sans nouvelles versions industrielles des prévisions prolongent les conventions du modèle ; la comparaison aux sources porte uniquement sur 2025.

Le contrôle du service client interdit également de conclure à une amélioration générale : pour 268091 en 2025, le volume servi passe de **3 528 253 UN** dans le témoin à **3 499 453 UN** avec la livraison fournisseur fixe, soit **28 800 UN de moins** ; les jours avec au moins une unité de reliquat passent de sept à neuf. La variante globale sert 3 125 053 UN et compte 35 jours avec reliquat. La demande physique est identique. Les délais annoncés sont utiles pour isoler les hypothèses du MRP, mais la variante n'est pas adoptée comme nouveau nominal sur la seule amélioration des écarts de stock.

Le déficit de 28 800 UN apparaît dans le service des **26–28 décembre**. Le 30 novembre (J333), le témoin fabrique un lot supplémentaire de 28 800 UN, tandis que la variante fournisseur fixe ne le fabrique pas : le registre signale une contrainte sur **693055**, avec une capacité de fabrication non limitante. Le témoin reçoit ce jour-là 50 kg de 693055, puis consomme 11,6928 kg pour ce lot ; la variante n'a pas cette réception au même jour. Ce rapprochement établit la chaîne locale matière–fabrication–service. Il ne permet pas d'attribuer directement ce manque aux 35 jours de 002612 : les trajectoires et les autres aléas peuvent diverger après modification des décisions. Le [diagnostic daté](../../artifacts/testing/mrp_delivery_rules_20260930/validation/service_268091_timing.json) conserve les lignes CSV et les huit contrôles correspondants.

Les **26 cas de tests ciblés** et les **trois qualifications CSV** passent. L'[oracle indépendant](../../artifacts/testing/mrp_delivery_rules_20260930/validation/runs_check.json) réalise **770 459 contrôles** : dates de livraison/disponibilité, identité des lots, carnet initial conservé, demande PF identique sur cinq ans, quantités UN entières et conservation des couvertures entre témoin et variante fournisseur seule. Il recalcule directement depuis les Excel et CSV les douze erreurs de stock du tableau, puis les rapproche du contenu de la carte. Ces contrôles valident les conventions programmées, pas l'identification complète du MRP industriel.

Le [parcours navigateur natif](../../artifacts/testing/mrp_delivery_rules_20260930/browser/native/browser-f4bbbd1d9df64c21b9d96336de1d5377/manifest.json) et le [regroupement des preuves natives](../../artifacts/testing/mrp_delivery_rules_20260930/validation/native/gate-82be5a235d8d4798853c7c766642d5f4/manifest.json) passent. La revue supplémentaire reste **partielle** : le parcours étendu rencontre des délais d'attente sur certains clics. Le parcours court avec clics souris visibles valide les courbes stocks/flux des deux articles et l'export de 002612, mais son sélecteur de scénarios devient ambigu pour 001848, car l'attribut `data-run` existe aussi sur des lignes de commandes. Cela limite la preuve du script ; ce n'est pas une erreur démontrée des valeurs affichées. La [preuve détaillée](../../artifacts/testing/mrp_delivery_rules_20260930/browser/review-4bb9a32d42a74c2aaf4aec2033c7b535/manifest.json) conserve cette limite, sans transformer un contrôle échoué en réussite.

La [capture 002612 examinée](../../artifacts/testing/mrp_delivery_rules_20260930/browser/review-4bb9a32d42a74c2aaf4aec2033c7b535/002612_stock_reference_delais_fixes.png) montre les courbes et légendes lisibles, les points sources distincts et les périmètres explicites. La carte reconstruit néanmoins de grandes tables, même repliées, à chaque changement de vue : c'est une limite de performance à traiter séparément. Le [manifeste de livraison](../../artifacts/testing/mrp_delivery_rules_20260930/manifest.json) distingue qualification du moteur, contrôle des résultats et couverture partielle de l'interface.

Les commandes exactes, le graphe commun et leurs empreintes sont dans le [plan de reproduction](../../artifacts/testing/mrp_delivery_rules_20260930/study/plan.json). La [recette](../../artifacts/testing/mrp_delivery_rules_20260930/study.py) applique `prepare`, puis `run --variant reference`, `run --variant fia_fixe`, `run --variant fixe_global` et `render`. Elle refuse les destinations existantes : pour une nouvelle reproduction, adapter son dossier d'étude et son nom de carte. Elle dépend des références antérieures indiquées dans le plan ; aucun résultat antérieur n'a été écrasé. Les [métriques détaillées](../../artifacts/testing/mrp_delivery_rules_20260930/comparison_metrics.json) gardent le périmètre et l'unité de chaque couple article/site.

### Deux hypothèses générales testées et non adoptées

**Plafond de fin de plan.** Ramener la dernière proposition au besoin net restant retrouve les 3 331,16 kg de 001848 au 18 mai dans le plan du 5 janvier. Sur les 52 versions, cependant, il retrouve le solde final nul mais seulement trois dernières réceptions à la bonne semaine et pour la bonne quantité. Pour 001757, il dégrade les 52 soldes finaux auparavant exacts. Le plafond n'est donc pas intégré comme règle universelle. De plus, 206 des 208 plans s'arrêtent avant la borne des 52 semaines : le dernier point exporté ne peut pas être traité sans hypothèse comme la fin des besoins connus.

**Fermeture d'une semaine contenant un jour férié.** Les jours fériés 2025/2026 sont vérifiés dans le [calendrier public métropolitain](https://calendrier.api.gouv.fr/jours-feries/metropole.json), consulté le 30 septembre 2026. La fermeture de toute la semaine reste une hypothèse, distincte de ces dates officielles. Le test anticipe les besoins sur la semaine ouverte précédente et n'altère pas les engagements du préfixe.

Pour 001757, ce candidat explique les 3 000 kg du 13 avril (`Feuille1!H15`) : avant les semaines de Pâques, du 1er mai et du 8 mai, la couverture passe de sept à dix semaines. L'erreur moyenne H1 baisse de 500 à 71,43 kg ; mais celle de H2 augmente de 500 à 666,67 kg. Le même calendrier dégrade 002612. Les sources contiennent aussi des réceptions positives pendant les semaines supposées fermées : la fermeture hebdomadaire n'est pas une règle commune identifiée.

**Contre-exemple à surveiller dans les courbes :** pour 338929/H2, le candidat calendrier retrouve le solde K sur les lignes comparées, mais place 144 631 UN au 2 novembre, une semaine absente de la source, au lieu du 9 novembre (`H26757`). Un stock projeté exact ne suffit donc pas à valider les dates de réception.

Les quantités et calendriers du nominal restent inchangés à l'issue de ces contre-épreuves. Les vérifications indépendantes figurent dans `validation/analysis_check.json`, `validation/engine_comparison_check.json` et `validation/calendar_check.json` de cette passe ; elles certifient les calculs annoncés, pas l'identification complète de l'ERP.

Analyse du 28 septembre 2026. **Objectif : reproduire le comportement de la supply chain réelle**, en retrouvant les stocks hebdomadaires, les plans et les décisions compatibles avec les données. Les sections 1–14 décrivent l'audit initial ; la section 15 corrige la comparaison ; la section 16 conserve les essais antérieurs non retenus ; les sections 17–18 rapprochent les prévisions et le carnet initial. **La section 19 décrit la séparation livraison/disponibilité et le calcul des achats par échéance.** La variante à zéro jour est abandonnée comme piste de calibration.

Les deux classeurs apportent des paramètres explicites et des résultats de planification. Ils ne contiennent pas le code du MRP industriel. Le rapport distingue donc les règles écrites, les comportements vérifiés dans les chiffres et les règles qui restent à identifier. Il complète les nomenclatures, délais, capacités, commandes ouvertes et confirmations métier déjà disponibles dans les autres sources.

## Ce que contiennent les fichiers

| Fichier / feuille | Contenu vérifié | Usage correct |
|---|---|---|
| Flow_Data_Inventory_and_Replenishment_rules / Stocks | 1 646 photos, 26 articles, 32 couples article/site, 53 dates | Stocks réels de référence : 1er janvier 2025, puis les 52 lundis |
| Même classeur / Politique de stock MRP | 27 politiques | Délais de sécurité en jours ouvrés et quantités de sécurité, champs séparés |
| Même classeur / Taile de Lot | 4 politiques | Paramètres des lots de fabrication aux sites indiqués |
| Même classeur / Graph | Tableau croisé des stocks de 773474 à Gien et Gaillac | Représentation des mêmes stocks ; aucune règle supplémentaire |
| Flow_Data_MRP_results / Feuille1 | 53 398 lignes, 33 couples article/site, 52 versions de plan | Projections datées ; ce ne sont pas des mouvements tous exécutés |

**Horizon de 52 semaines confirmé.** Les versions vont du 5 janvier au 28 décembre 2025. Chaque version peut projeter jusqu'à 364 jours après sa date. En comptant la semaine courante, cela peut produire **53 dates**. Une projection de décembre 2025 peut donc aller jusqu'en décembre 2026. Les 52 versions ne doivent jamais être additionnées comme des flux annuels.

Toutes les dates de version et de semaine du MRP sont des dimanches. La photo de stock correspondante est généralement celle du lundi suivant. Le jour exact représenté par le libellé de semaine, à l'intérieur du processus ERP, n'est pas documenté.

Les 1 637 plans article/site/date présents ne contiennent pas tous 53 lignes : 1 480 présentent des semaines absentes entre deux lignes. Cela peut résulter d'un export qui omet certaines semaines. **Une absence ne prouve ni un flux nul ni une fin de l'horizon de planification.** La fréquence hebdomadaire de l'export ne prouve pas que le MRP lui-même ne tourne qu'une fois par semaine.

Le fichier Stocks conserve un filtre Excel sur 002612 : 1 540 lignes sont masquées et 106 visibles. L'analyse a lu toutes les lignes. Il ne faut pas limiter l'analyse aux lignes visibles à l'ouverture du classeur.

## 1. Toutes les sécurités et tous les temps de réception

Dans la feuille de politique : E = délai de sécurité, F = quantité de sécurité, G = unité de cette quantité. Dans Feuille1 du MRP : E = « Temps de réception en jours ». Les temps de réception sont constants pour chaque couple article/site dans cet export.

**Les deux colonnes de durée ne représentent pas automatiquement le même mécanisme.** Le calendrier lundi–vendredi des jours de sécurité a été confirmé par l'utilisateur. Le calendrier et les opérations incluses dans le temps de réception restent à préciser : achat, fabrication, transport, réception, contrôle qualité, etc.

| Article | Site | Sécurité : jours ouvrés | Sécurité : quantité, unité source | Temps de réception : jours | Cellules politique |
|---|---|---:|---|---:|---|
| 001757 | Avène (1810) | 20 | 0 G | 13 | E5:G5 |
| 001848 | Gien (1430) | Absente | Non renseignée | 26 | — |
| 001848 | Avène (1810) | 20 | 0 G | 13 | E12:G12 |
| 001893 | Gaillac (1450) | Absente | Non renseignée | 5 | — |
| 001893 | Avène (1810) | 15 | 0 KG | 24 | E7:G7 |
| 002612 | Gaillac (1450) | Absente | Non renseignée | 5 | — |
| 002612 | Avène (1810) | 20 | 0 KG | 9 | E4:G4 |
| 007923 | Gien (1430) | Absente | Non renseignée | 0 | — |
| 007923 | Avène (1810) | 15 | 0 G | 6 | E25:G25 |
| 016332 | Avène (1810) | 7 | 0 G | 1 | E6:G6 |
| 021081 | Gaillac (1450) | 0 | 900 000 KG | 75 | E23:G23 |
| 029313 | Gien (1430) | Absente | Non renseignée | 0 | — |
| 029313 | Avène (1810) | 7 | 0 G | 1 | E13:G13 |
| 038005 | Gien (1430) | 20 | 0 G | 14 | E11:G11 |
| 039668 | Avène (1810) | 7 | 0 G | 1 | E18:G18 |
| 042342 | Gien (1430) | 5 | 0 ZUN | 14 | E22:G22 |
| 049371 | Avène (1810) | 40 | 888 000 G | 9 | E26:G26 |
| 055703 | Avène (1810) | 30 | 0 G | 13 | E10:G10 |
| 099439 | Avène (1810) | 7 | 0 G | 1 | E28:G28 |
| 268091 | Dépôt Muret (1920) | 0 | 0 ZUN | 10 | E3:G3 |
| 268967 | Dépôt Muret (1920) | 60 | 0 ZUN | 15 | E2:G2 |
| 333362 | Gien (1430) | 10 | 110 000 ZUN | 5 | E16:G16 |
| 338928 | Avène (1810) | 10 | 0 ZUN | 6 | E15:G15 |
| 338929 | Avène (1810) | 10 | 0 ZUN | 6 | E24:G24 |
| 344135 | Gien (1430) | 10 | 0 ZUN | 4 | E14:G14 |
| 426331 | Avène (1810) | 10 | 0 ZUN | 1 | E8:G8 |
| 693055 | Gaillac (1450) | Absente | Non renseignée | 28 | — |
| 693055 | Avène (1810) | 20 | 0 G | 7 | E20:G20 |
| 708073 | Gien (1430) | 10 | 2 000 000 G | 5 | E27:G27 |
| 730384 | Gien (1430) | 10 | 23 500 M | 5 | E19:G19 |
| 734545 | Gien (1430) | 10 | 0 ZUN | 1 | E9:G9 |
| 773474 | Gien (1430) | 20 | 0 G | 6 | E17:G17 |
| 773474 | Gaillac (1450) | 20 | 0 G | 33 | E21:G21 |

G signifie grammes, KG kilogrammes, ZUN unités, M mètres. Exemples : 888 000 G = 888 kg ; 2 000 000 G = 2 000 kg. Les 900 000 de 021081 sont bien exprimés en **KG**.

Quatre articles ont simultanément une sécurité en jours et une sécurité en quantité : **333362, 730384, 049371 et 708073**. La façon de combiner ces deux protections n'est pas écrite : addition, maximum, anticipation des besoins ou autre traitement. La formule actuelle du modèle ne peut donc pas être tenue pour confirmée par le seul tableau.

Le champ est nommé **délai de sécurité**. Les données ne prouvent pas qu'il doit être transformé en une quantité cible égale à « consommation moyenne × nombre de jours ». Une avance de date et un stock physique cible sont deux mécanismes différents à départager.

Le zéro explicite de 268091 est conservé dans le relevé des données, sans le traduire en objectif de stock nul et sans relancer de scénario à zéro jour. Les stocks réellement présents dans les Excel restent la référence à reproduire. Une règle absente n'est pas un zéro : cinq couples stock n'ont aucune politique, et 029313/Gien n'existe que dans le MRP.

## 2. Tailles de lot écrites et vérifiées dans les projections

| Article | Site de fabrication | Lot fixe | Minimum | Maximum | Unité rapprochée des stocks | Cellules Taile de Lot |
|---|---|---:|---:|---:|---|---|
| 268967 | Gien | 0 | 107 800 | 107 800 | ZUN | E2:G2 |
| 268091 | Avène | 0 | 28 800 | 142 485 | ZUN | E3:G3 |
| 773474 | Gaillac | 3 200 000 | 0 | 0 | G | E4:G4 |
| 693055 | Gaillac | 600 000 | 0 | 0 | G | E5:G5 |

La feuille des lots n'a pas de colonne d'unité. L'unité ci-dessus vient du même article dans les stocks et le MRP. Pour 268967, minimum = maximum = **107 800 unités**. Pour 773474, le lot fixe est **3 200 kg** ; pour 693055, **600 kg**. Les zéros des bornes des lots fixes ne signifient pas une fabrication maximale de zéro : leur codification ERP précise reste à confirmer.

La quantité minimale de 268091 est **28 800 unités**, son maximum **142 485**. Le multiple de **14 400** et le nombre maximal de lots par semaine ne sont pas écrits dans cette feuille : ils viennent d'autres informations déjà disponibles et ne doivent pas être perdus.

Le contrôle des quantités prévues confirme trois régularités :

| Article / site | Comportement des entrées H | Portée de la conclusion |
|---|---|---|
| 773474 / Gaillac | **906 lignes positives sur 906**, multiples de 3 200 000 G | Confirme le lot fixe de 3 200 kg écrit pour cette fabrication |
| 693055 / Gaillac | **953 sur 953**, multiples de 600 000 G | Confirme le lot fixe de 600 kg écrit pour cette fabrication |
| 021081 / Gaillac | **170 sur 170**, multiples de 20 000 KG | Multiple très net de 20 tonnes à retrouver dans les règles d'achat/transport ; son origine n'est pas prouvée ici |

Ces comptes portent sur des lignes de plans successifs, pas sur autant de commandes distinctes. Une entrée hebdomadaire de 6 400 kg peut regrouper deux lots de 3 200 kg : elle n'invalide pas la taille du lot.

**Un lot de fabrication n'est pas nécessairement une réception hebdomadaire au dépôt.** Sur les 2 351 entrées positives de 268967 à Muret, aucune n'est un multiple exact de 107 800. Pour 268091, seules 5 sur 2 421 sont des multiples de 14 400. Les règles de lot sont définies à Gien ou Avène, alors que ces flux sont au dépôt. Fractionnement, regroupement et contenu de la colonne Entrée restent à caractériser : on ne peut ni imposer le lot d'usine à chaque réception du dépôt ni conclure que le lot source est faux.

## 3. Le calcul du stock projeté est retrouvé exactement

Dans chaque plan, pour un même article et un même site :

**Stock projeté de la ligne = stock projeté de la ligne précédente + Entrée − Sortie + contribution Stock_physique.**

Colonnes : H = Entrée, I = Sortie, J = Stock_physique, K = Stock fin de semaine. Pour la première ligne, la contribution initiale est déjà portée par J ; on ne doit pas ajouter une seconde fois le stock du fichier Stocks. La relation tient sur les **53 398 lignes** à la précision numérique du fichier, en conservant chaque version séparément.

Exemple 021081/Gaillac, plan du 5 janvier :

- `Feuille1!H277:K277` : 140 000 − 50 532 + 752 312 = **841 780 kg**.
- Ligne 278, semaine suivante : 841 780 + 120 000 − 30 220 + 379 880 = **1 311 440 kg**.

Cette équation explique comment le solde est calculé. Elle n'explique pas, à elle seule, comment le MRP a choisi les entrées et leurs dates.

## 4. Stock total et stock utilisable dans le plan : une distinction essentielle

La colonne J n'est pas seulement un stock initial placé dans la première semaine : **800 lignes** portent une contribution positive après la date du plan. Cela concerne par exemple 021081, 773474 et les deux produits finis.

Pour 021081, dans le plan du 5 janvier : **752 312 kg** sont portés dans la semaine du 5 janvier et **379 880 kg** dans celle du 12 janvier. Leur somme vaut **1 132 192 kg**, exactement le stock total de la photo du lundi 6 janvier (`Stocks!E190`).

Pour 773474/Gaillac, le même plan répartit **6 400 kg** en première semaine et **3 200 kg** au 26 janvier. Leur somme, **9 600 kg**, correspond à la photo du 6 janvier (`Stocks!E1611`).

**Confirmation utilisateur reçue pendant l'analyse : il s'agit de stock déjà présent, disponible plus tard, notamment pour des raisons de qualité.** Les dates de J décrivent donc la disponibilité de quantités physiques existantes. Elles ne doivent pas être traitées comme autant de nouvelles livraisons. La cause précise et l'identité des lots ne sont pas détaillées ligne par ligne dans l'export.

Sur les 1 615 photos appariables au lundi suivant, la somme J égale la photo dans **1 131 cas**, lui est inférieure dans **469** et supérieure dans **15**. Il reste donc des différences de périmètre ou de date à expliquer. Pour 268967, la première photo est 1 092 542 unités, contre 1 089 257 réparties dans J, soit 3 285 unités d'écart. Ce n'est pas un motif pour modifier arbitrairement l'Excel.

Le modèle doit distinguer les quantités présentes et les quantités disponibles à une date donnée. Tout rendre disponible immédiatement, ou compter à nouveau les contributions futures comme de nouvelles marchandises, peut changer les décisions. Le rapprochement détaillé avec l'inventaire est conservé dans le fichier de preuve stock_reconciliation.json, avec les écarts bruts et leurs dates.

## 4 bis. Rapprochement complet avec l'inventaire de stock

Le rapprochement porte sur **tous les 1 615 relevés hebdomadaires présents dans l'inventaire**, associés au plan du dimanche précédent. Les 31 stocks du 1er janvier n'ont pas de plan à cette date. Inversement, 22 plans n'ont pas de photo associée : 14 pour 344135/Gien et 8 pour 029313/Gien. Ces absences restent visibles.

On compare le stock total de l'inventaire à **J de la semaine du plan + toutes les contributions J futures du même plan**, sans ajouter les entrées H et sans utiliser le solde projeté K comme stock de départ.

| Article / site, plan du 5 janvier et inventaire du 6 janvier | Unité | J dans la semaine du plan | J disponible plus tard | Total réparti dans le MRP | Inventaire | Écart MRP − inventaire |
|---|---|---:|---:|---:|---:|---:|
| 021081 / Gaillac | kg | 752 312 | 379 880 | 1 132 192 | 1 132 192 | 0 |
| 773474 / Gaillac | kg | 6 400 | 3 200 | 9 600 | 9 600 | 0 |
| 338929 / Avène | UN | 354 000 | 0 | 354 000 | 354 000 | 0 |
| 268967 / Muret | UN | 981 240 | 108 017 | 1 089 257 | 1 092 542 | −3 285 |
| 693055 / Gaillac | kg | 590 | 1 200 | 1 790 | 1 800 | −10 |
| 002612 / Gaillac | kg | 395 | 0 | 395 | 1 250 | −855 |

Sur l'ensemble : **1 131 égalités exactes, 469 totaux MRP inférieurs à l'inventaire et 15 supérieurs**. Les tolérances numériques ne changent aucun de ces résultats. Le détail conserve les quantités brutes, unités, dates et cellules sources, sans arrondir un écart de 1 UN à zéro.

Des différences répétées méritent une explication de périmètre :

- **002612/Gaillac : −19 kg sur 51 dates** ; −855 kg le 6 janvier.
- **693055/Gaillac : −10 kg sur 51 dates** ; −610 kg le 3 mars.
- **042342/Gien : −1 500 000 UN sur 42 dates**, −1 625 000 sur huit, avec deux autres valeurs ponctuelles. Ce sont des différences entre les deux fichiers, pas une erreur de conversion à corriger automatiquement.
- **268967/Muret : un écart aux 52 dates**, le plus souvent quelques milliers d'unités, mais pas une constante unique.
- **3 mars : 29 couples sur 31 diffèrent simultanément**. Un décalage d'extraction ou de période est une piste, sans cause confirmée.

Le cas 002612/Gaillac du 6 janvier doit rester ouvert : `Feuille1!H158:K158` contient **1 250 kg d'entrée, 0 sortie, 395 kg de stock et 1 645 kg de solde projeté**. L'inventaire corrigé contient **1 250 kg de stock total**. Ces valeurs désignent des choses différentes ; la signification des 1 250 kg confirmés auparavant est demandée à l'utilisateur. Aucun fichier n'est corrigé dans cette analyse.

**Stock de l'inventaire − J de la semaine courante n'est pas automatiquement tout du stock en contrôle qualité.** Cette différence contient les disponibilités futures connues **et** l'écart encore inexpliqué entre les deux extractions. Les quantités non rapprochées doivent rester identifiées séparément.

[Détail du rapprochement stock par stock et date par date](../../artifacts/testing/mrp_source_rules_20260928/stock_reconciliation.json) · [Vérification indépendante](../../artifacts/testing/mrp_source_rules_20260928/validation/export-oracle.json).

## 5. Les plans sont révisés ; ils ne décrivent pas tous des événements exécutés

Comparaison de la même semaine cible entre deux versions hebdomadaires consécutives :

| Article / site | Comparaisons sur semaines communes | Entrées H différentes | Sorties I différentes |
|---|---:|---:|---:|
| 268967/1920 | 2650 | 662 | 681 |
| 268091/1920 | 2428 | 1049 | 1270 |
| 338929/1810 | 1605 | 758 | 745 |
| 021081/1450 | 1083 | 26 | 215 |
| 773474/1450 | 1326 | 272 | 351 |

Les changements existent aussi à court terme. Pour 268967, parmi 153 comparaisons dont la semaine cible se trouve à au plus 15 jours calendaires de la nouvelle version, H change 33 fois. Il n'y a donc pas de gel absolu visible de tous les totaux hebdomadaires. Cela n'exclut pas un horizon gelé pour certains types d'ordres, qui ne sont pas identifiés dans l'export.

Une réception peut être prévue avant l'expiration du « Temps de réception » compté depuis la date de version : elle peut venir d'une commande déjà engagée. L'export ne donne pas sa date de création. Les temps de réception ne permettent donc pas de repousser automatiquement toutes les entrées à « date du plan + délai ».

Pour reproduire les décisions réelles, les prévisions doivent être celles qui étaient connues à la date de décision. La version de décembre ne doit pas piloter une décision de janvier. Les sorties prévues ne remplacent pas automatiquement les consommations et ventes réellement exécutées.

## 6. Les soldes projetés négatifs doivent rester visibles

**1 236 lignes** ont un stock fin de semaine négatif, notamment **623 pour 268091/Muret** et **516 pour 693055/Gaillac**. Les stocks physiques de la feuille Stocks sont, eux, non négatifs.

Un solde projeté négatif exprime un manque dans le plan tel qu'il est exporté. Ce n'est pas la preuve d'un stock physique négatif ni d'une livraison client réellement manquée. Le déficit peut dépendre des dates, besoins, ordres et statuts présents dans l'export. Le supprimer ou le remplacer par zéro ferait perdre une information utile pour reproduire le MRP.

## 7. Rapprochement avec les règles déjà disponibles

Par rapport à `Extract_Données_Complémentaires.xlsx`, 22 règles de sécurité sont identiques, trois valeurs changent et deux règles sont ajoutées :

| Article/site | Ancien fichier | Nouveau fichier | Références ancien → nouveau |
|---|---|---|---|
| 268967/Muret | 25 jours | 60 jours | Politique de Stock MRP!E26 → Politique de stock MRP!E2 |
| 268091/Muret | 20 jours | 0 jour | E25 → E3 |
| 426331/Avène | 7 jours | 10 jours | E20 → E8 |
| 773474/Gaillac | Absente | 20 jours | Nouvelle ligne 21 |
| 021081/Gaillac | Absente | 900 000 kg | Nouvelle ligne 23 |

Le minimum de lot de 268091 change de 14 400 à 28 800 (`Taille de Lots!G2` → `Taile de Lot!G3`) ; la règle de lot de 693055/Gaillac est ajoutée. Les deux autres règles de lot sont inchangées.

**Les paramètres ne portent pas de date d'entrée en vigueur.** Le fait qu'un classeur contienne les stocks de 2025 ne prouve pas que chaque règle de son tableau s'appliquait au 1er janvier. Les nouvelles lignes complètent les anciennes données ; les valeurs contradictoires doivent être datées et expliquées, pas remplacées automatiquement.

Confirmation utilisateur à conserver : pour **268967 (Permixon)**, l'objectif est **un an de stock sur toute la chaîne depuis l'entrée de Gaillac jusqu'au produit fini au dépôt**, exprimé en équivalent produit fini. Il s'agit d'une règle globale qui s'ajoute aux règles locales. Ces deux classeurs ne contiennent ni cette consigne ni les nomenclatures nécessaires à sa conversion. Il faut les rapprocher des BOM existantes et préciser la demande annuelle de référence et les stocks/encours/transits inclus. Compter chaque quantité physique une seule fois ; ne pas additionner les équivalents de composants complémentaires comme s'ils représentaient chacun un produit fini supplémentaire.

## 8. Règles encore impossibles à identifier avec certitude dans ces seuls exports

| Sujet | Ce que nous savons | Ce qu'il manque pour reproduire la décision |
|---|---|---|
| Déclenchement du réapprovisionnement | Besoins, entrées et soldes projetés datés | Calcul exact du besoin net, seuil et horizon utilisés |
| Sécurité en jours | Valeurs explicites, calendrier lundi–vendredi confirmé | Avance de date, couverture physique ou autre application ; combinaison avec la quantité de sécurité |
| Disponibilité du stock | J répartit du stock déjà présent selon sa disponibilité, confirmation utilisateur | Motifs détaillés, identités des lots et traitement des écarts avec l'inventaire |
| Temps de réception | Valeur E constante par article/site | Calendrier, point de départ et opérations comprises |
| Lots | Quatre règles écrites, deux vérifiées directement dans les entrées de fabrication | Règles des autres articles, arrondis, regroupement et fractionnement des entrées au dépôt |
| Achats de 021081 | Toutes les entrées prévues sont multiples de 20 tonnes | Origine : lot d'achat, arrondi, contrat, transport ou autre |
| Commandes ouvertes | Des entrées proches sont présentes | Identifiants, dates de création, ordres fermes/propositions et statuts |
| Besoins et prévisions | Les sorties I sont datées et révisées | Ventilation commandes clients/prévisions/retards/transferts et méthode de consommation des prévisions |
| Capacités et fabrication | Lots et sites connus | Ordonnancement, capacités, changements de série, rendements et délais physiques ; à compléter par les autres sources |
| Calendrier du calcul | 52 versions exportées | Fréquence réelle du MRP et jours de commande/livraison |
| Stock global du 268967 | Objectif d'un an confirmé par l'utilisateur | Répartition réelle entre étapes et assiette annuelle de calcul |

Les conventions actuelles du simulateur — 23 besoins forcés sur capacité × nomenclature, déduction de tout le transit futur sans limiter aux dates utiles, planchers génériques de couverture, pilotage et lissage de fabrication — ne sont pas démontrées comme règles industrielles par ces classeurs. Elles doivent être confrontées aux plans ; conserver des quantités issues des sources ne suffit pas à valider ces algorithmes.

## 9. Contrôles et limites des données

- Aucun doublon article/site/date dans Stocks, aucun doublon article/site/version/semaine dans le MRP.
- 31 couples stock ont 53 photos. 344135/Gien n'en a que trois, en décembre ; 029313/Gien est présent dans 8 versions MRP sans photo de stock correspondante. Une absence n'est jamais remplacée par zéro dans cette analyse.
- Les valeurs de stock suivent un coût unitaire constant par couple article/site ; devise et statuts de valorisation non précisés. Ces valeurs ne constituent pas des règles de commande.
- La correction 002612/Gaillac du 6 janvier est déjà présente avant cette analyse : `Stocks!E946 = 1 250 kg`, `F946 = 1 575`.
- Graph concorde avec les 53 dates de Stocks pour 773474. Son total général additionne des photos : il ne représente ni un stock à une date ni un flux annuel.
- Une recherche descriptive de rapprochement entre le solde K et différents horizons de besoins futurs est conservée dans le JSON. Elle n'identifie pas un algorithme de commande unique et n'est pas utilisée pour modifier la simulation.
- Les empreintes des deux classeurs sont restées inchangées. Les calculs sont faits en mémoire sur les données réelles ; aucun test de modification de date, d'altération ou de disparition de fichiers n'a été exécuté.

## 10. Ce qui diffère dans le MRP effectivement exécuté

Complément du 28 septembre, après les deux simulations de cinq ans `mrp_rules_integration_20260928`. Cet audit relit leurs résultats, le code et les Excel ; il ne modifie aucun moteur, paramètre, classeur ou HTML et ne lance pas de nouvelle simulation. Le logiciel ERP est inconnu, selon la réponse utilisateur. **Nous pouvons établir ce que fait notre moteur et ce que montrent les exports ; nous ne pouvons pas déclarer retrouvé tout l'algorithme industriel.**

Les contrôles précédents ont vérifié la conservation des quantités, la cohérence des lots et la fidélité arithmétique des courbes aux CSV, sur les scénarios et invariants couverts. Ces propriétés ne certifient pas que les décisions MRP reproduisent celles de l'entreprise. Le présent audit trouve notamment un problème de rattachement hebdomadaire et des hypothèses de pilotage encore non validées.

| Sujet | Modèle réellement exécuté | Sources industrielles / conclusion |
|---|---|---|
| Demande client | Une année issue de `demand_PF.xlsx`, répartie quotidiennement et répétée tous les 365 jours | Les besoins I des 52 plans Flow sont révisés. Volumes et profils diffèrent ; I n'est pas une vente réalisée |
| Besoins de composants | Pour 23 couples, priorité à capacité journalière × nomenclature | Le besoin planifié source varie par semaine. Une capacité confirmée ne justifie pas de la traiter comme une demande |
| Fabrication intermédiaire | Autre plancher capacité × nomenclature des destinations, puis commande asservie au stock | Ce plancher existe aussi en dehors de la liste des 23 forçages. Son équivalence avec l'ERP n'est pas démontrée |
| Sécurité en jours | Convertie en quantité cible ; maximum avec la sécurité quantitative et les autres planchers | Le libellé « délai de sécurité » ne confirme ni ce mécanisme ni le choix du maximum |
| Dates des besoins et réceptions | Le calcul net soustrait toutes les réceptions futures engagées | Les soldes sources sont datés semaine par semaine. Le calcul exact d'allocation aux dates reste inconnu |
| Stock indisponible | Option initiale ajoutée mais inactive dans les deux runs ; réceptions d'ouverture matérialisées à la date utilisable | J futur est du stock déjà détenu. Les dates de livraison et d'entrée du carnet peuvent aussi différer de plusieurs mois |
| Ordres de fabrication initiaux | Tous les O.Proc importés sont traités comme des encours dont les composants ont été engagés avant J0 | Les dates et quantités existent, mais les dates réelles de prélèvement matière ne sont pas fournies |
| Révision des ordres | Carnet initial importé une fois ; nouvelles décisions quotidiennes ; pas de rééchelonnement des ordres engagés dans le parcours BASE examiné | Les entrées et besoins des versions Flow changent. Statuts fermes/proposés et identifiants manquent pour reconstituer cette révision |
| Lots | Tailles souvent respectées, mais pilotage des lancements propre au modèle | Respecter un lot de 3,2 t ne garantit ni le bon nombre de lots ni les bonnes dates |
| Délais | Délais du graphe, distributions aléatoires et marges de couverture | Le « temps de réception » Flow ne décrit pas nécessairement les mêmes opérations |
| Périmètre | Deux PF et une partie des articles/sites ; certains stocks de sites entiers sont utilisés | Plusieurs composants semblent couvrir davantage de produits ou d'activités. Cinq couples Flow n'ont pas de série de stock simulée |
| Objectif Permixon | Aucune commande globale identifiée imposant un an sur toute la chaîne | La règle utilisateur est globale ; son assiette et sa répartition ne sont pas encore traduites dans le pilotage |

### Besoins et programme de fabrication : les deux principaux forçages

Pour **338929/Avène**, le besoin utilisé vaut **203 550 UN chaque jour**, contre une demande nominale moyenne d'environ **9 798 UN/j**. La cible de sécurité atteint **2,44 à 2,85 millions d'unités**. Le besoin à capacité maximale a donc une influence directe sur le surstock de packaging ; la totalité de l'écart de stock ne peut cependant pas lui être attribuée isolément.

Sur les 38 semaines présentes du premier plan, avec la convention actuelle de fin de semaine, le besoin source est **3 267 182 UN**, le signal brut nominal **2 517 682**, mais le signal utilisé **54 144 300** : **16,57 fois le besoin source**. Cette dernière somme est un signal de dimensionnement répété, pas une quantité réellement commandée ou consommée.

Un second mécanisme existe pour **773474/Gaillac** : le signal de fabrication a un plancher de **1 486 826,572 G/j**, calculé à partir de la capacité de Gien et de sa nomenclature. Le retirer de la liste des besoins statiques ne supprimerait pas à lui seul ce plancher. La commande de fabrication suit ensuite :

```text
cible = max(stock de base, jours de cible PF × signal)
commande brute = signal + 0,25 × (cible − stock)
commande lissée = max(0, 0,2 × commande précédente + 0,8 × commande brute)
```

Les règles de lots, composants disponibles, capacités et campagnes limitent cette commande. Dans les runs examinés, les jours de cible PF valent zéro. À J1, `0,8 × 1 486 826,572 = 1 189 461,2576 G`, puis la taille de lot conduit à fabriquer **3,2 millions G**. Ces gains de commande ne sont pas des règles retrouvées dans les Excel.

Références : `run_first_simulation.py:8580`, `:8634`, `:11201`, `:11212`, `:12324` ; liste des 23 couples dans `config/reproduction_20260920/nominal.json:101`. La dynamique des systèmes et les réactions à l'état peuvent être conservées en faisant évoluer cette couche de décision.

### Paramètres renseignés et paramètres qui déclenchent réellement une décision

Pour **773474/Gaillac**, les 20 jours sources changent la cible affichée à J0 : **7,285 → 29,142 millions G**. Mais le contrôleur de fabrication locale ne lit pas cette sécurité. La boucle de réapprovisionnement traite les paires ayant une liaison entrante ; elle ne transforme pas ce besoin affiché en ordre de fabrication local. Les premiers lancements J1/J8/J15/J22 sont identiques. **La règle est visible dans le diagnostic, sans être appliquée directement à la fabrication.**

Pour **021081/Gaillac**, les 900 000 kg sont bien lus comme cible. Pourtant, les deux runs ne créent **aucune nouvelle commande** sur 1 825 jours : les 23 réceptions proviennent toutes du carnet initial, pour **1 320 000 kg**. Le stock minimal reste **941 844 kg** et le besoin net reste nul. Une amélioration de sa courbe dans la variante ne démontre donc pas l'effet d'un nouvel achat déclenché par cette sécurité.

Pour **693055/Gaillac**, le lot source de 600 kg est connu, mais aucun processus de fabrication n'existe dans le graphe. Le modèle reçoit uniquement un ordre initial de 600 kg à J55. Il ne peut donc pas reproduire la suite des fabrications prévues dans le MRP par un simple changement de taille de lot.

Pour **268091**, le minimum de lot passe effectivement à 28 800 UN dans la variante ; sa sécurité au dépôt reste **20 jours**, conformément à la décision utilisateur. Pour **268967**, 60 jours remplacent 25 dans la variante, mais l'adéquation de leur conversion en stock cible reste à vérifier.

### Sécurité, disponibilité datée et réservations

Le modèle combine les protections par un maximum. Exemple 333362/Gien à J0 : `max(110 000 UN, 154 000 UN/j × 14 jours calendaires) = 2 156 000 UN`. Cela ne démontre pas comment l'ERP combine ses champs de quantité et de délai.

Il existe des mécanismes ERP où un délai de sécurité **avance les dates des besoins et des réceptions**, en complément du stock de sécurité quantitatif : c'est notamment la définition documentée par [SAP, Safety Time / Actual Range of Coverage](https://help.sap.com/docs/SAP_ERP/85d3fce10e264972a0155c8b46ecf93b/8aaace5314894208e10000000a174cb4.html?locale=en-US). Cette référence explique une hypothèse à départager ; elle ne prouve pas le paramétrage du système industriel étudié, dont le logiciel est inconnu.

Le calcul net courant utilise `cible + retard − disponible − toutes les réceptions futures`. Les réceptions ont bien des dates dans le pipeline, mais cette soustraction ne les filtre pas selon la date du besoin. En outre, une paire provenant du snapshot n'utilise la couverture complète du délai que si elle est explicitement déclarée dynamique ; la liste correspondante est vide dans les runs. **Besoins dynamiques, couverture du délai et réception datée doivent être traités ensemble.** Le retrait isolé du forçage de 338929 avait déjà causé des ruptures ; il ne constitue pas une correction validée.

Les réservations sont distinctes des départs. À J0, sur les 9,6 millions G de 773474/Gaillac, 3,2 millions partent et 6,4 millions sont réservés pour J9/J18 : le disponible devient zéro, mais ces 6,4 millions restent sur le site. Cette distinction explique pourquoi un stock disponible ne se compare pas directement à un inventaire « Stock Total ».

Références : `run_first_simulation.py:12366`, `:12418`, `:12436`, `:13333`, `:13433`. La colonne `bn_qty` est recalculée après les commandes, en fin de journée ; elle ne décrit pas seule la décision initiale.

## 11. Deux différences de calendrier démontrées

### Livraison et disponibilité : cas 021081

Dans `Extract_En_cours.xlsx`, feuille `Sheet1` :

| Ligne | Quantité E | Date de livraison G | Champ H | Date d'entrée I |
|---|---:|---|---:|---|
|24|100 000 kg|7 janvier 2025|75|23 avril 2025|
|40|40 000 kg|7 janvier 2025|75|23 avril 2025|
|41|40 000 kg|14 janvier 2025|75|30 avril 2025|

Les dates G et I sont des valeurs stockées dans le fichier. **Le moteur n'ajoute pas arbitrairement trois mois à une date d'entrée : il importe ces deux dates.** Il interprète G comme livraison physique et I comme disponibilité, puis ne matérialise la réception en stock qu'à I (`run_first_simulation.py:5283`). Le délai de lane sert séparément à reconstruire le départ.

Le nouveau plan MRP du 5 janvier présente **140 000 kg en H277 au repère du 5 janvier**. Les 23 commandes initiales regroupées selon leur date G reproduisent exactement les 14 semaines H positives de ce premier plan, pour 1,32 million kg. Leurs dates I ne les reproduisent pas. Sans identifiants, cela ne prouve pas une correspondance individuelle de chaque ordre, mais établit une correspondance complète des quantités hebdomadaires.

Entre G et I, les quantités du carnet sont encore traitées comme du pipeline dans le modèle. Si G désigne bien la livraison physique au site et si le carnet est exécuté à ces dates, elles sont pourtant déjà physiquement sur le site : **140 000 kg au 13 janvier**, jusqu'à **1 180 000 kg au 21 avril**. Trente-six des 52 photos sont concernées ; moyenne de cette quantité intermédiaire : **404 615 kg**. Ce sont des dates planifiées de carnet, pas des preuves de livraisons industrielles exécutées.

Ce mécanisme est distinct des **379 880 kg déjà détenus** du J futur du 5 janvier. L'option de disponibilité du stock initial ne traite pas à elle seule toutes les réceptions ultérieures entre livraison physique et disponibilité. Pour comparer au stock total industriel, il faut représenter explicitement ces états et confirmer le sens du « temps de réception ». Le calendrier des 75 jours n'est pas établi : du 7 janvier au 23 avril, on compte 106 jours calendaires, ou 76 lundi–vendredi en excluant le départ et incluant l'arrivée.

### Le dimanche MRP ne peut pas être tenu systématiquement pour une fin de semaine

La carte actuelle compare les flux simulés du lundi au dimanche au repère dimanche d du MRP. Or, pour les 14 entrées positives de 021081, le dimanche qui correspond aux dates de livraison G est **celui qui précède ces livraisons** :

- H277, repère 5 janvier, 140 000 kg : livraisons G du mardi 7 janvier.
- H278, repère 12 janvier, 120 000 kg : livraisons G du mardi 14 janvier.
- H279, repère 19 janvier, 100 000 kg : livraison G du mardi 21 janvier.

**La convention de fin de semaine utilisée par la carte est donc inadaptée à ce rapprochement précis.** Elle introduit un rattachement de sept jours différent de celui des commandes sources. Les contrôles CSV→courbes validaient le calcul de cette convention, pas sa signification métier. Cette conclusion est démontrée pour H/021081/premier plan ; son extension aux I, aux autres articles et à la frontière dimanche/lundi reste à confirmer. Aucun HTML n'est corrigé silencieusement dans cet audit.

Les deux interprétations ont été recalculées sans combler les semaines absentes :

| Produit / dépôt | Convention de rattachement | Semaines complètes en 2025 | Sorties I prévues | Demande nominale sur ces jours | Écart modèle/source |
|---|---|---:|---:|---:|---:|
|268091|Semaine se terminant au dimanche indiqué|47|4 194 201 UN|3 132 285 UN|−25,32 %|
|268091|Lundi–dimanche suivant le repère|48|4 831 275 UN|3 213 884 UN|−33,48 %|
|268967|Semaine se terminant au dimanche indiqué|51|2 466 126 UN|1 558 383 UN|−36,81 %|
|268967|Lundi–dimanche suivant le repère|51|2 480 046 UN|1 558 383 UN|−37,16 %|

Les périmètres aux bornes changent : pour 268091, la seconde convention inclut I545 = 637 074 UN. À mêmes 47 lignes source, le seul déplacement temporel modifie le biais de −25,32 % à −24,07 %. Il faut donc distinguer changement de période et décalage des courbes. Dans tous ces cas, la demande nominale diffère sensiblement du besoin source. **Ces nombres comparent une demande du modèle à une sortie prévue, pas à une vente réellement exécutée.**

Le profil nominal ajoute une autre convention : les 52 étapes hebdomadaires commencent au 1er janvier, donc mercredi–mardi en 2025, puis le dernier jour du cycle de 365 jours vaut zéro. Les demandes négatives du fichier de 268967 sont compensées sur les semaines positives suivantes : huit semaines changent, total annuel conservé. Les projections Flow ne sont pas intégrées comme prévisions révisées au fil des cinq années.

## 12. Les encours initiaux et le périmètre expliquent une partie des écarts

### Une hypothèse d'encours qui pèse fortement sur la consommation

Les **22 O.Proc** initiaux sont traités en mode `wip` : leurs composants sont supposés engagés avant J0 et ne sont pas prélevés dans les stocks de 2025 lors de leur mise à disposition. Cela inclut 20 ordres de 268091, un de 773474 et un de 693055, sans nomenclature active pour ce dernier.

Exemple : l'ordre source de la ligne 91, **141 780 UN de 268091**, a une livraison au 12 mai et une entrée au 26 mai. Le modèle suppose néanmoins ses composants déjà engagés avant J0 et inscrit `issue_day = -1` dans l'audit, sans débit du stock initial. Les dates effectives de prélèvement matière ne sont pas présentes dans les données disponibles : **ce traitement est une hypothèse du nominal, pas une observation de production.**

Sur 2025, le nominal met à disposition **3 716 915 UN de 268091**, dont **1 945 715 issues des ordres initiaux** et **1 771 200 fabriquées par les nouvelles décisions**. Le packaging 338929 n'est nouvellement consommé que pour ces 1 771 200. Assimiler toute la mise à disposition PF à une fabrication consommant les matières de l'année fausserait l'explication des stocks. Références : `run_first_simulation.py:10742`, `:10802`, registre des lots du run.

### Des écarts de périmètre à éclaircir entre composants et produits finis

Sur les semaines présentes et communes du premier plan, avec la convention actuelle de semaine se terminant au dimanche, besoins composant I divisés par besoins PF I × nomenclature du modèle : **42,43 pour 002612/Avène** (39 semaines), **12,32 pour 007923/Avène** (37 semaines), **4,57 pour 773474/Gien** (26 semaines), **7,92 pour 021081/Gaillac** (34 semaines). Le caractère partagé des matières Avène avait été signalé par l'utilisateur. Les deux derniers rapports imposent également d'examiner le périmètre amont de Permixon.

Ce ne sont pas des coefficients d'allocation validés. Fabrication, sorties dépôt, variation des stocks, décalages de plan et ordres initiaux peuvent différer. On ne peut pas automatiquement diviser les stocks par ces rapports. Une allocation cohérente doit considérer ensemble demande, stocks et commandes en cours.

Cinq couples Flow n'ont pas de série de stock dans le modèle : **001848/Gien, 001893/Gaillac, 002612/Gaillac, 007923/Gien, 029313/Gien**. Les quatre premiers représentent 212 photos ; le dernier a des plans mais aucune photo. Une règle MRP ne remplace pas un périmètre absent.

### La règle d'un an pour Permixon a besoin d'une assiette explicite

Avec la seule nomenclature actuelle, 1 PF268967 consomme **9,654718 G de 773474**, soit **0,08631317892 KG de 021081** en remontant la chaîne. Les stocks initiaux de 021081/Gaillac, 773474/Gaillac et Gien, et du PF au dépôt représentent **16 839 402 équivalents PF** si on les affecte tous exclusivement à ce produit. Cela correspond à **10,685 années de la demande nominale de 1 575 986 UN/an**.

**Ce calcul conditionnel ne signifie pas que l'entreprise possède dix ans de stock.** Il démontre que l'assiette du modèle, les allocations ou les coefficients doivent être clarifiés avant de traduire la consigne d'un an. Le calcul exclut les stocks fournisseurs, transits, encours et composants complémentaires ; ceux-ci ne sont pas additionnés comme des PF supplémentaires. Aucun stock n'est réduit dans cet audit.

## 13. Ce que les derniers essais permettent de conclure

Sur 28 couples et 1 407 photos hebdomadaires comparables, l'erreur absolue moyenne divisée par le stock moyen source a une médiane non pondérée de **77,03 % dans le nominal**, **76,84 % dans la variante**. Dix-huit couples s'améliorent, dix se dégradent. Aucun n'est sous 10 % sur cette mesure. Avec la clôture du jour de la photo au lieu de la veille, la médiane devient **76,85 → 77,21 %** : le faible gain global dépend du rapprochement horaire.

Exemples nominal → variante : **338929/Avène 244,47 → 250,24 %**, **773474/Gaillac 82,89 → 83,13 %**, **268091/dépôt 65,77 → 64,70 %**, **268967/dépôt 27,96 → 42,58 %**. Les erreurs de périmètre et les stocks indisponibles limitent leur interprétation comme erreur du seul MRP.

La taille des lots est souvent correcte : 773474 est produit par 3,2 t ; pourtant le premier plan prévoit 64 t jusqu'à sa dernière ligne du 20 juillet, contre 25,6 t nominales mises à disposition jusqu'à cette date. Pour 693055, 11,4 t sont prévues jusqu'au 7 décembre, contre 0,6 t issue du seul ordre initial. Ce sont des comparaisons entre plans et exécutions modélisées, avec la réserve de période hebdomadaire décrite plus haut.

Les aléas ne sont pas appariés : même graine 42, mais `common_random_numbers=false`. Exemple vérifié : les mêmes 54 tranches de 5 000 UN de 338929 commandées à J42 ont les mêmes départs J42–118, mais arrivent **J59–135 dans le nominal** et **J80–156 dans la variante**. Une modification d'autres commandes décale le flux de tirages. L'écart entre les courbes ne peut donc pas être attribué exclusivement aux paramètres locaux modifiés.

Dans ces runs BASE, les incidents fournisseurs et la génération de risques dépendant de l'état sont désactivés, tandis que les délais aléatoires sont actifs. La dépendance des décisions de production et d'achat aux stocks reste présente. Cela distingue le fonctionnement normal du moteur de sa couche d'incidents et de cascades.

## 14. Ordre de travail proposé

1. **Fixer les périmètres et les dates comparées.** Définir le repère hebdomadaire Flow, distinguer livraison physique/disponibilité, relier les besoins au bon article/site et identifier les produits couverts. Présenter les conventions concurrentes tant qu'elles ne sont pas confirmées.
2. **Reconstituer l'état de départ et les commandes engagées.** Séparer stock utilisable, détenu indisponible, réservé, transport et encours ; confirmer quels O.Proc avaient réellement consommé leurs composants avant J0. Exploiter les dates G/I existantes sans en inventer le calendrier.
3. **Préciser le sens des règles industrielles.** Délai de sécurité, quantité de sécurité, combinaison des deux, temps de réception, statuts des ordres et possibilités de rééchelonnement. Traduire la règle globale d'un an de Permixon sur une assiette définie. Documenter les hypothèses restantes avant de les intégrer au pilotage.
4. **Faire piloter achats et fabrication par les mêmes besoins datés.** Traiter ensemble les forçages capacité×BOM, les réceptions par échéance et le contrôleur de fabrication, selon les règles clarifiées au point précédent. Relier effectivement la politique 773474 aux lancements. Conserver le moteur de dynamique des systèmes, les capacités, les lots et les réactions à l'état.
5. **Valider progressivement.** Reproduire d'abord le tableau MRP hebdomadaire source avec ses propres H/I/J ; confronter ensuite les décisions proposées aux versions successives, puis la trajectoire simulée aux photos de stock. Identifier les règles sur une partie des semaines et vérifier sur les autres. Comparer les variantes avec des aléas appariés et conserver le nominal historique comme référence.

L'information supplémentaire la plus utile serait un extrait conservant les **identifiants d'ordres, leur type/statut, date de besoin, livraison et disponibilité**, accompagné de la définition des colonnes E/G/H/I/J et des périodes. Sans ces informations, plusieurs règles de décision peuvent produire le même tableau hebdomadaire.

## 15. Suite : comparaison corrigée et examen des O.Proc sur tous les plans de 2025

### Carte et comparaison reproductible

La [carte de comparaison actualisée](../../resultats/comparaison_mrp_fiabilisee_20260928/comparaison.html), bouton **Essais MRP 2025**, conserve les deux suivis de lots et les autres onglets historiques. Le panneau de comparaison utilise deux recalculs de 1 825 jours : nominal conservé et variante des paramètres sources. Leurs 33 CSV respectifs sont identiques aux références antérieures. Les figures de comparaison restent limitées à 2025.

La vue permet désormais de choisir explicitement trois conventions : dimanche–samedi à partir du repère source, lundi–dimanche suivant ce repère, et l'ancien lundi–dimanche se terminant au repère. La première est proposée par défaut, conformément au rapprochement des commandes 021081 ; sa généralisation industrielle reste non confirmée. Les bornes exactes accompagnent le survol, les exports et le tableau des périodes comparées. Une fenêtre doit inclure le repère et les sept jours agrégés ; aucune semaine partielle n'est totalisée.

Les stocks disponible, réservé et détenu indisponible restent distincts. Quand le registre de disponibilité manque, le stock total simulé n'est pas présenté comme entièrement reconstitué et aucune valeur manquante n'est transformée en zéro. Les photos industrielles restent les données de référence. Les cinq couples sans série simulée restent accessibles dans la couverture.

L'onglet Entrées / sorties expose aussi le carnet initial du couple sélectionné : quantité, type, date G de livraison prévue, date I de disponibilité interprétée, fichier et ligne CSV. Ces lignes ne sont pas ajoutées une seconde fois aux courbes. Le tableau porte sur les couples présents dans Flow ; les vingt OF de 268091/Avène ne font pas partie de ce sélecteur, faute de couple correspondant dans l'export.

### Réponse à la vérification des O.Proc avec le MRP complet

Les 52 versions des plans ont été examinées, en conservant séparément leurs cibles 2025 et 2026. Les 22 O.Proc du carnet comprennent vingt OF de 268091, un de 693055 et un de 773474. Les besoins et entrées projetés permettent des rapprochements de quantités ; les fichiers ne donnent pas les identifiants communs, statuts de lancement ou prélèvements matière nécessaires pour identifier l'état physique de chaque OF.

Un signal nouveau apparaît pour **338929** dans le premier plan du 5 janvier : **10 des 13 regroupements selon la date G** des OF 268091 correspondent exactement au besoin d'étuis après une majoration de **2 % et arrondi supérieur**. Aucun de ces treize groupes ne correspond simplement au rapport 1:1.

| Ordre(s) dans Extract_En_cours | Quantité de PF | Besoin d'étuis dans Flow_Data_MRP_results | Rapprochement |
|---|---:|---:|---|
| Ligne 75 | 139 660 | I705 = 142 454 | arrondi supérieur de 139 660 × 1,02 |
| Lignes 72 + 82 | 98 315 | I707 = 100 282 | arrondi supérieur de 98 315 × 1,02 |
| Ligne 91 | 141 780 | I723 = 144 616 | arrondi supérieur de 141 780 × 1,02 |

Les vingt OF totalisent **1 945 715 PF**, soit **1 984 632 étuis** après majoration et arrondi par ordre. Sur les repères du 5 janvier au 11 mai, le premier plan demande **2 129 248 étuis**, soit cette somme plus **144 616**. Trois déplacements de dates candidats permettent un rapprochement quantitatif de tous les ordres ; les valeurs répétées empêchent d'en faire une identification certaine des OF.

Aux dates G d'origine restant à venir, les correspondances passent de 10/13 à **4/12, 3/12 puis 2/11** dans les trois versions suivantes ; aucune ne persiste ensuite à ces dates d'origine. Les plans sont révisés : le rapprochement du premier plan n'est pas une règle de quantités figées pour toute l'année.

Pour 693055, l'ordre de 600 000 G correspond à H788 dans la semaine de sa date G. Pour 773474, H969 contient 9 600 000 G, soit trois lots fixes, sans pouvoir isoler l'ordre initial de 3 200 000 G. Pour 268091, le plan usine **268091/1810 est absent** : le plan de produit fini fourni concerne le dépôt 1920. On ne peut pas assimiler une réception au dépôt au lancement d'un OF à Avène.

**Conclusion : les plans comportent des besoins futurs compatibles avec les OF du carnet ; ils ne démontrent pas que toutes leurs matières étaient déjà engagées avant J0. Ils ne suffisent pas non plus à prouver la date réelle des prélèvements.** L'hypothèse globale du mode `wip` reste donc à remplacer par un traitement explicite des états d'ordres, avec les données permettant de les distinguer. Aucun basculement global vers une consommation à la réception n'est effectué sur cette seule inférence.

### Le facteur de 2 % n'est pas une perte physique démontrée

La nomenclature disponible écrit bien un étui par PF : `268091.xlsx/BOM!B15 = 1 000`, `E15 = 1 000`, `F15 = UN.` ; `Data_poc.xlsx/BOM!H46 = 1 000`, `K46 = 1 000`, `L46 = UN`. Le graphe et le moteur conservent ce rapport. Aucun coefficient de rebut/rendement de 2 % n'a été trouvé dans les fiches BOM/FIA et politiques pertinentes consultées.

Il s'agit donc d'une **majoration de besoin planifié candidate, absente des nomenclatures disponibles**, et non d'une donnée explicitement renseignée perdue à l'import. Une marge de 2 % et un rendement de 98 % ne sont pas équivalents : le second demande environ 2,0408 % de matière en plus. Le plan ne permet pas d'attribuer cet excédent à du rebut effectivement consommé ou détruit. La BOM physique et le registre matière ne sont pas modifiés ; un futur essai devra distinguer majoration de planification et consommation réelle.

Reproduction : [script des recalculs et du rendu](../../artifacts/testing/mrp_comparison_reliable_20260928/reproduce.py), [identité des 66 CSV](../../artifacts/testing/mrp_comparison_reliable_20260928/identity.json), [oracle indépendant](../../artifacts/testing/mrp_comparison_reliable_20260928/validation/source_oracle.py). L'exécution utilise un nouveau dossier de sortie, les fichiers sources restant inchangés. La correction concerne la comparaison ; les mécanismes MRP listés en sections 10–14 ne sont pas encore corrigés par ce rendu.

Validation sur les sources finales stabilisées : **8 tests ciblés en mémoire**, invariants des **deux simulations de cinq ans**, **299 440 contrôles numériques indépendants** sans échec (écart maximal 1e-9) et **20 parcours/contrôles du panneau dans Chromium** réussis. Ces derniers examinent 1 417 083 points de séries, les trois conventions, les 33 couples, les cinq vues, les versions MRP, les exports et les deux suivis de lots. Le contrôle géométrique SVG est échantillonné ; ces preuves ne certifient ni toutes les interactions possibles ni la calibration industrielle.

Preuves finales : [oracle Excel/CSV](../../artifacts/testing/mrp_comparison_reliable_20260928/validation/result_final.json), [navigateur du panneau](../../artifacts/testing/mrp_comparison_reliable_20260928/ui/run3/browser.json), [agrégation doctor/tests/qualification/navigateur](../../artifacts/testing/mrp_comparison_reliable_20260928/toolbox/gate-f53c136a6db341a1b2ec103369444720/manifest.json). Le premier démarrage Playwright avait été refusé sur un canal IPC Windows avant ouverture du navigateur ; les vérifications réussies ont été exécutées après approbation de l'outil hors sandbox, sans changer les protections système. Les preuves intermédiaires ne sont pas comptées comme validation du rendu final.

## 16. Essais séparés : échéances des réceptions et sécurité de fabrication

Cette étape modifie le moteur uniquement par **deux options désactivées par défaut**. Le nominal est recalculé sur 1 825 jours : ses **33 CSV sont identiques octet par octet** à la référence précédente. Les classeurs industriels, les sécurités sources, la BOM physique et l'hypothèse actuelle des OF initiaux sont conservés. Aucun essai à zéro jour n'est introduit.

La [nouvelle carte de comparaison](../../resultats/comparaison_mrp_date_20260928/comparaison.html), bouton **Comparaisons 2025**, contient quatre simulations de cinq ans : nominal historique, référence avec règles sources, filtrage des réceptions par échéance, puis filtrage avec sécurité de fabrication. Les comparaisons industrielles portent sur 2025. Les trois derniers calculs partagent le graphe des règles sources et les aléas indexés par liaison/jour/origine/rang ; des commandes supplémentaires peuvent rester sans correspondant. Le nominal garde son mécanisme aléatoire historique. Une seule graine ne permet pas une conclusion statistique multigraines.

### Changements et lecture de la carte

- `--mrp-receipt-netting-mode within_cover` ne déduit du besoin de réapprovisionnement par transport que les réceptions encore attendues dans la fenêtre de couverture existante, borne incluse. Les commandes plus tardives restent engagées et seront reçues. Les contrôleurs de stocks fournisseurs gardent leur règle historique. L'association à une modification initiale du pipeline non indexée est explicitement refusée.
- `--production-mrp-safety-targets` rend les sécurités des produits fabriqués effectives dans les cibles MPS et fabrication : maximum entre cible historique, quantité de sécurité fixe et jours de sécurité convertis × signal journalier du contrôleur, puis multiplicateur de pilotage habituel. Gains de dynamique des systèmes, capacités, nomenclatures, lots et délais restent en place.
- La vue **Besoins MRP** sépare réceptions dans l'horizon et plus tardives, précise l'échéance au survol et à l'export, et montre le calcul avant émission de commande séparément de la fin de journée. Une absence de relevé ne devient pas zéro. Une autre courbe affiche la cible réellement utilisée par la fabrication, distincte du diagnostic MRP et de la quantité produite.

Les autres onglets et les deux suivis de lots de cette copie restent ceux du nominal historique. Les nouveaux scénarios sont accessibles dans le panneau de comparaison ; cette carte ne présente pas une nouvelle généalogie de lots pour chacun des quatre calculs.

### Résultats : ne pas adopter ces deux changements isolément comme MRP industriel

Le tableau utilise les **52 dates des photos industrielles**, rapprochées de la clôture du dimanche précédent. Les valeurs sont des moyennes à ces dates, pas des moyennes sur tous les jours. L'inventaire source est un stock total ; le modèle comparé fournit un disponible. Ce rapprochement décrit un écart de niveaux, sans prouver une identité de périmètre physique.

| Article / site | Moyenne des photos sources | Référence règles sources | Réceptions datées | Avec sécurité fabrication |
|---|---:|---:|---:|---:|
| 338929 / Avène | 521 515 UN | 1 735 773 UN | 2 895 773 UN | 2 895 773 UN |
| 773474 / Gaillac | 25 169 kg | 4 062 kg | 4 062 kg | 41 415 kg |
| 021081 / Gaillac | 1 558 863 kg | 1 618 835 kg | 1 618 835 kg | 1 274 989 kg |

Pour **338929**, l'écart absolu moyen aux photos passe de **1 317 169 à 2 461 885 UN** avec le filtrage des réceptions : le résultat se dégrade. Écarter une commande tardive du besoin immédiat peut provoquer des nouvelles commandes répétées avant l'arrivée des précédentes. Le stock moyen quotidien 2025 augmente d'environ 66,8 %. Ce filtrage de fenêtre n'est donc **pas un calcul MRP complet des besoins et réceptions à chaque date** : il ne traite ni chaque rupture intermédiaire ni le remplacement d'un besoin déjà couvert plus tard.

Exemple vérifié dans les CSV : à **J53**, la variante commande **270 000 étuis**, disponibles entre **J134 et J210**, alors que sa fenêtre se termine à **J130**. Aucune de ces nouvelles quantités ne peut couvrir le manque qui motive cette décision. Sur J52–J58, elle engage 1 860 000 unités supplémentaires, dont 1 075 000 arrivent après la borne propre à leur décision ; la référence appariée ne commande pas pendant ces sept jours. Ce cas doit devenir un critère métier de la prochaine correction, au-delà de la seule justesse arithmétique du filtrage.

Pour **773474 à Gaillac**, la sécurité de fabrication réduit l'écart absolu moyen de **21 108 à 16 246 kg**, mais fait passer le modèle d'un stock trop faible à un stock trop élevé. Le signal de fabrication conservé est de **1 486 826,572 G/jour**, encore lié à une capacité aval. À J0, avec 20 jours ouvrés convertis en 28 jours calendaires, la cible appliquée vaut **41 631 144,016 G, soit 41 631 kg**. Elle diffère de la cible du diagnostic MRP, qui utilise un autre signal. Il faut corriger la base des besoins avant de considérer ce niveau comme une cible industrielle démontrée ; diminuer arbitrairement les jours sources ne résoudrait pas ce problème.

La fabrication supplémentaire de 773474 consomme davantage de **021081** : son écart absolu moyen aux photos passe de **322 608 à 404 142 kg**. Sur cinq ans, les trois variantes ont les mêmes quantités servies aux clients pour les deux PF ; ces hausses de stocks et de production n'apportent pas de gain de service mesuré dans cet essai. Les options restent expérimentales, sans remplacement du nominal.

Pour 021081, l'absence de nouvelles commandes **vers Gaillac** ne signifie pas absence d'activité amont : des commandes alimentent les stocks des fournisseurs. Dans la variante avec fabrication, le besoin net Gaillac est positif 114 jours, mais aucun des quatre fournisseurs n'atteint alors le lot expédiable de 20 000 kg. Leur maximum constaté sur cinq ans est de 19 709 kg ; ce n'est pas un plafond configuré. Le contrôleur utilise une capacité amont estimée et n'engage plus son réapprovisionnement proactif quand le signal de demande est nul. Ce diagnostic explique la différence entre besoin calculé et commande réalisable ; il ne démontre pas une capacité industrielle réelle de ces fournisseurs.

### Suite métier et portée des vérifications

La priorité devient de **calculer les besoins à partir du programme de fabrication et de la demande**, en réservant les capacités à leur rôle de limite, puis d'affecter les réceptions aux besoins datés pour éviter les commandes de remplacement répétées. Le moteur de dynamique des systèmes reste le cadre d'exécution. Les jours de sécurité source sont conservés. Les statuts physiques des O.Proc, le périmètre partagé Avène et l'objectif annuel de stock de toute la chaîne 268967 restent des sujets distincts non résolus par ces deux options.

La reproduction utilise [study.py](../../artifacts/testing/mrp_dated_receipts_20260928/study.py), phases `prepare`, `run`, `render`, avec un dossier de travail et un chemin HTML neufs. Les exécutions retenues sont sous `mrp_dated_receipts_20260928/final`. Une première tentative et un premier manifeste de tests ont été refusés car les fichiers de carte changeaient encore ; ils ne constituent pas une preuve réussie. Les quatre calculs et les tests ont été relancés après gel des sources.

Les **55 tests ciblés en mémoire** ont réussi. Les quatre simulations passent les invariants physiques. L'[oracle indépendant sur les ordres, réceptions et cibles](../../artifacts/testing/mrp_dated_receipts_20260928/validation/independent_csv.json) effectue **3 037 989 vérifications** sans anomalie ; le [rapprochement Excel/CSV vers les données du panneau](../../artifacts/testing/mrp_dated_receipts_20260928/payload_result.json) ajoute **443 195 contrôles numériques hérités et 1 308 315 contrôles du nouveau contrat**, sans échec. Le seul contrôle de version de schéma v3 est explicitement remplacé par le contrôle v4 ; les équations de l'oracle précédent restent inchangées. Aucun test d'altération, de disparition, de droits ou de dates de fichiers n'a été utilisé.

Le navigateur a réussi **6 contrôles ciblés** couvrant 33 couples, 471 095 points et 1 933 séries, avec 330 positions SVG échantillonnées, ainsi que **9 contrôles standards**. Les échéances, exports, absences de données, conversions, tableaux avant/après commande et deux suivis de lots sont vérifiés ; aucune erreur JavaScript ni requête réseau n'a été observée pendant le parcours ciblé. Les tableaux larges utilisent un défilement horizontal. Ce parcours ne couvre pas toutes les interactions ni chaque pixel.

Les liens des manifestes finaux et la couverture navigateur sont réunis dans le [bilan de livraison](../../artifacts/testing/mrp_dated_receipts_20260928/manifest.json). Ces preuves valident l'exécution et les calculs annoncés ; elles **ne certifient pas la calibration industrielle**, comme le montrent les écarts ci-dessus.

## 17. Corrections fondées sur les plans sources

### Ce que les données permettent réellement de corriger

**Quantité standard et quantité obligatoire étaient confondues.** La colonne G de FIA s'appelle « Quantité standard de commande ». Pour 338929, `268091.xlsx/FIA!G20` contient 5 000 UN ; pour 333362, `268967.xlsx/FIA!G4` contient 5 000 UN. Ce champ ne définit ni un minimum, ni un multiple obligatoire, ni une quantité maximale à expédier par jour.

La contradiction est vérifiable dans les 52 versions du MRP : seulement **2 des 1 082 H positifs de 338929** sont multiples de 5 000 ; pour 333362, **437 des 741 H positifs ne sont pas multiples de 5 000**. Exemples : H712 = 144 631 étuis ; H648 = 124 000 unités de 333362, H657 = 54 000 et H658 = 221 000. Ces comptes décrivent des lignes de projections successives, pas autant de réceptions industrielles distinctes.

Les variantes corrigées retirent donc le multiple et l'étalement artificiel en tranches de 5 000 pour ces deux couples. Les contraintes physiques de stock, les unités entières et les contraintes de transport effectivement renseignées restent actives. Cela ne crée pas une donnée de palettisation ou un minimum de livraison absent des fichiers.

**La capacité maximale ne constitue pas un besoin permanent.** Le moteur pouvait maintenir des besoins amont à partir de capacité × nomenclature même si la demande prévue était inférieure. Le mode corrigé propage la prévision dans les nomenclatures et entre sites. La capacité continue de limiter l'exécution ; elle ne devient plus un plancher de demande. Une prévision multiniveau et un programme de fabrication déjà développé ne sont pas développés une deuxième fois.

**693055 ne possède pas de processus de fabrication représenté à Gaillac.** Sa nomenclature aval est connue (`268091.xlsx/BOM`, ligne 12 : 406 G pour 1 000 PF), mais pas sa propre nomenclature ni sa capacité industrielle. Le repli historique utilisait un approvisionnement à quatre jours limité par deux jours de signal aval. Il ne s'agit pas d'une règle industrielle. Le nouveau classeur fournit pourtant un lot fixe de 600 000 G (`Taile de Lot!E5`) et le MRP indique un temps de réception de 28 jours à Gaillac. Les variantes corrigées utilisent ces données comme **frontière d'approvisionnement agrégée** : besoin prévu sur délai + revue, disponible et encours déduits, puis arrondi au lot fixe. Les réceptions gardent des lots séparés de 600 kg. La revue quotidienne est conservée comme convention du simulateur ; les 28 jours sont interprétés en jours calendaires, à confirmer. Le délai de transport vers Avène reste séparé à 70 jours. Aucune BOM ni capacité industrielle n'est inventée ; cette frontière ne peut pas simuler les contraintes de fabrication amont de ce composant.

### Règle de couverture et regroupements : vérification hors ajustement

Pour l'étui 338929, une règle de couverture des **trois semaines suivantes**, tenant compte des disponibilités J, reconstitue une part importante des projections. Le calcul autonome part d'un seul solde source au début de chaque segment puis utilise son propre solde ; il ne recopie pas H ou K à chaque semaine. Seuls les segments de semaines renseignées et les décisions au-delà du délai initial sont retenus.

Sur 722 semaines admissibles, **602 réceptions H et 644 soldes K sont retrouvés exactement**. La séparation chronologique donne 331/362 H exacts sur la première moitié des versions et 271/360 sur la seconde, soit **75,28 % sur la période de vérification**. La règle est informative, mais ne reproduit pas toutes les décisions. Elle ne justifie pas de remplacer arbitrairement tous les délais de sécurité par 21 jours.

Les écarts révèlent des regroupements : dans le premier plan, H719 = 289 232 au 13 avril 2025 puis H720 = 0 au 20 avril, au lieu de deux besoins de 144 616. Parmi 30 épisodes d'anticipation qui se résorbent, 29 se terminent pendant une semaine contenant un jour férié national. Cette association est compatible avec un calendrier industriel ; elle ne démontre pas les jours de fermeture de l'entreprise. Le calendrier lundi–vendredi confirmé par l'utilisateur n'est donc pas remplacé automatiquement. Sources calendaires : [API publique 2025](https://calendrier.api.gouv.fr/jours-feries/metropole/2025.json), [Service Public 2026](https://www.service-public.gouv.fr/particuliers/actualites/A18558).

Preuves : [analyse des réceptions et des cellules](../../artifacts/testing/mrp_source_driven_20260928/source_supply/analysis.json), [projection autonome](../../artifacts/testing/mrp_source_driven_20260928/source_supply/autonomous_projection.json), [association au calendrier](../../artifacts/testing/mrp_source_driven_20260928/source_supply/calendar_association.json).

### Prévisions industrielles : utilisation datée, sans copier les résultats

Une variante séparée utilise les **5 178 besoins futurs I des deux produits finis au dépôt**. À chaque décision, seule la dernière version déjà connue est utilisée. Les données H ne deviennent pas des commandes simulées, et K ne remplace pas le stock du modèle. Une semaine absente conserve la prévision nominale ; un zéro explicitement renseigné reste zéro. La demande physique demeure celle de `demand_PF.xlsx`.

Les 104 lignes de semaine courante sont conservées comme preuves mais exclues des nouveaux besoins prévisionnels. Pour 268091, le besoin de la semaine augmente dans chacune des 51 transitions où il devient la semaine courante ; exemple : 73 218 dans le plan du 8 juin, puis 874 805 dans celui du 15 juin. Cela peut agréger des reliquats et ne décrit pas automatiquement de nouvelles ventes à créer chaque semaine. L'état industriel des reliquats n'est pas fourni. Pour les quatre années suivantes, les versions de 2025 sont répétées annuellement : c'est une convention de prolongation, pas quatre années de données industrielles.

### Comparer des stocks de même nature et des périmètres compatibles

La photo d'inventaire porte sur le total détenu. La contribution J à la semaine courante indique ce qui est déjà présent et disponible dans cette période du plan ; les J futurs correspondent à du stock déjà détenu, rendu utilisable plus tard. Comparer directement tout l'inventaire au seul disponible simulé peut donc doubler artificiellement un écart.

Sur les 52 versions, 773474 à Gaillac représente en moyenne **25 169 kg dans l'inventaire**, mais **12 615 kg de J courant** et autant en J futur. Pour 021081, l'inventaire moyen atteint **1 558 863 kg**, contre **447 692 kg de J courant** et **1 111 474 kg en J futur**. Les écarts de date et de périmètre empêchent de supposer une égalité parfaite. Les comparaisons doivent présenter les deux références séparément.

Autre limite démontrée : sur les semaines communes d'une même version, le besoin de 773474 à Gien vaut en médiane **2,96 fois** celui déduit du seul PF268967 par la nomenclature disponible ; à Gaillac, le ratio est 3,53. Ce constat signale des périmètres ou programmes différents. **Il ne constitue pas un facteur de division des stocks.** Les sources ne sont pas redimensionnées pour faire coïncider les courbes. [Oracle nomenclatures et périmètres](../../artifacts/testing/mrp_source_driven_20260928/validation/perimeter-oracle.json).

### Vérification : le premier calcul corrigé a été refusé

Les premiers recalculs sur cinq ans ont révélé des ruptures tardives et douze erreurs de généalogie, malgré la réussite des anciens invariants généraux. Un résidu numérique de fabrication presque nul pouvait prélever une unité de packaging par jour, alors que l'encours n'enregistrait plus de travail. Les contrôles ont retrouvé jusqu'à 78 unités consommées sans lien vers le lot fini. Il s'agit d'un défaut du moteur, pas d'un rebut industriel à ajouter au modèle.

Le moteur neutralise désormais ces résidus avant prélèvement. La qualification rapproche exactement les consommations et la généalogie des campagnes closes, y compris un parent totalement absent des liens. Elle conserve la possibilité d'un encours dans une campagne ouverte et refuse explicitement toute erreur du rapport de parcours des lots. Les preuves précédentes avec ces erreurs restent des échecs ; les succès arithmétiques ou navigateur ne les annulent pas.

### Résultats des corrections après recalcul sur cinq ans

La [carte corrigée](../../resultats/mrp_source_driven_20260928/carte_corrigee.html), bouton **Comparaisons 2025**, permet de superposer quatre calculs : nominal conservé, référence avec paramètres sources et aléas appariés, besoins corrigés avec prévision historique, puis besoins corrigés avec prévisions MRP sources. Les deux derniers utilisent également la frontière 693055 décrite ci-dessus. Les autres onglets et les deux suivis de lots restent ceux du nominal historique ; le panneau ne prétend pas afficher la nouvelle généalogie de chaque variante.

L'écart moyen absolu ci-dessous est calculé sur **52 photos hebdomadaires de 2025**, rapprochées de la clôture simulée précédente, hors photo d'ouverture. Il compare le disponible simulé à la photo totale : **les différences de périmètre précédemment décrites restent applicables**. Ces chiffres ne doivent pas être lus comme une mesure pure de justesse du MRP.

| Article / site | Unité | Référence avec règles sources | Besoins corrigés | Avec prévisions MRP sources |
|---|---|---:|---:|---:|
| 338929 / Avène | UN | 1 317 169 | **229 088** | 794 177 |
| 333362 / Gien | UN | 792 825 | 278 173 | **207 858** |
| 773474 / Gaillac | kg | 21 108 | **13 046** | 15 815 |
| 021081 / Gaillac | kg | **322 608** | 416 299 | 416 299 |
| 268091 / dépôt | UN | 519 057 | 521 550 | **397 256** |
| 268967 / dépôt | UN | 291 701 | **138 669** | 261 774 |

L'étui 338929 passe d'un stock moyen de 1 735 773 à **530 124 UN** aux dates comparées, contre **521 515 UN** dans les photos : son écart absolu moyen diminue de **82,6 %**. Une moyenne proche ne signifie pas que chaque semaine correspond : l'écart hebdomadaire moyen reste de 229 088 UN. Les prévisions industrielles ne sont **pas systématiquement meilleures** : elles améliorent le PF268091, mais augmentent notamment le stock et l'écart du PF268967 et de l'étui par rapport à la variante corrigée à prévision historique.

Contre-vérification de périmètre : en utilisant **J courant**, l'écart moyen de 773474/Gaillac est de 9 662 kg pour la référence, 7 015 kg pour les besoins corrigés et 9 785 kg avec prévisions sources. Le nominal historique est à 9 600 kg. Pour 268967/dépôt, ces écarts sont respectivement 355 357, 165 212 et 374 309 UN, contre **82 451 UN pour le nominal historique**. La nouvelle variante n'est donc pas meilleure que toutes les références sur tous les indicateurs.

Sur cinq ans, les deux variantes servent finalement presque 100 % de la demande des deux PF. Les réapprovisionnements de 693055 représentent respectivement **7 et 8 lots de 600 kg**, reçus chacun après 28 jours ; les commandes de repli à quatre jours disparaissent, ainsi que les blocages de fabrication liés à ce composant. Les douze erreurs de généalogie de la première exécution ont disparu.

**Le service cumulé ne certifie pas la ponctualité.** Avec prévision historique, 268091 connaît encore 22 jours de retard client après le démarrage, jusqu'à 160 544 UN en attente. Avec prévisions sources, aucun stock de commandes clients en attente d'au moins 100 UN n'est relevé après J10. Pour 333362, les blocages de fabrication concernent 56 campagnes dans la première variante et 19 dans la seconde, représentant 982 et 224 journées contraintes. Il ne s'agit pas d'autant d'incidents indépendants. Les stocks au dépôt peuvent protéger les clients pendant ces retards de fabrication.

**Le traitement des besoins par date reste incomplet.** À J1824 dans la variante corrigée à prévision historique, le stock 333362 est nul, mais 272 027 UN de réceptions encore attendues couvrent comptablement la cible : le besoin net est inférieur à une unité. Les 33 réceptions arrivent entre J1828 et J1930. Supprimer le découpage par 5 000 ne résout pas cette anticipation. Exclure simplement ces réceptions et recommander toute leur quantité doublerait l'approvisionnement ; il faut distinguer nouvelles quantités à commander et ordres existants à replanifier, avec leurs possibilités physiques de modification. Le précédent filtre `within_cover` reste désactivé. **Aucune des deux variantes n'est présentée comme une reproduction complète du MRP industriel.**

L'état disponible/indisponible de 021081, le périmètre multiproduit de certaines matières, le calendrier industriel des regroupements et l'état physique des OF initiaux demeurent des limites précises. Les coûts de la frontière 693055 utilisent la convention économique existante faute de coût industriel renseigné : **36 000 € par lot de 600 kg** avec les paramètres courants. Cette valeur n'est pas un prix industriel vérifié et ne permet pas de conclure à un gain économique.

### Preuves finales et reproduction

Reproduction : [recette](../../artifacts/testing/mrp_source_driven_20260928/study.py), [commandes et conventions exactes](../../artifacts/testing/mrp_source_driven_20260928/final_v2/plan.json). Exécuter `prepare`, `run`, puis `render` avec un nouveau `--workdir` et un nouveau `--html` ; les sorties existantes sont protégées contre l'écrasement. Les quatre calculs de 1 825 jours ont duré respectivement 40,5, 52,8, 47,4 et 47,7 secondes dans cette session, contrôles et rendu exclus ; ce relevé ne constitue pas un benchmark comparatif de performance.

Les **33 CSV du nominal sont identiques octet par octet** à la référence conservée. **74 tests ciblés en mémoire** et les invariants des quatre calculs passent sur le code stabilisé. L'oracle indépendant effectue **1 083 945 vérifications sans échec** : prévisions connues à la décision, demande physique conservée, unités entières, propagation des nomenclatures, quantités standards non contraignantes, ordres et réceptions 693055, coûts conventionnels, et rapprochement des stocks. Le contenu numérique de la carte passe en plus **443 195 vérifications existantes et 1 308 315 vérifications du contrat de courbes**, sans anomalie.

Le navigateur hors ligne vérifie les **33 couples, cinq vues et trois conventions hebdomadaires**, 156 choix de version, les exports et l'accès aux deux suivis. **4 174 207 points** sont rapprochés du contenu numérique ; **50 623 positions SVG** sont échantillonnées. Les 31 conventions visibles correspondent aux données embarquées. Les neuf contrôles standards passent aussi, sans erreur JavaScript ni requête réseau pendant les parcours. Les captures ont été examinées ; cet accès aux suivis ne certifie pas chaque lot historique.

Liens : [identité du nominal](../../artifacts/testing/mrp_source_driven_20260928/final_v2/identity.json), [contre-vérification indépendante](../../artifacts/testing/mrp_source_driven_20260928/validation/independent-csv-final-v2.json), [données et courbes](../../artifacts/testing/mrp_source_driven_20260928/payload_result_final.json), [navigateur final](../../artifacts/testing/mrp_source_driven_20260928/ui_v2/review-db1d8742ea9646a3a2315927ec731e3e/manifest.json), [bilan des manifestes](../../artifacts/testing/mrp_source_driven_20260928/manifest.json). Ces contrôles ne certifient pas une calibration industrielle complète. Les premières preuves invalidées ou en échec sont conservées séparément ; elles ne sont pas utilisées comme qualification finale. Aucun test d'altération de fichiers, de dates ou de protections système n'a été effectué.

## 18. Rapprochement du carnet, des plans et des photos de stock

**Les trois fichiers sont complémentaires et ont été croisés par article, division, unité et date.** `Extract_En_cours.xlsx` décrit 104 lignes engagées au démarrage (53 AVICDE, 29 ECHCDE, 22 O.Proc). Le fichier Flow MRP conserve 52 versions des projections, soit 53 398 lignes et 33 couples article/site. Le fichier d'inventaire donne les photos de stock total. Ces photos constituent des observations ; un ordre et une projection restent des prévisions tant que leur exécution n'est pas identifiée.

### Ce qui correspond entre les fichiers

Pour les achats du carnet, **les 49 regroupements article/site/semaine disposant d'une ligne dans le premier plan MRP donnent exactement les mêmes quantités**, en utilisant la date G de livraison et des semaines dimanche–samedi. Quinze autres regroupements n'ont pas de semaine correspondante et restent manquants, pas nuls. Avec la date I de disponibilité, on ne retrouve que cinq égalités, contre 36 différences et 26 semaines absentes. Ce résultat étaye le rattachement des H du premier plan aux livraisons prévues, sans prouver leurs dates réelles d'exécution.

Deux lignes du carnet apparemment identiques ne doivent pas être supprimées : **lignes 63 et 66**, 049371/Avène, 1 800 kg chacune. Avec la ligne 67, elles donnent les **5 400 kg de H445** du MRP. Sans identifiant d'ordre, supprimer l'une ferait perdre une quantité cohérente avec le plan.

Les O.Proc ne sont pas tous rapprochables de la même façon :

- **693055/Gaillac, ligne 103** : 600 000 G, livraison G le 27 janvier, disponibilité I le 25 février. H788 du premier plan contient bien 600 000 G dans la semaine du 26 janvier.
- **773474/Gaillac, ligne 105** : 3 200 000 G, G le 24 janvier, I le 3 mars. H969 contient 9 600 000 G dans la semaine du 19 janvier : le plan agrège trois fois le volume de cet ordre, sans permettre d'identifier les trois ordres.
- Les **20 O.Proc de 268091/Avène**, lignes 72–91, n'ont pas de couple 268091/1810 dans le Flow MRP. Le plan du produit au dépôt ne constitue pas une correspondance directe avec l'usine.

L'analyse rapproche également **1 614 intervalles entre photos** et les ordres initiaux attendus sur ces intervalles. Pour 773474/Gaillac, les photos du 20 et du 27 janvier passent de 6 400 à 9 600 kg : +3 200 kg est compatible avec la livraison G du 24 janvier. Pour 693055/Gaillac, le stock augmente de 600 kg entre le 24 février et le 3 mars, près de la date I du 25 février, tandis qu'il diminuait la semaine du 27 janvier. Ces exemples interdisent d'assimiler automatiquement toute variation à une réception identifiée. Les sorties, transferts et ajustements peuvent se compenser ; le résidu n'est pas déclaré « consommation réelle ».

Sur les 104 lignes, **99 délais G→I correspondent à lundi–vendredi hors jours fériés nationaux**, contre 70 avec seulement lundi–vendredi et trois en jours calendaires. Les cinq exceptions concernent 021081/Gaillac, avec neuf jours ouvrés supplémentaires en traversant août. Une fermeture est plausible, pas démontrée. Cette constatation sur le carnet ne modifie pas le calendrier de sécurité confirmé par l'utilisateur.

Preuves : [correspondances anciennes/nouvelles et cellules](../../artifacts/testing/mrp_alignment_20260928/source_crosswalk/crosswalk_v2.json), [104 ordres et contexte des stocks](../../artifacts/testing/mrp_alignment_20260928/source_crosswalk/orders_stocks.json), [tableau CSV des rapprochements](../../artifacts/testing/mrp_alignment_20260928/source_crosswalk/orders_stocks.csv).

### Anciennes et nouvelles données : différences exactes

L'ancien inventaire d'ouverture contient 32 couples ; le nouveau en contient 31 au 1er janvier. **344135/Gien manque à cette date** dans le nouveau fichier, même si l'ancien stock valait zéro. Parmi les 31 couples communs, **27 quantités sont identiques**. Les quatre différences nouveau−ancien sont : +0,00328125 kg pour 002612/Avène ; −0,172 G pour 038005/Gien ; +1 UN pour 042342/Gien ; +0,000023437 G pour 055703/Avène. Elles ne justifient pas les grands écarts ultérieurs des simulations.

Les règles, en revanche, présentent des différences significatives : minimum de fabrication 268091 de **14 400 à 28 800 UN** ; sécurité du PF268967 au dépôt de **25 à 60 jours ouvrés** ; 426331/Avène de **7 à 10 jours**. La nouvelle source affiche « 00 » pour la sécurité de 268091 au dépôt, contre 20 auparavant : les simulations conservent les **20 jours protégés**, sans essai arbitraire à zéro. Les fichiers ne donnent pas les dates d'entrée en vigueur de ces différences. Pour les temps de réception, neuf couples ancien/nouveau sont identiques et huit diffèrent, notamment 338929 : 4→6 ; 333362 : 4→5 ; 693055/Gaillac : 21→28 ; 773474/Gaillac : 26→33.

Dans le premier plan du 5 janvier, la somme des contributions J, courantes et futures, égale la photo du 6 janvier pour **22 des 31 couples comparables**. Les neuf différences restantes sont conservées : ni égalité universelle supposée, ni remplacement automatique du stock simulé chaque semaine.

Les recettes anciennes ont aussi été recoupées : **46 des 48 liens de nomenclature comparés concordent**, deux sont absents du seul `Data_poc.xlsx` mais présents dans les autres classeurs. Aucune fraction de stock multiproduit n'est déduite arbitrairement de ces rapprochements.

Le 6 janvier, **002612/Gaillac est bien à 1 250 kg**, cellule `Stocks!E946` ; F946 contient la valeur financière 1 575, pas une quantité. La devise n'est pas renseignée dans l'en-tête. La carte historique `02_carte_lots_recente.html` contient encore son ancien extrait à 1 250 414 ; les cartes de comparaison plus récentes et la livraison ci-dessous lisent 1 250. L'index signale cette limite historique.

### Défauts du modèle distingués des incertitudes industrielles

**Un défaut est corrigé dans les variantes, avec nominal conservé.** Le carnet initial réduisait durablement l'horizon de couverture, en plus d'être déduit comme quantités déjà commandées. Pour 333362, six ordres totalisant 629 000 UN étaient reçus entre J58 et J91 ; pourtant ils retranchaient encore 66 jours de couverture à J1824. Le calcul corrigé garde les 125 jours d'horizon, au lieu de 59. Pour 338929, il conserve 92 jours au lieu de 78. Les commandes initiales restent comptées une seule fois en quantités. Les stocks de sécurité, délais physiques et nomenclatures ne sont pas modifiés par cette correction.

**Deux autres défauts de représentation sont localisés mais pas corrigés dans cette livraison :**

- Les dates G et I sont conservées dans les entrées, mais le moteur ne matérialise actuellement l'arrivée qu'à I. Il classe donc encore comme transit les quantités potentiellement présentes entre G et I. Une correction devra passer le même lot du transit au stock bloqué à G, puis au disponible à I, sans seconde réception ni coût. Ces dates restent celles du scénario planifié, pas des observations industrielles.
- Les graphes courants ne séparent pas le stock initial disponible du stock déjà détenu mais disponible plus tard. Pour 021081, le plan du 5 janvier indique **752 312 kg disponibles et 379 880 kg futurs**, soit 1 132 192 kg, égal à la photo du 6 janvier. Le stock initial du 1er janvier est d'une autre date : imposer rétroactivement cette répartition nécessiterait une hypothèse explicite. Les 379 880 kg ne doivent jamais être créés comme un nouvel achat.

Le même délai FIA est en outre utilisé à deux étages, pour l'approvisionnement du fournisseur puis pour son transport vers l'usine. Exemple vérifié du registre précédent pour 338929 : commande amont J0, réception fournisseur J42, expédition immédiate, réception usine J112. La source donne un délai prévisionnel de livraison de 42 jours ; elle ne justifie pas à elle seule cette décomposition et une durée totale de 112 jours. Une distribution Erlang et ce découpage appartiennent au modèle, pas au classeur. [Audit de l'initialisation et états physiques](../../artifacts/testing/mrp_alignment_20260928/engine/initial_receipt_states.json).

### Effet mesuré du correctif et statut de la reproduction

Les quatre simulations de **1 825 jours** ont été relancées. Les **33 CSV du nominal restent identiques**. Les deux variantes corrigées sont comparées à leurs résultats précédents, avec les mêmes entrées et conventions. Écart absolu moyen aux 52 photos de 2025, disponible simulé contre total photographié, clôture précédente :

| Article/site | Unité | Prévision historique avant → après | Prévisions MRP sources avant → après |
|---|---|---:|---:|
| 338929/Avène | UN | 229 088 → 251 787 | 794 177 → 971 633 |
| 333362/Gien | UN | 278 173 → 243 237 | 207 858 → 466 252 |
| 773474/Gaillac | kg | 13 046 → 13 046 | 15 815 → 16 369 |
| 021081/Gaillac | kg | 416 299 → 416 299 | 416 299 → 409 697 |
| 268091/dépôt | UN | 521 550 → 521 550 | 397 256 → 397 256 |
| 268967/dépôt | UN | 138 669 → 160 044 | 261 774 → 367 501 |

**Corriger le double crédit n'améliore pas toutes les courbes.** Le défaut pouvait compenser d'autres écarts de demande, délai ou disponibilité. Ce résultat ne justifie ni de le conserver dans le mode corrigé, ni d'adopter cette variante comme calibration industrielle réussie. La [nouvelle carte de comparaison](../../resultats/mrp_alignment_20260928/carte.html) expose ces calculs ; les autres onglets et les deux suivis restent ceux du nominal historique. [Détail avant/après](../../artifacts/testing/mrp_alignment_20260928/stock_comparison.json).

Une étude séparée évalue des règles de couverture sur les plans, avec sélection sur la première moitié des versions puis vérification sur la seconde. **18 036 points** ont été recalculés et contre-vérifiés indépendamment. H et K ne sont pas recopiés à chaque semaine ; un K source amorce chaque segment contigu, éventuellement situé plus loin dans le plan. Il s'agit donc d'une reproduction conditionnelle par segments, pas d'un MRP complet initialisé une seule fois. Les cibles calendaires se recouvrent entre versions ; la seconde moitié n'est pas constituée d'observations entièrement indépendantes. La contrainte de lancement physique des ordres n'est pas modélisée dans ce diagnostic.

Pour 338929, le candidat trois semaines retrouve **167 des 225 H positifs** de vérification ; l'erreur absolue sur H rapportée au volume source est de **16,32 %**. Pour 268091/dépôt, un candidat fondé sur la valeur source « 00 », uniquement dans cette analyse de fichier et jamais appliqué au nominal, donne une erreur H de 7,13 % mais un écart moyen de K de **267 035 UN**. Reproduire assez bien une réception sans reproduire le solde ne valide pas la règle. Beaucoup d'autres articles restent nettement moins bien reproduits ; aucune sélection n'est intégrée automatiquement au moteur. [Résultats par article](../../artifacts/testing/mrp_alignment_20260928/rule_replay_summary.csv).

La poursuite doit donc porter sur **l'état physique et la disponibilité**, **un délai fournisseur non dupliqué**, puis **l'affectation des besoins et ordres par date** : une commande ferme trop tardive doit produire un retard explicite, pas disparaître du calcul ou être rachetée une seconde fois. Les trois sources fournissent les contraintes de rapprochement de cette étape. Elles ne rendent pas un solde hebdomadaire équivalent à un journal complet des mouvements exécutés.

Vérifications réalisées sur le code stabilisé : **91 tests ciblés en mémoire**, invariants des quatre simulations, contre-calcul indépendant de la couverture sur les cinq ans, unités physiques et généalogie, rapprochement des données et courbes. Les sources industrielles n'ont pas été modifiées. Les durées moteur relevées sont 42,0, 37,6, 38,1 et 41,9 secondes, hors contrôles et rendu ; ce n'est pas un benchmark. Aucun test d'altération de fichiers ou de protection système. [Manifestes et limites de la livraison](../../artifacts/testing/mrp_alignment_20260928/manifest.json).

## 19. Livraison, disponibilité et achats par échéance

### Règles extraites et limites de leur identification

Le [catalogue consolidé](../../artifacts/testing/mrp_execution_20260928/rules/catalogue.json) rapproche **157 champs sur 41 couples article/site**, avec les cellules anciennes et nouvelles, les unités, les différences et les décisions utilisateur. Il distingue quatre états : donnée extraite, propriété démontrée dans les chiffres, hypothèse candidate et information absente. Neuf classeurs sont suivis par empreinte. Les comparaisons Flow MRP portent sur 33 couples ; les populations ne sont donc pas interchangeables.

Le [premier plan du 5 janvier](../../artifacts/testing/mrp_execution_20260928/rules/initial_plan.json) sépare J courant et J futur, besoins I, engagements du carnet et références H/K. **J futur représente du stock déjà présent.** Il ne devient jamais un achat. Pour 021081/Gaillac, 752 312 kg disponibles et 379 880 kg disponibles plus tard composent les 1 132 192 kg détenus. Cette répartition est vérifiée au 5 janvier ; elle n'est pas imposée rétrospectivement à l'ouverture du 1er janvier. Les mouvements détaillés des quatre jours intermédiaires manquent.

Les paramètres explicites sont extraits ; **toutes les règles de décision du MRP industriel ne sont pas identifiées**. Restent notamment le traitement des reliquats, le statut matière des O.Proc, les calendriers de réception, le gel des commandes et le périmètre multiproduit. Les stocks et résultats H/K demeurent des références à retrouver, pas des valeurs injectées chaque semaine pour forcer l'accord.

**Une règle présente dans le catalogue n'est pas nécessairement appliquée intégralement par le nouveau contrôleur.** Les sécurités des sorties de fabrication, les programmes exécutés et les transferts de PF vers le dépôt restent en partie pilotés par le moteur historique. La séparation J courant/J futur du 5 janvier reste un rapprochement à cette date, pas un nouvel état d'ouverture au 1er janvier. Le sens exact du délai de sécurité dans l'ERP, les horizons fermes et les règles de rééchelonnement restent à déterminer. Le calendrier de sécurité confirmé et les valeurs sources ne sont pas abaissés pour améliorer artificiellement les écarts.

### Ce qui change dans le moteur expérimental

Deux modes optionnels s'ajoutent au mode historique. Le moteur physique reste celui de la dynamique des systèmes, avec dépendance à l'état, capacités, nomenclatures et lots. Les paramètres de sécurité du scénario sont préservés : lundi–vendredi, dépôt à 100 %, et 20 jours protégés pour 268091 au dépôt. `tau_process` conserve sa convention de planification.

- **`availability`** : chaque achat initial arrive physiquement à G. Le même lot est bloqué jusqu'à I, puis devient disponible. Cette libération ne crée ni une deuxième livraison ni un nouveau lot. Le stock physique inclut disponible, bloqué et réservé avant départ. La détention du stock bloqué entre dans le coût de stockage selon les taux existants ; les coûts d'achat du carnet initial conservent leur convention historique.
- **`dated`** : un calcul indépendant, [mrp_planning.py](../../simulation/engine/mrp_planning.py), affecte le stock et les engagements aux besoins datés avant de proposer des achats supplémentaires. Un engagement en retard reste attendu et son retard est affiché : il n'est pas automatiquement racheté. Les minimums, multiples et maximums dimensionnent les propositions ; les quantités physiques UN restent entières.
- Le calcul du réseau crédite les fabrications en cours une seule fois et propage les nouveaux besoins par les nomenclatures. La protection de stock est identifiée séparément : **ce n'est pas une consommation physique**. Les achats et transferts de composants sont déclenchés aux dates de lancement, sous contraintes. Les programmes de fabrication et les flux de produits finis vers le dépôt conservent leur pilotage physique antérieur ; les nouvelles propositions les concernant restent des projections.
- Une protection complémentaire non couverte est demandée à la date du calcul augmentée du délai de planification : la commande correspondante peut donc être passée immédiatement. Sa quantité reste la cible diminuée des besoins bruts déjà comptés dans l'horizon, puis le stock et les engagements sont déduits. L'ancienne échéance recalculée à « aujourd'hui + couverture » pouvait repousser indéfiniment le lancement lorsque la couverture dépassait le délai. Cette convention de reconstitution corrige ce report ; elle ne prouve pas une nouvelle règle de stock minimum industriel.
- Pour les nouveaux achats externes concernés, **le délai fournisseur FIA intervient une fois**, de la commande à la livraison. Le temps de réception E s'ajoute ensuite jusqu'à la disponibilité. Son calendrier lundi–vendredi est une convention candidate, distincte du calendrier de sécurité confirmé ; les jours fériés et fermetures ne sont pas inventés. La fabrication du fournisseur et le départ du camion restent inconnus : la livraison est représentée à cette frontière agrégée, avec identité fournisseur, sans trajet détaillé fabriqué.

La fin prévue d'une campagne en cours est également bornée par la disponibilité des composants affectés à son travail restant. Cette contrainte remonte l'amont vers l'aval, puis recalcule le solde et le retard projetés. Un garde-fou exige que le changement des seules dates fermes conserve les mêmes propositions d'achats. C'est une condition nécessaire de disponibilité, **pas un ordonnancement complet sous capacité** ; aucune durée physique supplémentaire n'est ajoutée à `tau_process`.

Les dates G/I du carnet sont des dates **planifiées dans la source**, ensuite exécutées dans le modèle. Elles ne prouvent pas que la livraison industrielle a eu lieu ce jour-là. Les O.Proc ne sont pas reclassés arbitrairement en fabrications déjà consommées.

Le délai de référence sert à planifier ; les délais tirés et la fiabilité des fournisseurs restent des hypothèses du scénario physique. La table des achats présente séparément délai source, délai tiré et temps de réception. Un décalage de livraison simulée ne doit donc pas être attribué automatiquement à une règle du MRP industriel. Une seule graine est comparée ici : cette passe n'est pas une campagne statistique de calibration.

### Comparaison et lecture de la carte

Ouvrir la [carte finale de cette étape](../../resultats/mrp_execution_20260928/carte_mrp.html), puis **Comparaisons 2025**. Le lien de l'index pointe vers cette version ; les essais précédents restent des références séparées.

Le protocole conserve quatre scénarios de 1 825 jours : nominal historique ; prévisions sources avec moteur précédent ; séparation livraison/disponibilité ; achats calculés par échéance. La comparaison industrielle concerne **2025 seulement**. Les quatre années suivantes prolongent les hypothèses de demande et de prévisions de 2025 ; elles ne constituent pas quatre années de données industrielles supplémentaires.

Le panneau de comparaison distingue disponible, bloqué, réservé et total physique. Il présente les dates G/I et les achats exécutés, puis les besoins, engagements, propositions et retards de planification. Une table hebdomadaire permet de comparer les projections à une même date de calcul. Son solde disponible exclut la réserve de planification des consommations et utilise les disponibilités à I : il n'est pas automatiquement équivalent au solde K industriel. La dernière semaine incomplète masque H/K. Le calcul simulé intervient **après production et service client, avant les achats, transferts et expéditions restants du jour** ; son stock de départ peut différer de la clôture quotidienne. L'instant exact de l'export ERP reste inconnu.

Les autres onglets et les deux suivis de lots de la carte conservée restent ceux du nominal historique. Les nouveaux scénarios sont explicitement limités au panneau de comparaison. Le mode daté expérimental refuse les combinaisons non qualifiées avec incidents, préchauffage ou redimensionnement d'état.

### Résultats : amélioration partielle, variante non adoptée comme nominal

Les quatre simulations sont terminées et passent les invariants. **Les 33 CSV du nominal sont identiques à la référence conservée**, ainsi que les 33 CSV de la référence avec prévisions sources à leur précédent calcul. La variante disponibilité préserve les stocks disponibles, les productions, les commandes et la demande de cette référence ; elle ajoute la présence physique et les coûts de détention du stock entre G et I.

La comparaison principale ci-dessous oppose **réceptions datées** et **achats par échéance**, deux modes qui décrivent tous deux disponible + réservé + bloqué. Erreur absolue moyenne aux 52 photos de 2025, avec la clôture simulée de la veille ; unités propres à chaque ligne :

| Article/site | Unité | Réceptions datées | Achats par échéance | Évolution de l'erreur |
|---|---|---:|---:|---:|
| 338929/Avène | UN | 970 525 | 963 646 | −0,7 % |
| 333362/Gien | UN | 464 054 | 366 070 | −21,1 % |
| 773474/Gaillac | kg | 16 369 | 16 369 | 0 % |
| 021081/Gaillac | kg | 689 712 | 689 712 | 0 % |
| 268091/dépôt | UN | 397 256 | 397 256 | 0 % |
| 268967/dépôt | UN | 367 501 | 428 322 | +16,5 % |

Sur les **29 couples comparables**, douze erreurs diminuent, douze augmentent et cinq restent identiques. Les couvertures diffèrent : 344135/Gien ne dispose que de **trois photos**, et 001848/Gien garde un périmètre partiel. Quatre couples sources sont exclus faute de séries comparables. L'erreur de 042342/Gien diminue de 56 566 845 à 52 304 163 UN. En revanche, 693055/Gaillac passe de 862,5 à 1 081,7 kg et 338928/Avène de 345 197 à 667 176 UN. Ces chiffres ne sont pas additionnés entre unités différentes.

Une baisse d'erreur ne suffit pas à établir un bon niveau de stock : pour 338929, le stock physique moyen source vaut 521 515 UN, contre **1 413 142 UN** dans le nouveau mode. Pour 333362, les moyennes sont 322 436 et 647 460 UN ; l'erreur hebdomadaire reste de 366 070 UN. La protection corrigée peut rétablir la fabrication tout en créant trop de stock par rapport aux sources. **La moyenne et la trajectoire doivent être vérifiées séparément.** [Tous les écarts, les deux alignements temporels et les volumes d'achats](../../artifacts/testing/mrp_execution_20260928/impact_v6.json).

Sur cinq ans, les volumes clients servis et les indicateurs de reliquat retrouvent ceux du mode disponibilité. Pour 268967, le retard supplémentaire J968–J974 de l'essai intermédiaire disparaît ; l'accumulation des reliquats revient de 292 995,9 à **8 814,9 UN·jours**. Les reliquats supérieurs à une unité sont limités au démarrage dans ce scénario. Les résidus fractionnaires de prévision restent distingués des mouvements physiques entiers. Un ratio cumulé proche de 100 % n'est toujours ni un service industriel à l'heure ni une validation de l'ERP.

La correction de réserve fait passer les jours de contrainte liés à **344135 en 2025 de 246 à zéro**, entre les deux essais datés. Elle engage notamment 480 000 UN à J0, disponibles J47, et 120 000 à J4, disponibles J20. Ces quantités sont présentes avant le lancement de fabrication J74. L'achat J74 garde le même délai défavorable de 70 jours, avec disponibilité J148 : c'est la protection reconstituée qui évite la rupture, pas une réduction de ce délai. Les capacités configurées ne sont pas augmentées. La fabrication 2025 revient aux volumes du témoin : 1 940 400 PF268967 et 1 900 800 PF268091. Pour 338928, l'achat préventif fait au contraire monter le stock moyen et dégrade l'accord aux photos. [Causalité, bilans et comparaisons des deux essais](../../artifacts/testing/mrp_execution_20260928/engine/impact_v6_diagnostic.json).

**Les quantités et dates MRP ne sont pas encore reproduites.** Sur les 33 couples, l'écart entre H de la semaine courante et les réceptions physiques simulées diminue dans un cas, augmente dans six et reste identique dans 26. H décrit une réception projetée industriellement, pas son exécution observée. La comparaison des plans à même version, entre les deux essais datés, améliore K sur 18 couples mais le dégrade sur dix. L'écart entre H source et les disponibilités projetées du modèle diminue sur huit couples et augmente sur neuf ; **ce dernier calcul compare la livraison H à la disponibilité I, pas deux calendriers de livraison identiques**. Les témoins historiques n'exportent pas ces mêmes projections par version : aucun faux plan K de référence n'est créé. Les sources ne permettent pas d'apparier les identifiants et dates de création des commandes industrielles individuelles. [Métriques H/K, quantités et délais par couple](../../artifacts/testing/mrp_execution_20260928/engine/impact_v6_diagnostic.json).

**Cette variante reste une étude, sans remplacement du nominal.** Les matières partagées, le stock initial indisponible, le calendrier de réception et le couplage entre programmes prévisionnels et exécution physique restent déterminants. Le besoin utilisateur d'un an de couverture sur l'ensemble de la chaîne 268967 n'est pas transformé en un an à chaque nœud ; son périmètre et les coefficients restent à rapprocher avant calibration.

Durées d'exécution, CSV et contrôles internes du moteur compris, qualifications externes et navigateur exclus : nominal **72,2 s** ; prévisions sources **82,7 s** ; séparation G/I **83,2 s** ; achats par échéance **391,5 s**. Le calcul daté coûte ici 4,71 fois le mode disponibilité. Certaines qualifications indépendantes ont tourné en parallèle : ces durées sur une machine et une graine ne constituent pas un benchmark. Cette passe apporte une représentation et des preuves supplémentaires, **pas une accélération du nouveau mode**.

### Vérification des corrections

Les **314 tests ciblés** passent sur le code stabilisé, avec 135 sélecteurs explicitement relus. Ils couvrent les états physiques, les dates, les lots, les exports et le calcul daté, sans altération de fichiers de test. Les simulations de validation ont fait détecter puis corriger des colonnes manquantes dans l'export de généalogie, un arrondi intermédiaire des besoins fractionnaires, des retraits fournisseur fictifs dans un export de flux, une couverture incomplète du calendrier d'une paire introduite par le carnet initial, une date de fin de campagne antérieure à ses composants et le report permanent de la réserve. Le cas d'arrondi a été reproduit sur les valeurs réelles 001893/Avène ; les résidus restent désormais précis jusqu'au dimensionnement et la quantité publique couvre effectivement le besoin. La borne de campagne est vérifiée notamment sur le cas J905/J908/J971 de l'essai précédent et sur deux fabrications dépendantes. Les nouveaux tests imposent une commande préventive quand la protection manque, puis l'absence de double achat une fois la commande engagée ou reçue. Les contrôles de couverture et de bilan n'ont pas été supprimés. [Manifeste des tests](../../artifacts/testing/mrp_execution_20260928/validation/final_v6/tests-08ff7b1253724f0496a994698ff01a2b/manifest.json).

Pour 001848/Gien, l'unité du registre permet de lire les 7 000 kg du carnet sans reprendre les 7 000 000 G bruts comme des kg. L'absence d'état initial dans le graphe reste explicite ; une quantité simulée nulle avant réception ne devient pas une observation industrielle. La carte expose ce périmètre partiel et refuse des unités contradictoires.

Les **18 diagnostics datés** du planificateur pur ont été réexécutés après ses corrections numériques et contre-vérifiés par 1 570 contrôles indépendants : leurs résultats sont inchangés. Ils ne prouvent pas à eux seuls le contrôleur de réserve du réseau ni son raccord au calendrier de fabrication. Pour 021081, le carnet initial suffit à retrouver H/K sur les 25 premières semaines renseignées, sans nouvelle proposition ; cela ne valide pas le mécanisme du plancher de sécurité de 900 000 kg. Pour 338929, le premier segment contient 22 semaines : 2 156 564 UN de besoins, 411 600 UN de stock et engagements, et 1 744 964 UN à compléter. Les retards varient selon le calendrier candidat. Pour 333362, la première séquence ne contient qu'une semaine connue : elle ne permet pas d'identifier sa politique d'achat. [Diagnostic et preuve indépendante](../../artifacts/testing/mrp_execution_20260928/validation/revalidation/refresh.json).

Les quatre qualifications natives réussissent. L'[oracle indépendant des CSV](../../artifacts/testing/mrp_execution_20260928/validation/execution_csv_v6.json) effectue **3 088 981 contrôles**, sans échec : stocks, unités, dates G/I, identité des lots, coûts, commandes et projections. Les **100 CSV des trois scénarios témoins** sont identiques à leur calcul précédent ; la demande physique reste identique dans les quatre scénarios. Les flux du mode daté changent avec la correction de réserve et sont de nouveau contrôlés, sans imposer leur identité avec l'essai refusé.

L'oracle rapproche **1 412 échéances de réserve** avec la date du calcul augmentée du délai. Dans 54 instantanés, un manque doit être couvert immédiatement : les propositions le couvrent. Quinze instantanés ne comportent qu'une réserve déjà couverte et ne rachètent rien ; le cas d'une réserve seule non couverte est vérifié par les tests purs. La borne de disponibilité matière est contrôlée sur **trois campagnes distinctes**, présentes dans huit instantanés, avec 71 besoins de composants. Ces rapprochements d'échéances portent sur les instantanés hebdomadaires exportés de 2025 ; ils ne constituent pas une vérification exhaustive de chaque date prévisionnelle des cinq ans.

L'[oracle du contenu de la carte](../../artifacts/testing/mrp_execution_20260928/validation/payload_v6.json) rapproche les cellules sources et les CSV au contenu numérique affichable : **3 183 827 contrôles**, sans échec. Il vérifie notamment les 55 champs du diagnostic, les stocks, les unités et dates, les tableaux d'achats et les projections. Les empreintes restent stables pendant ces contrôles. Ces nombres décrivent la couverture des rapprochements ; **ils ne mesurent pas la fidélité du modèle à l'industrie**.

La [revue navigateur finale](../../artifacts/testing/mrp_execution_20260928/ui/review-3bea9003a4f94f3788fccc1eb98ba522/manifest.json) parcourt les 33 couples, cinq vues et trois calendriers, ainsi que 156 choix de version. Elle rapproche **5 441 678 points**, 51 163 cellules de projection et 8 226 cellules d'ordres ; 60 832 positions SVG sont échantillonnées. Les exports et l'accès aux deux suivis passent, sans erreur JavaScript ni requête réseau. Les neuf parcours natifs passent également sur le même HTML. Les captures ont été examinées : courbes et légendes sont lisibles, les tableaux les plus larges demandent un défilement horizontal. Cela ne certifie ni chaque pixel ni chaque lot historique.

Le [contrôle d'ensemble des preuves natives](../../artifacts/testing/mrp_execution_20260928/validation/final_v6/gate-a06cd7b873f748cbaefd099ade852ce1/manifest.json) confirme les empreintes du code, des entrées et des résultats. Le [manifeste de livraison](../../artifacts/testing/mrp_execution_20260928/manifest.json) réunit ces vérifications et les contre-calculs indépendants, avec **validation technique réussie, calibration industrielle non acquise et nominal non remplacé**.

### Reproduire cette étape

La [recette existante](../../artifacts/testing/mrp_execution_20260928/study.py) prépare les quatre scénarios, les simule puis construit la carte. Le [plan exécuté](../../artifacts/testing/mrp_execution_20260928/simulation_v6/plan.json) conserve les commandes complètes et les empreintes des entrées. Depuis la racine du dépôt, utiliser un dossier de travail neuf et un nouveau nom de carte :

```powershell
python -B etudecas/artifacts/testing/mrp_execution_20260928/study.py prepare --workdir etudecas/artifacts/testing/mrp_reproduction_nouvelle
python -B etudecas/artifacts/testing/mrp_execution_20260928/study.py run --workdir etudecas/artifacts/testing/mrp_reproduction_nouvelle
python -B etudecas/artifacts/testing/mrp_execution_20260928/study.py render --workdir etudecas/artifacts/testing/mrp_reproduction_nouvelle --html etudecas/resultats/mrp_reproduction_nouvelle.html
```

La recette refuse d'écraser ses fichiers existants. Elle dépend des graphes et recettes précédents cités dans le plan, ainsi que de la carte nominale conservée ; ces fichiers sont donc encore nécessaires à sa reproduction. Les cinq premiers essais de cette étape restent des preuves intermédiaires, avec leurs échecs ou limites documentés. **Seule la livraison `simulation_v6` est retenue ici.** Aucun test d'altération de fichiers, de dates ou de protections système n'a été effectué.

## Preuves et reproduction

Complément modèle : [calculs reproductibles](../../artifacts/testing/mrp_system_comparison_20260928/analyse.py) et [résultats / empreintes des 18 entrées inchangées](../../artifacts/testing/mrp_system_comparison_20260928/evidence.json). Trois audits indépendants en lecture seule ont couvert le moteur, les besoins/périmètres et les stocks/réceptions ; les regroupements des 23 commandes 021081 et les deux alignements ont été contre-calculés séparément. Aucune nouvelle simulation ni aucun test d'altération de fichiers n'a été lancé pour ce complément.

[Données détaillées de l'analyse](../../artifacts/testing/mrp_source_rules_20260928/analysis.json) · [Oracle indépendant sur les Excel](../../artifacts/testing/mrp_source_rules_20260928/validation/export-oracle.json) · [Script de lecture](../../artifacts/testing/mrp_source_rules_20260928/analyse.py).

Les deux calculs indépendants de l'audit initial rapprochent les cellules et les équations du MRP. Ils ne prouvent pas l'identité d'un algorithme ERP non fourni. Cet audit initial n'a changé aucun moteur, stock nominal ou carte. Les étapes ultérieures sont décrites en sections 15 à 19 ; les fichiers industriels restent inchangés.
