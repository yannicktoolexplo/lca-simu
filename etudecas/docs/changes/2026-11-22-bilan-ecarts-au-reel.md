# Bilan des écarts au réel en 2025

[Bilan interactif par article, site et date](../../resultats/bilan_ecarts_20261122.html) ·
[Tableau physique en CSV](../../resultats/bilan_ecarts_20261122_physique.csv) ·
[Preuves](../../artifacts/testing/bilan_ecarts_20261122/final_manifest.json)

## Demande prévue, demande réelle et sorties

Dans l’essai précédent, j’ai repris les **réceptions simulées** et
remplacé les **départs simulés de D1920** par la **demande historique de
la semaine** dans le bilan de stock. Ce test mesure jusqu’où le simple
écart de quantité ou de datation des sorties peut expliquer la variation
du stock. Les sorties clients brutes restent inconnues. L’essai ne
change aucune donnée de demande dans le moteur. Il réduit l’erreur de
variation physique de **0,47 %** pour le 268091 et de **46,8 %** pour le
268967, sous cette convention.
[Calcul des flux](../../artifacts/testing/iterations_chainage_20261121/sources/receipt_pressure.json)

Dans le candidat historique de **152 jours**, le MRP planifie avec les
versions de prévision déjà connues. À la clôture d’une semaine, la
demande réelle est publiée le lundi suivant et vient consommer le
budget du mois auquel elle se rapporte. Par exemple, **1 000 − 300 =
700**, soit **233,33 unités prévues** par semaine s’il en reste trois.
Le moteur répartit ce reliquat sur les vrais jours calendaires restants.
Un nouveau mois ouvre son budget. Les commandes encore à livrer
restent ouvertes. Le rythme obtenu reste un besoin de planification
auquel s’appliquent stocks, lots et horizons figés.

Les **304 lignes journalières** de cet essai ont été recalculées à
partir des entrées et des dates de publication. La référence active
emploie encore une consommation hebdomadaire. Le bilan mensuel revu
chaque semaine est celui du candidat qualifié, présenté comme tel.
[Contrôle de la règle de demande](../../artifacts/testing/bilan_ecarts_20261122/demande/demand_modes.json)

À terme, la demande réalisée d’une semaine sera générée par le
scénario et publiée à sa clôture. Le MRP conservera la prévision
en entrée. Un premier prototype de demande autonome apprend sur
25 semaines et est évalué sur les 25 semaines suivantes, avec 32
trajectoires. La correction simple de biais réduit l’erreur de
**107,3 à 65,2 %** pour le 268091 et de **158,7 à 149,1 %** pour le
268967 par rapport à la prévision brute. Les fourchettes censées
couvrir 80 % des semaines en couvrent **48 % et 60 %**. Ces résultats
gardent le générateur au stade d’essai.
Sur les mêmes semaines, la médiane de la demande passée utilisée
comme valeur constante atteint **33,2 % et 45,1 %** d’erreur. Elle
est plus proche de l’historique que chacun des 32 tirages. Ce témoin
donne le seuil à battre pour le futur générateur.
[Témoins simples](../../artifacts/testing/bilan_ecarts_20261122/demande/constant_baselines.json)

## Où les essais ont rapproché les courbes

L’**erreur absolue en %** additionne les écarts absolus à chaque
date, puis les rapporte à la somme des valeurs absolues observées.
Le **biais** garde le signe des écarts et utilise le même dénominateur.
Un biais peut compenser les avances et les retards. Il est donc présenté
à côté de l’erreur absolue. Sur une série observée entièrement à zéro,
les écarts restent exprimés en unités physiques. Les résultats par
famille font la moyenne des pourcentages définis par article et site.

Les trois scénarios courts sont comparés aux mêmes dates. Le
**contrôle initial**, la **réduction prudente des ordres figés** et
le **candidat avec engagements et autorisation d’atelier** couvrent
la même fenêtre du 1er janvier au 1er juin 2025. Les points de mesure
dépendent de la couverture des sources. Les photos du lundi sont
rapprochées de la clôture simulée du dimanche.

