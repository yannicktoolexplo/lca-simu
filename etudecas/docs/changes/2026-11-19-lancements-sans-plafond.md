# Lancements MRP sans plafond de production PF

Étude du 19 novembre 2026, du 1er janvier au 1er juin 2025 : **152 jours**.
La référence `coherent-MRP-20261014` et les comparaisons précédentes sont conservées.

## Règle appliquée

Les lancements des lots suivent les besoins prévisionnels. Les horizons figés
restent de **4 semaines à 1810 et 8 semaines à 1430**. La prévision est révisée
le lundi et à l'ouverture du mois. La demande réelle devenue connue réduit le
reliquat mensuel, réparti sur les **jours calendaires restants**. Dans l'exemple
de quatre semaines entières, 1 000 prévus moins 300 demandés laisse 700 unités :
700 ÷ 3 = environ 233,33 unités de besoin prévisionnel par semaine restante.
Un mois civil n'a pas nécessairement quatre semaines entières : le calcul réel
utilise ses jours restants, et non systématiquement trois parts identiques.

Le MRP recalcule quotidiennement le plan hors de la zone figée. Il déduit les
stocks et les réceptions déjà engagées : les 700 unités de besoin ne sont donc
pas une obligation de fabriquer 700 unités supplémentaires. Le gel conserve les
dates et quantités prévues des ordres ; l'exécution physique peut néanmoins
prendre du retard, notamment si la matière manque. Aucune demande réelle future
n'est révélée au MRP.

Le débit hérité de 7 700 unités/jour correspondait à 107 800 unités divisées par 14
jours, sans capacité industrielle mesurée. Le candidat retire ce débit et le
quota hebdomadaire de lancements pour les deux PF. Il conserve les lots sources,
nomenclatures, stocks, engagements, calendriers et délais de disponibilité.
Plusieurs ordres dus peuvent partir le même jour, chacun avec son identité et
une vérification du kit matière présent, arrondi par lot physique. Les réceptions
futures ne financent pas le lancement courant. Une substitution insuffisamment
prouvée reste explicitement refusée. Le candidat change donc aussi l'admission
matière compatible avec ce calendrier : l'effet du débit seul n'est pas isolé.

Les ordres initiaux de conditionnement acceptent désormais ce mode explicitement
sans capacité modélisée : jour ouvert sans plafond quantitatif, jour fermé à zéro.
Leurs quantités et leurs dates restent inchangées ; aucun ordre n'est supprimé.

## Vérifications sur cette phase

**90 tests ciblés** passent. La préparation indépendante compte
**818 contrôles**.
Le cas synthétique de huit jours, relu sur
**1053 contrôles**, vérifie deux
lots de 107 800 unités à J1 et un à J2 : **323 400 PF physiques entiers**, sans double
consommation ni phase quotidienne répétée. Une réserve annexe automatique de 107 800
unités reste inutilisée. Seul le travail continu admet quatre unités du dernier
bit du nombre flottant ; les PF et composants comptés en unités restent entiers.

Le cas réel de **10 jours**, exécuté par le même adaptateur que les calculs longs,
conserve **20 ordres initiaux**, soit
**1 945 715 unités**. Le premier conditionnement
intervient à J9 et reste disponible à J23. Les
7 besoins concurrents ne deviennent connus qu'après la
production de leur jour de clôture J4. Sa contre-revue comporte
**887 contrôles** ; sa qualification CSV passe.
La disponibilité à J23 est prévue, pas encore observée dans ces dix jours.
Deux refus de cette contre-revue sont archivés : l'oracle avait supposé à tort
que le délai déclaré égalait toujours le nombre de jours lundi–vendredi entre
les dates source, puis avait omis les usages concurrents d'un carton. Le bilan
final les inclut. Pour cinq ordres, les dates représentent 11 ou 12 jours
lundi–vendredi alors que le délai déclaré vaut 10 : l'explication calendaire
reste inconnue ; les dates et les délais source sont tous conservés.