| Famille | Couples et points | Contrôle initial | Réduction des ordres | Dernier candidat |
| --- | ---: | ---: | ---: | ---: |
| Stock physique | 30 · 630 | 30,80 % | 30,77 % | **29,91 %** |
| Prélèvements matière et emballage | 28 · 521 | 107,93 % | 90,13 % | **83,75 %** |
| Entrées physiques | 27 · 502 | 121,97 % | **120,38 %** | 127,16 % |
| Mouvements nets signés | 30 · 563 | 111,20 % | **104,93 %** | 105,42 % |
| Prélèvements d’étuis dédiés | 2 · 34 | 135,31 % | 81,74 % | **72,07 %** |
| Production comparée à l’estimation par les étuis | 2 · 34 | 135,31 % | **81,74 %** | 82,79 % |

Entre les deux derniers scénarios, **6 stocks se rapprochent,
21 restent identiques et 3 se dégradent**. Les prélèvements
s’améliorent sur **6 couples** et se dégradent sur **2**. Les entrées
restent identiques sur **25 couples** et se dégradent sur **2**.
Après le 7 mai, l’erreur des prélèvements remonte de **89,71 % à
94,68 %**. Sur 5 séries de prélèvements et 4 séries d’entrées,
le volume observé sur la fenêtre est nul et l’écart est donné
en unités physiques.
[129 séries, points et statistiques](../../artifacts/testing/bilan_ecarts_20261122/physical_score.json)

| Série sur la fenêtre commune | Réduction des ordres | Dernier candidat | Biais du candidat |
| --- | ---: | ---: | ---: |
| 268967 · stock à D1920 | 7,29 % | **3,94 %** | +3,79 % |
| 268967 · retraits d’étuis à D1430 | 85,91 % | **66,57 %** | −46,43 % |
| 268967 · production estimée par les étuis | **85,91 %** | 88,01 % | −46,43 % |
| 333362 · stock à D1430 | 46,41 % | **26,12 %** | +18,08 % |
| 333362 · entrées à D1430 | **106,26 %** | 160,83 % | −5,46 % |
| 773474 · stock à D1430 | **29,22 %** | 33,66 % | −33,66 % |
| 268091 · stock à D1920 | 42,39 % | 42,39 % | +27,32 % |
| 268091 · production estimée par les étuis | 77,57 % | 77,57 % | +33,37 % |
| 693055 · stock à D1450 | 30,14 % | 30,14 % | +8,94 % |
| 693055 · stock à D1810 | 26,55 % | 26,55 % | +20,37 % |

Pour le 268967, le volume sur semaines documentées se rapproche,
alors que les dates d’achèvement se dégradent légèrement par rapport
à la variante précédente. Pour le 333362, le faible biais sur les
entrées cache des écarts de calendrier importants. Les points
individuels permettent de localiser les semaines qui font l’écart.
À volume total conservé sur les semaines documentées, déplacer les
lots ne peut faire descendre l’erreur de production sous **33,37 %**
pour le 268091 et **46,43 %** pour le 268967. Il faudra examiner le
volume engagé en plus du calendrier.

## L’année civile et les essais courts

Le résultat annuel archivé documente **1 563 photos sur 31 couples**
et **1 296 mouvements nets**. L’erreur moyenne sur stocks vaut
**34,95 %** dans cette archive. La demande chargée et la localisation
du contrôle des produits finis diffèrent des essais de novembre.
La tendance de progression se lit sur les fenêtres appariées.

| Produit | Sorties de fabrication simulées sur 365 jours | Dont nouveaux lots simulés | Biais sur semaines avec étuis documentés |
| --- | ---: | ---: | ---: |
| 268091 | 4 292 915 | 2 347 200 | −15,00 % sur 46 semaines |
| 268967 | 1 401 400 | 1 401 400 | −31,76 % sur 36 semaines |

Les sorties de fabrication du 268091 incluent **1 945 715 unités
du carnet initial**. Le biais est calculé uniquement sur les semaines
avec prélèvements d’étuis renseignés. Ces prélèvements estiment la
production industrielle, avec une incertitude sur la date de fin.