La phase précédente reste archivée. Son candidat avait échoué à l'initialisation,
avant J0 : il ne prouvait aucun comportement historique. Ses essais de fixture
refusés et ses preuves sur un autre état de code ne sont pas comptés comme des
réussites actuelles. Les corrections numériques et CSV sont rééprouvées ici.

Les deux calculs historiques reprennent les mêmes 206 besoins concurrents :
c'est une hypothèse commune issue du témoin conservé, pas un carnet industriel
indépendant. Le témoin courant est rapproché de l'ancien v3 avant le candidat.

Un premier oracle a refusé les dates des besoins matière déjà échus : il les
comparait directement à la date prévue de l'ordre. La règle existante reporte
une dette échue au jour du calcul tout en conservant sa date d'origine. La
contre-revue qualifiée contrôle ces deux dates et l'absence de modification du
carnet après gel. Le refus initial est conservé ; le moteur n'a pas été modifié
pour le faire passer.

## Résultats

La production réelle est **estimée par les retraits d'étuis** ; elle ne constitue
pas un journal de PF terminés. Une semaine absente reste inconnue. Les cumuls
portent sur les mêmes semaines documentées ; ce ne sont pas des totaux annuels.

### PF 268967

Toutes les quantités ci-dessous sont en unités physiques.

| Mesure | Témoin avec plafond | Lancements sans plafond | Écart candidat − témoin |
| --- | ---: | ---: | ---: |
| Erreur moyenne de production par semaine connue | 27 595 | 59 769 | 32 174 |
| Production sur les semaines observées | 415 800 | 539 000 | 123 200 |
| Écart du cumul à l'estimation réelle | 13 300 | 136 500 | 123 200 |
| Erreur moyenne de stock à Muret | 82 525 | 76 123 | -6 402 |
| PF terminés dans les nouveaux lots | 431 200 | 646 800 | 215 600 |
| Quantité servie aux clients | 623 081 | 623 081 | 0 |

Le cumul réel estimé vaut **402 500 unités** sur
**13 semaines connues**. L'erreur de production varie de
116,6 %, celle de stock de
-7,8 %.
La demande client vaut 623 081 unités dans les deux calculs.
L'attente finale passe de 0 à 0 unités.

### PF 268091

Toutes les quantités ci-dessous sont en unités physiques.

| Mesure | Témoin avec plafond | Lancements sans plafond | Écart candidat − témoin |
| --- | ---: | ---: | ---: |
| Erreur moyenne de production par semaine connue | 84 871 | 88 985 | 4 114 |
| Production sur les semaines observées | 3 097 715 | 3 212 915 | 115 200 |
| Écart du cumul à l'estimation réelle | 688 615 | 803 815 | 115 200 |
| Erreur moyenne de stock à Muret | 289 163 | 320 654 | 31 490 |
| PF terminés dans les nouveaux lots | 1 152 000 | 1 267 200 | 115 200 |
| Quantité servie aux clients | 1 419 969 | 1 419 969 | 0 |

Le cumul réel estimé vaut **2 409 100 unités** sur
**21 semaines connues**. L'erreur de production varie de
4,8 %, celle de stock de
10,9 %.
La demande client vaut 1 419 969 unités dans les deux calculs.
L'attente finale passe de 0 à 0 unités.


## Origine du pic de 268967

La nouvelle version prévisionnelle connue le **31 mars** augmente fortement les
besoins. La lecture directe de `Flow_Data_Customer_Demand.xlsx`, feuille
`Projection`, confirme deux exemples : pour la semaine du 26 mai, la quantité
passe de **45 286 à 111 315** ; pour celle du 9 juin, de **66 167 à 150 439**.
Les quatre cellules correspondent aux versions du 24 février et du 31 mars.
Le fichier encode ces demandes négativement ; leurs quantités positives sont
correctement reprises. Ces quatre cellules n'établissent seules ni l'unité,
ni le site, ni la validité industrielle de toute la prévision.

Quatre ordres déjà créés mais encore modifiables sont alors avancés. Leurs
besoins datés tombent à l'intérieur des huit semaines figées : le moteur place
les quatre lancements à la première date autorisée, **le 26 mai**. Ils deviennent
figés le 1er avril. Cela représente **431 200 unités le 26 mai**, puis un autre
lot de **107 800 le 30 mai**. La semaine atteint **539 000 unités simulées**,
contre **82 250 estimées dans le réel**. Les dates d'un ordre déjà figé avant
cette révision restent inchangées. Les six nouveaux lancements de 268967 sont
acceptés par le contrôle matière : ce pic n'est pas causé par une panne ou une
attente matière dans cet essai.

La concentration vient donc d'une hausse de prévision, de la borne figée et
de l'exécution quotidienne des lots entiers. Ce constat ne valide pas un nouveau
plafond, ni un étalement arbitraire des lots après cette date. Le prochain test
discriminant est un calcul local autour du 30–31 mars : garder le même carnet,
les mêmes stocks, la même taille de lot et le gel de 56 jours, puis isoler l'effet
de la version prévisionnelle et celui de la couverture de sécurité. Cette
contre-épreuve n'est pas exécutée dans la présente étude.

[Détail des lancements](../../artifacts/testing/lancements_sans_plafond_20261119/diagnostic/launch_explanation.md)
et [contrôle des cellules source](../../artifacts/testing/lancements_sans_plafond_20261119/diagnostic/projection_cells_check.json).

## Limites et suite

Retirer le plafond ne garantit pas une production progressive : les lots et leurs
dates peuvent créer des pics. Dans la résolution quotidienne native, un lot
approvisionné peut finir en une journée. Aucune durée physique mesurée, ni durée
de 14 jours, n'est ajoutée ; les courbes ne sont pas lissées artificiellement.
Les stocks aval peuvent absorber une différence de production. Les coûts connus
restent partiels. Ces essais ne démontrent ni une capacité industrielle réelle
ni une cause historique ; aucune référence n'est promue.

Deux descriptions héritées restent obsolètes : le commentaire du programme dans
le graphe mentionne encore 7 700 UN/jour, et le résumé du gel contient encore
`capacity_reservation`. Ces textes descriptifs ne pilotent pas le calcul. Les
arguments effectifs du moteur, le débit nul explicite dans le graphe et la
politique `unconstrained_lot_calendar_v1` établissent le mode réellement exécuté.
Dans ce mode seulement, ce débit nul signifie une capacité non modélisée ; il
ne représente pas une usine arrêtée. Ces descriptions sont à corriger lors d'une
prochaine révision des sources ; elles sont conservées ici pour préserver le gel.

Le navigateur, Node, les suites globales et les essais d'altération de fichiers
ne sont pas exécutés. La revue statique du HTML et la revue visuelle du PNG
restent distinctes d'une validation navigateur. Le manifeste final donne les
contrôles exécutés et les exclusions. Le contrôle documentaire global est
refusé : les index et empreintes de références générés restent à mettre à jour
dans six domaines, dont le contrat d'entrée modifié ici. Ce refus n'est pas
compté comme un contrôle réussi ; le contrat manuel de ce mode est documenté.

## Preuves et reproduction

- [Comparaison HTML](../../resultats/lancements_sans_plafond_20261119.html)
- [Comparaison précédente conservée](../../resultats/usages_concurrents_fixes_20261118.html)
- [Protocole courant](../../artifacts/testing/lancements_sans_plafond_20261119/protocol.json)
- [Preuves finales](../../artifacts/testing/lancements_sans_plafond_20261119/final_manifest.json)
- [Contre-revue du cas réel](../../artifacts/testing/lancements_sans_plafond_20261119/validator/smoke_real_final_review.json)
- [Phase antérieure conservée](../../artifacts/testing/duree_lots_sans_plafond_20261119/protocol.json)

Les cas `runs/control/case.json` et `runs/priority/case.json` du dossier courant
passent par `current_reference.run_engine`. Les pilotes refusent une sortie déjà
existante, des preuves manquantes ou des sources différentes du gel. Les résultats
lourds restent locaux.