Sur les **98 jours appariés**, les transferts déclenchés par le
besoin réduisent l’erreur de stock du 268091 à D1920 de **12,66 %**
sur 14 photos prises en fin de dimanche. Pour le 268967, elle
augmente de **26,21 %**. Dans un autre essai, un achat décalé empêche
la fabrication d’un lot de **107 800 unités** à D1430. Les 14 mêmes
photos de D1920 sont pourtant identiques à celles de l’essai où le
lot est fabriqué puis gardé à l’usine. Le contrôle au niveau usine
permet de départager les deux mécanismes.
[Essais comparés sur leurs propres fenêtres](../../artifacts/testing/bilan_ecarts_20261122/essais_locaux/local_experiments.json)

## Prévisions, plans et limites des données

| Famille | Périmètre et résultat |
| --- | --- |
| Prévision commerciale | Sur les 51 semaines pleines, dernière prévision connue avant la semaine, erreur **151,36 %** pour 268091 et **116,97 %** pour 268967. Biais **+126,84 %** et **+75,30 %**. Ces écarts sont présents dans l’entrée commerciale. |
| Demande réelle chargée | **0 % d’écart** sur les 20 semaines complètes appariées par produit dans les scénarios courts. Ce chiffre contrôle le chargement des données. |
| Plans MRP à quatre semaines | Sur **2 088 points et 30 couples**, l’erreur médiane des besoins passe de **31,89 % à 30,01 %**, celle du stock projeté de **50,22 % à 45,52 %**. Les versions sont comparées selon les mêmes dates cibles. |
| Plans MRP de D1920 | Pour 268091, le besoin et le solde projeté restent à **58,66 % et 386,02 %** d’écart. Le dénominateur du solde est faible dans plusieurs semaines. Pour 268967, le solde se dégrade de **11,62 % à 13,96 %**. |
| Commandes et réceptions d’achat | **88 positions sur 104** du carnet initial sont représentées dans l’essai. Sur les réceptions agrégées, actualiser les échéances rapproche le 042342 à D1430, **103,39 % à 1,69 %**, et dégrade le 021081 à D1450, **221,24 % à 775,95 %**. La correspondance par ligne de commande reste inconnue. |
| Livraisons, disponibilité et CA | Le témoin simule tout le volume publié à J+2, avec zéro attente avant départ de D1920. Les expéditions et livraisons industrielles brutes par commande ne sont pas identifiées. Le CA perdu observé se lit dans son périmètre financier, **7,13 % et 4,60 %** du CA livré et perdu signé. |
| Stocks utilisables, transit et coûts | Les statuts du MRP sont des positions planifiées et les photos sont physiques. Les mises à disposition et les transits industriels par lot sont inconnus. La valorisation des relevés et les coûts d’immobilisation simulés ont des bases différentes. Un écart global de coût ou de niveau de service ne serait pas comparable. |

Une partie des besoins agrégés du MRP alimente déjà le modèle.
Les écarts de plan ne valent donc pas validation indépendante de
toutes les décisions. Les mouvements nets peuvent avoir une erreur
supérieure à 100 % lorsque des hausses et baisses se produisent à
des semaines différentes.
[Plans, achats et familles documentées](../../artifacts/testing/bilan_ecarts_20261122/complements/coverage_complement.json)

## Priorités après ce bilan

1. **268091 et D1920.** Vérifier la première semaine de prévision
   et les besoins qui déclenchent les gros lancements au sortir du
   gel. Suivre en parallèle les transferts d’D1810 par lot. Garder
   l’écart de stock de D1920 et le total physique de la chaîne
   comme mesures conjointes.
2. **268967 et les réceptions de D1430.** Les prélèvements et le stock
   se rapprochent, mais les dates de fin de lot restent en écart.
   Raccorder le 042342 à sa libération, puis comparer la fin physique
   du lot de 107 800 et son départ éventuel. Le stock de D1920 seul
   ne permet pas de choisir entre matière indisponible et lot
   resté à l’usine.
3. **D1450 et achats amont.** Reprendre les dates de réception et
   de mise à disposition des couples dont le stock se dégrade ou
   dont l’erreur de flux est élevée. Pour le 693055, l’écart de stock
   reste de 30,14 % à D1450 sur la fenêtre récente et de 83,46 %
   sur le repère annuel. Les fenêtres couvrent des saisons différentes.
4. **Demande autonome.** Comparer le futur générateur à la médiane
   passée et au signal commercial, sur des semaines gardées à part.
   La demande générée doit rester entière, pouvoir dépasser la
   prévision et être découverte au même moment que l’historique
   dans le rejeu actuel.
