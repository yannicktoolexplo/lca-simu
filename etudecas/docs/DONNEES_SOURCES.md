# Données sources : contenu, rapprochements et limites

Audit du **8 octobre 2026** de tous les fichiers présents dans `etudecas/data/source`.
Ce document est le point d'entrée pour reprendre une étude sans reconstruire à
chaque fois la connaissance des sources. Les détails chiffrés, lignes Excel,
empreintes et résultats par article/site sont dans le
[registre associé](reference/source_knowledge.json).

**Périmètre : 22 fichiers — 14 Excel, 7 CSV et 1 JSON — et 38 onglets Excel.**
Les deux fichiers temporaires Office `~$…` sont exclus. Tous les onglets et toutes
les lignes non vides ont été parcourus. Les quantités ont été rapprochées après
conversion explicite des unités. Les formules Excel ont été lues avec leur
résultat enregistré ; Excel n'a pas été utilisé pour les recalculer.

La référence demande/centre de distribution acceptée, commit **`d9193dff4`**,
reste conservée. Cet audit ne modifie ni les sources, ni les règles du moteur,
ni les scénarios, ni les cartes HTML. Il distingue une observation dans les
fichiers, une déduction numérique et une hypothèse métier.

## Ce qu'il faut retenir

| Constat vérifié | Conséquence pour le travail suivant |
|---|---|
| Il existe bien des stocks d'usine pour les matières et semi-finis. Les photos des deux PF concernent seulement Muret. | Ne plus confondre « pas de photo du PF en sortie d'usine » avec « pas de stock d'usine ». |
| Les colonnes `Sorties` et `Sorties_article_scan3` s'ajoutent dans les bilans des composants. | Ne pas traiter scan3 comme un sous-ensemble déjà inclus dans Sorties. |
| À Gaillac, les entrées de 773474 valent systématiquement deux fois les entrées compatibles avec les stocks sur les 41 semaines rapprochables. | Examiner cette incohérence d'export avant d'ajuster le MRP pour reproduire ces volumes. La cause du facteur deux reste inconnue. |
| Les 104 dates d'entrée des en-cours sont compatibles avec lundi–vendredi, jours fériés et fermeture du 4 au 15 août. | Distinguer le jour de livraison du jour de disponibilité ; le calendrier mérite un essai ciblé ultérieur. |
| Les nomenclatures se recoupent, mais les consommations scan3 des matières et des emballages ne conduisent pas aux mêmes quantités de PF. | Le problème ne peut pas être attribué uniquement aux commandes MRP ; le périmètre des consommations doit aussi être résolu. |
| Certaines politiques de stock et tailles de lot ont changé entre fichiers, sans date d'effet. | Conserver les versions et les choix historiques pour 2025 ; ne pas prendre automatiquement la dernière valeur pour toute l'année. |
| Le nom d'une colonne ne suffit pas : à Muret, `Sorties` contient des valeurs positives et négatives. | Ce champ ne fournit pas à lui seul les départs clients bruts. La référence acceptée reste explicitement une estimation de la réponse réelle. |

## 1. À quoi sert chaque fichier ?

Les nombres ci-dessous désignent des lignes de données, hors en-tête, sauf
mention contraire. Plusieurs fichiers reprennent les mêmes informations : ils
ne constituent pas autant de mesures industrielles indépendantes.

| Fichier | Contenu utile | Place dans l'analyse |
|---|---|---|
| `268091.xlsx` | BOM : 15 composants ; FIA : 23 conditions d'achat | Nomenclature Cicalfate et conditions fournisseur : prix, base de prix, unité, délai, quantité standard. |
| `268967.xlsx` | BOM : 8 composants ; FIA : 8 conditions | Nomenclature Permixon à Gien, dont le semi-fini 773474. |
| `773474.xlsx` | BOM : 1 composant ; FIA : 4 conditions | Fabrication à Gaillac et achats de 021081. |
| `Data_poc.xlsx` | Acteurs, relations, BOM et paramètres de démonstration | Version structurelle ancienne ; certaines références et relations sont dépassées. |
| `demand_PF.xlsx` | Structure enrichie, 104 lignes de demande, trajets et machines | Demande utilisée dans la référence acceptée ; structure plus complète que Data_poc, mais métadonnées de calendrier anciennes. |
| `Extract_Données_Complémentaires.xlsx` | 32 stocks initiaux, 25 politiques, 3 tailles de lot | Photo de départ et ancienne version des règles ; à conserver pour comprendre 2025. |
| `Extract_En_cours.xlsx` | 104 engagements : quantités, sites, dates de livraison et de disponibilité | Initialisation des réceptions/fabrications déjà prévues avant le démarrage. |
| `Flow_Data_Inventory_and_Replenishment_rules.xlsx` | 1 646 photos, 27 politiques, 4 tailles de lot ; onglet Graph | Source détaillée de stock daté et version actualisée des paramètres. Graph est une présentation des stocks, pas une nouvelle observation. |
| `Flow_Data_Inventory_movements.xlsx` | 1 319 mouvements hebdomadaires | Rapprochement physique des stocks, entrées, sorties, consommations scan3 et ajustements. |
| `Flow_Data_MRP_results.xlsx` | 53 398 lignes, 52 versions de plan, 33 couples article/site | Ce qui était prévu à chaque calcul MRP, pour chaque semaine future. Ce ne sont pas des mouvements exécutés. |
| `Flow_Data_Customer_Demand.xlsx` | 106 lignes historiques ; 1 352 prévisions | Historique daté et 13 versions prévisionnelles de 52 semaines par PF. |
| `CA_Perdu_Réel.csv` | 522 lignes, 261 jours ouvrés par PF en 2025 | CA livré et perdu, avec corrections signées. Pas de quantité livrée ni de prix de vente explicite. |
| `Dispo_PF_Projeté.csv` | 64 lignes, 32 dates de calcul par PF | Nombres de semaines de rupture projetées ; horizons qui se recouvrent, pas service réalisé. |
| `Stock_PF_Immobilisé.csv` | 104 valorisations hebdomadaires | Valeur financière des PF, sans ventilation explicite usine/dépôt. |
| `Stock_Composants_Immobilisé_Cos.csv` | 52 valorisations | Agrégat financier cosmétique, périmètre à rapprocher des stocks détaillés. |
| `Stock_Composants_Immobilisé_Pharma.csv` | 52 valorisations | Agrégat financier pharmaceutique, même réserve de périmètre. |
| `Fournisseur.xlsx` | 31 comptes/localisations, dont 4 sites internes | Identité et géographie ; les sites internes ne sont pas tous des fournisseurs externes. |
| `Trame_Audit_Fournisseur.xlsx` | 4 onglets d'évaluation, 810 cellules avec formule | Questionnaire et calculs de maturité/résilience ; exemple lié à VD0993480A. |
| `Trame d'audit fournisseur finalisé.xlsx` | Autre version des mêmes 4 onglets, 810 cellules avec formule | Réponses et scores différents ; le mot « finalisé » ne démontre ni une date d'effet ni un audit industriel indépendant. |
| `supplier_public_evidence.csv` | 31 pièces documentaires, 20 fournisseurs | Contexte public stocké localement, avec URL, date, périmètre et confiance. |
| `supplier_context_proxies.csv` | 29 fournisseurs | Signaux dérivés de contexte, pas observations de retard ni probabilités de défaillance mesurées. |
| `supply_graph_poc.json` | 26 articles, 36 nœuds, 39 liaisons, 1 scénario | Graphe dérivé comportant de nombreuses valeurs par défaut ; ce n'est pas une source industrielle primaire. |

## 2. Quels stocks possède-t-on réellement ?

La bonne identité est **article + site + unité + date**. Une même référence à
Gaillac et à Gien désigne deux stocks distincts. Son type peut dépendre du site :
773474 est PFI à Gaillac et MP à Gien dans le fichier actualisé.

| Site | Articles avec photos de stock |
|---|---|
| **Avène — 1810** | 001757, 001848, 001893, 002612, 007923, 016332, 029313, 039668, 049371, 055703, 099439, 338928, 338929, 426331, 693055 |
| **Gaillac — 1450** | 001893, 002612, 021081, 693055, 773474 |
| **Gien — 1430** | 001848, 007923, 038005, 042342, 333362, 344135, 708073, 730384, 734545, 773474 |
| **Muret — 1920** | 268091, 268967 |

Il y a **32 couples article/site** : 31 possèdent 53 photos du 1er janvier au
29 décembre 2025 ; 344135/Gien n'a que trois photos, en fin décembre.
L'ancien fichier donne cependant un stock initial nul pour 344135/Gien.
Le MRP contient aussi **029313/Gien**, absent des photos : les huit lignes
identifiées sont nulles. Ce n'est pas une série de stock mesurée supplémentaire.

**Stock de PF en sortie d'usine :** aucune série de photos pour 268091/Avène
ou 268967/Gien n'a été trouvée dans Stocks, les mouvements ou les groupes MRP.
Les lots de fabrication et les ordres O.Proc attestent des opérations à l'usine,
mais ne fournissent pas la quantité présente chaque semaine après fabrication.
Les CSV financiers ne permettent pas non plus de l'isoler directement.

**Règle usine PF → Muret reconfirmée par l'utilisateur le 8 octobre :**
l'industriel pousse au centre de distribution les produits fabriqués, une fois
le contrôle/libération terminé à l'usine. L'expédition ne dépend donc pas d'une
nouvelle commande client ; le pilotage des quantités à fabriquer reste distinct.
Le produit reste à l'usine pendant son contrôle et l'attente du départ, puis en
transit avant son arrivée à Muret. Ce principe ne signifie pas un stock usine
constamment nul ni une arrivée instantanée au dépôt.

La **fréquence réelle des départs reste inconnue** : une fois par semaine ou
plusieurs fois. Les photos et mouvements hebdomadaires ne permettent pas de
départager ces cadences. Un total hebdomadaire de 100 000 unités pourrait provenir
d'un seul départ ou de plusieurs. La confirmation du principe vient de
l'industriel, rapportée par l'utilisateur ; l'absence de photos de PF à l'usine
n'est pas, à elle seule, sa preuve. Toute cadence simulée reste une hypothèse
logistique tant qu'un calendrier ou un journal de transferts ne la documente pas.

Gaillac cumule un rôle de fabrication et de stockage/transfert. Les flux agrégés
corroborent les liaisons : **67 200 kg** de sorties de 773474 à Gaillac et autant
d'entrées à Gien ; **13 190 kg** de sorties de 693055 à Gaillac et autant d'entrées
à Avène. Ce rapprochement de volumes ne donne pas les identifiants des transports
ni leur durée exacte. La fabrication de 693055 à Gaillac est confirmée par
l'utilisateur, mais sa BOM amont n'est pas fournie : une matière fictive resterait
une convention de simulation clairement identifiée.

## 3. Lire correctement les dates, les signes et les unités

### Stocks et mouvements physiques

Pour les matières, emballages et semi-finis, le bilan à vérifier est :

```text
variation du stock = Divers + Entrées + Sorties + Sorties_article_scan3
```

Les sorties sont déjà signées. **Il faut additionner leurs valeurs signées**,
et non retrancher une deuxième fois leur signe. Scan3 s'ajoute à Sorties dans cet
export : 36/36 bilans pour 333362/Gien et 43/43 pour 773474/Gien, contre 12/36
et 14/43 si l'on omet scan3. L'utilisateur a indiqué que scan3 concerne seulement
268091 et 268967 ; ce sens métier reste la convention, avec la contradiction BOM
décrite plus loin.

Le repère du dimanche dans **Inventory_movements** se rapproche beaucoup mieux
du stock du **lundi suivant au lundi suivant + 7 jours** : **1 161/1 298** bilans
concordent, contre 33/1 273 avec la semaine précédente. Une ligne absente n'a
pas été remplacée par zéro. Ce résultat concerne cet export ; il ne prouve pas
que tous les autres fichiers utilisent la même convention hebdomadaire.

À Muret pour les PF, Entrées et scan3 sont toujours nuls tandis que Sorties est
positif ou négatif. Ce champ se rapproche d'un **mouvement net**, sans séparation
fiable des réceptions d'usine et des départs clients. Le bilan avec les photos
ferme sur 39/52 intervalles pour Cicalfate et 47/52 pour Permixon, première
période partielle comprise. Les écarts restants doivent rester visibles.

### Plans MRP

Il faut garder simultanément la **date de calcul** et la **semaine prévue**.
Les 52 versions vont du 5 janvier au 28 décembre 2025 ; l'horizon atteint
364 jours après le calcul, jusqu'au 27 décembre 2026. Il peut donc y avoir
53 repères en incluant la semaine courante. L'export n'est pas une grille pleine.

Pour un article/site et une version donnés, après tri des semaines :

```text
K(t) = K(t précédent) + H(t) − I(t) + J(t)
H = Entrée prévue ; I = Sortie prévue ; J = Stock_physique ; K = Stock fin de semaine
Pour la première ligne de la version, K(t précédent) = 0.
```

**53 398/53 398 bilans se ferment.** C'est un contrôle arithmétique de l'export,
pas la démonstration que notre moteur reproduit ses règles de décision.

L'utilisateur a confirmé que J placé dans le futur est du stock déjà présent,
mais disponible plus tard. **800 lignes** présentent un J futur non nul.
Ce n'est pas une nouvelle réception à ajouter au physique déjà présent.
Même en sommant J dans la version, le rapprochement avec les photos ne concorde
que dans **1 131/1 615 cas**. Les 484 écarts concernent aussi des PF, des emballages
et Gaillac : ils ne s'expliquent pas tous par les matières partagées.

Ne jamais additionner les entrées de toutes les versions pour calculer les
réceptions annuelles : une même proposition peut être répétée, avancée ou reportée.
Ces données permettent d'estimer des replanifications hebdomadaires, mais pas
d'identifier sans ambiguïté chaque ordre individuel.

### En-cours et calendrier

`Extract_En_cours` contient **53 AVICDE, 29 ECHCDE et 22 O.Proc**. Les dates de
livraison vont du 3 janvier au 21 mai, les dates d'entrée du 6 janvier au
19 septembre 2025. L'état exact de prélèvement des composants des O.Proc n'est
pas documenté par un identifiant/statut matière.

Le calcul `date de livraison + temps de réception`, sans compter le jour de
livraison lui-même, reproduit :

| Calendrier testé | Dates d'entrée exactes |
|---|---:|
| Lundi–vendredi | 70/104 |
| Lundi–vendredi hors jours fériés français | 99/104 |
| Idem, hors fermeture du 4 au 15 août 2025 inclus | **104/104** |

Deux agents l'ont recalculé indépendamment, avec des méthodes différentes.
Les cinq lignes qui nécessitent la fermeture sont **23, 25, 30, 39 et 42**.
La liste des jours exclus et les 104 dates sont conservées dans la preuve locale.
Cela appuie fortement ce calendrier pour **ces en-cours**, sans démontrer qu'il
faut l'appliquer à tous les transports, achats et sites. Les dates explicites
des engagements initiaux doivent être conservées avant toute recomputation.

Les durées diffèrent aussi entre les en-cours et le Flow MRP : par exemple
001848/Gien **14 → 26**, 338929/Avène **4 → 6**, 693055/Gaillac **21 → 28**,
773474/Gaillac **26 → 33** jours. Ce sont des divergences de paramètres entre
sources, pas des retards de livraison mesurés.

### Unités et montants

Les conversions utilisées sont `G / 1 000 = KG`, `ZUN = UN`, et `M` reste un
mètre. Aucun stock ni mouvement physique source en UN n'est fractionnaire.
Une base de prix de 1 000 porte sur le **prix**, pas automatiquement sur la
quantité commandée. Ainsi, 338929 a une quantité standard FIA de **5 000 ZUN**,
soit 5 000 unités, pas 5 000 kg ni 5 millions d'unités.

Les onglets de taille de lot ne portent pas eux-mêmes de colonne d'unité.
Les valeurs brutes 3 200 000 pour 773474 et 600 000 pour 693055 sont interprétées
en grammes par rapprochement avec les quantités et les autres tables, soit
**3 200 et 600 kg**. Cette conversion est une déduction documentée.

## 4. Actualisations, redondances et versions à conserver

| Comparaison | Résultat | Usage retenu |
|---|---|---|
| Stocks initiaux ancien/nouveau | 31 paires comparables ; 29 égales dans la tolérance, 002612/Avène diffère d'environ 3 g, 042342/Gien de 1 UN | Continuité initiale très forte ; conserver les valeurs brutes et leur précision. |
| Politique PF 268091/Muret | 20 → 0 jours | Nouvelle valeur présente, date d'effet absente ; ne pas annuler silencieusement une décision de scénario. |
| Politique PF 268967/Muret | 25 → 60 jours | Même réserve ; l'utilisateur a demandé de revenir au régime 2025 pour ses essais historiques. |
| Politique 426331/Avène | 7 → 10 jours | Actualisation identifiée, date d'effet inconnue. |
| Politiques Gaillac ajoutées | 773474 : 20 jours ; 021081 : 900 000 kg de sécurité fixe | Données nouvelles à considérer pour les essais, sans inventer leur date d'application. |
| Fabrication 268091 | Minimum 14 400 → 28 800 UN ; maximum 142 485 inchangé | Distinguer minimum de production, palette et multiple imposé. |
| Fabrication 693055 | Lot fixe ajouté, 600 kg après conversion | Complète le rôle fabricant de Gaillac. |
| BOM primaires contre demand_PF | 24 coefficients concordants après normalisation | Les fichiers primaires et la copie structurelle se corroborent. |
| Prix FIA contre copies structurelles | 29 correspondances Data_poc + 35 demand_PF concordantes | Une même information répétée, pas 64 observations nouvelles. |
| Data_poc contre demand_PF | Ancien 693710 remplacé par 007923 ; fabrication de 773474 à Gaillac ajoutée | Data_poc n'est plus une description complète de la structure courante. |
| Flow Customer actuel contre `8ac4831d4` | 106 historiques et 1 352 prévisions inchangés ; suppression de `SKU Label` | Actualisation de structure, pas nouvelle demande chiffrée. |
| demand_PF, colonnes prévision/réel | Égalité exacte sur les 104 lignes | Ne pas utiliser ces deux colonnes comme prévision et réalisation indépendantes. |
| Overview Data_poc / demand_PF | Onglets identiques ; 11 juin 2025, 11 pas | Métadonnées de démonstration impropres à dater seules les 52 semaines de demande. |
| Les deux audits fournisseurs | 337 cellules non vides différentes ; Mode d'emploi identique | Versions différentes, pas fichiers identiques ; ni date ni auditeur renseignés. |
| CSV de valorisation / Excel de stock | Aucun des 104 montants PF identique au centime | Périmètre ou valorisation différente ; ne pas supprimer comme doublon. |

Le nom « dernier fichier » ne suffit donc pas à décider qu'un ancien fichier
est inutile. Les anciennes politiques, les en-cours et les valorisations
conservent une information distincte. Cette passe ne supprime aucun original.

L'ancienne anomalie **002612/Gaillac = 1 250 414 kg** n'est **plus présente** :
la source actuelle donne **1 250 kg**, valeur **1 575**, le 6 janvier, ligne 946
de Stocks. Les photos voisines donnent 414 kg au 1er janvier et 1 664 kg au
13 janvier. Il subsiste donc une question de raccordement au démarrage, mais
il ne faut plus répéter le facteur 1 000 comme anomalie actuelle.

## 5. Anomalies et déductions qui comptent pour la suite

### 773474 à Gaillac : un facteur deux dans les entrées exportées

Sur les semaines rapprochables, le bilan avec Entrées intégral ferme **12/41**
fois ; avec Entrées divisées par deux, **41/41** fois. Les 29 entrées positives
du fichier sont toutes de **6 400 kg**, alors que les variations de stock et
les sorties correspondent à **3 200 kg**.

```text
Stock initial                    9 600 kg
Stock final                     35 200 kg
Sorties exportées               67 200 kg
Entrées impliquées par le bilan 35 200 − 9 600 + 67 200 = 92 800 kg
Somme Entrées dans le fichier   185 600 kg
```

Exemple contrôlable : ligne mouvement **1282**, repère du 19 janvier ; photos
Stocks **1240 et 433**, 20 et 27 janvier : le stock passe de 6 400 à 9 600 kg,
sans sortie, mais la colonne Entrées indique 6 400 kg.

**Le facteur est constaté ; sa cause n'est pas démontrée.** Double comptage
d'export, périmètre ou type de mouvement restent des explications possibles.
Ce n'est surtout pas une règle MRP à généraliser : pour 693055/Gaillac, les
entrées normales ferment 34/36 bilans ; leur moitié seulement 16/36.
Aucune correction `/2` n'a été appliquée aux sources ni à la simulation.

### Les consommations scan3 et la BOM ne décrivent pas encore le même volume

En divisant la consommation scan3 par la quantité de composant nécessaire à
un PF selon les BOM sources, sur les semaines exportées du 5 janvier au
28 décembre :

| Chaîne | Quantité de PF équivalente d'après les matières | D'après les emballages |
|---|---:|---:|
| Cicalfate | Environ **24,23 millions**, de façon très cohérente entre les 12 matières | Environ **5,02 millions** pour les étuis, **5,04 millions** pour les tubes |
| Permixon | Environ **5,80 à 6,08 millions** selon les matières | Environ **1,26 à 1,31 million** pour les emballages avec consommation documentée, hors 344135 |

Exemple : **049371**, environ 36 408 kg consommés, pour 0,0015022 kg par PF dans
la BOM, représente environ 24,24 millions de PF équivalents. Le même ordre de
grandeur ressort pour 001848.

Cette cohérence par groupe indique une différence systématique de périmètre,
d'unité de production ou d'affectation entre matières et conditionnement.
Elle **ne prouve pas** que toutes ces matières sont partagées, ni qu'il suffit de
multiplier une BOM par cinq. La BOM source et la confirmation utilisateur sur
scan3 sont conservées ; leur incompatibilité apparente reste explicitée.
Les matières confirmées partagées par l'utilisateur sont notamment 002612,
007923, 042342, 693055, 730384 et 708073. Cette confirmation ne permet pas de
choisir automatiquement un pourcentage d'affectation aux deux PF.

### Les prévisions sont réellement différentes des historiques

Flow Customer contient 13 versions de 52 semaines par PF, avec des horizons
jusqu'au **28 décembre 2026**. La première version est datée du 30 décembre 2024 ;
les suivantes sont datées de 2025. Ce sont des prévisions, pas des ventes 2026.

Sur les **51 semaines complètes de 2025**, en choisissant pour chaque lundi la
dernière version déjà connue qui contient cette semaine :

| Produit | Prévision source cumulée | Historique Flow cumulé |
|---|---:|---:|
| 268091 | 9 404 597 | 4 145 843 |
| 268967 | 2 965 870 | 1 691 923 |

L'écart est dans les cellules sources. Il peut combiner erreur de prévision et
différence de périmètre ; on ne peut pas le faire disparaître en renommant une
courbe. Les prévisions doivent être sélectionnées **à la date où elles étaient
connues**, sans utiliser rétrospectivement une version future.

### Demande, réponse et finance : conserver les définitions

La référence acceptée emploie la demande `demand_PF` avec ses quatre valeurs
négatives Permixon ramenées à zéro, les prévisions datées Flow, et une réponse
réelle **estimée** avec la part de CA livré. Elle reste inchangée.

L'audit confirme les limites de ces rapprochements :

- `demand_PF` ne date pas ses lignes ; l'ancrage hebdomadaire est une convention
  du scénario, pas une date écrite dans chaque cellule.
- Sur les 52 semaines rapprochées, demand_PF corrigé et Flow Historique sont
  égaux seulement 16 fois pour Cicalfate, 49 fois pour Permixon.
- Les semaines Flow Permixon du 21 avril, 28 avril et 26 mai valent zéro, alors
  que le CA livré est positif. Les quatre semaines demand_PF négatives ont
  également du CA livré positif.
- `CA_Perdu_Réel` donne des montants signés, sans prix de vente ni devise
  explicite. Sur l'année, `somme(CA livré) / somme(CA livré + CA perdu)` vaut
  **92,87 % pour Cicalfate et 95,40 % pour Permixon**. Ce n'est ni un comptage des
  unités livrées ni un taux de livraison à l'heure.
- La correction de CA perdu **−45,86** de Cicalfate, le 9 octobre, reste signée.
  `Nb_Rep_CA_Perdu = 0` n'implique pas partout une perte financière nulle.

Sous l'hypothèse « Flow Historique = sorties clients », on peut calculer
`réceptions Muret = variation stock + sorties clients − autres ajustements`.
Les réceptions ainsi déduites sont non négatives dans **50/51** semaines pour
chaque PF, dont 20 valeurs nulles pour Permixon. C'est un indice favorable,
**pas une identification certaine** : une semaine négative subsiste par PF et
les contradictions avec le CA restent présentes.

### Les valorisations ne permettent pas d'inventer un stock usine

L'Excel valorise les PF à un taux fixe de **0,50035** pour Cicalfate et **2,43404**
pour Permixon par unité. Le quotient entre la valeur CSV et la quantité Muret
varie respectivement de 0,47522 à 0,60673 et de 2,26334 à 2,36986.
Les agrégats de composants ne correspondent pas non plus exactement aux sommes
détaillées des sites candidats.

Un résidu financier peut venir du coût utilisé, du périmètre, de la date ou
d'un autre stock. **Il ne suffit pas à calculer un stock de PF à Avène ou Gien.**
Il faudrait le stock initial usine, la production effectivement terminée et les
départs physiques, ou une ventilation financière et un coût unitaire confirmés.

### Autres points à garder visibles

- Sur les intervalles **16→23 juin et 23→30 juin**, **18 couples article/site**
  ont des écarts opposés qui se compensent. 773474/Gaillac présente séparément
  deux écarts de −3 200 kg avec ses entrées brutes. Un décalage de comptabilisation
  ou de photo est plausible pour les écarts opposés ; aucune cause industrielle
  commune n'est prouvée.
- Les lignes **63 et 66** des en-cours sont identiques : 049371/Avène, 1 800 kg,
  livraison 17 janvier, entrée 29 janvier. Sans numéro d'ordre, ce peut être deux
  commandes égales ou un doublon d'export. Ne pas en supprimer une automatiquement.
- Le site **1820** figure dans les en-cours : ne pas le fusionner avec 1810 sans
  correspondance documentée.
- Les acteurs utilisent D1920 pour Muret, certaines relations DC-D1910/DC-1910.
  Ce sont des incohérences d'identifiant à résoudre dans la normalisation.
- Les trajets de demand_PF concernent des exemples internationaux ; ils ne
  documentent pas les délais réels Gaillac–Gien ou usine–Muret.

## 6. Achats et contexte fournisseur

Les FIA donnent **35 conditions article/fournisseur**. Elles permettent de
comparer prix ramenés à une même unité, délai annoncé et quantité standard.
Une quantité standard ne démontre pas, à elle seule, un minimum obligatoire ou
un multiple imposé. Le calendrier des délais FIA n'est pas explicité dans la
colonne « jours », contrairement aux jours ouvrés de sécurité.

Pour 001848, les deux conditions confirment : **1,58 EUR/kg, 56 jours, 6 000 kg**
chez VD0951020A, et **4,20 EUR/kg, 21 jours, 4 000 kg** chez VD0519670A.
L'utilisateur a confirmé principal économique/secours rapide pour ce cas.
Les conditions de prix/délai peuvent guider une règle commune candidate ; elles
ne prouvent pas une préférence automatique identique pour tous les achats.

Les audits fournisseurs partagent un même identifiant VD0993480A marqué
« Simulation », mais des en-têtes RAJA/FABRE et des réponses différents. Les
337 différences de cellules incluent des réponses et scores. Les dates et
l'auditeur sont vides ; leurs scores ne sont donc pas des probabilités de panne
mesurées pour les 29 fournisseurs du modèle.

Les 31 pièces publiques stockées couvrent 20 fournisseurs et plusieurs types
de faits, souvent à l'échelle d'un groupe plutôt que du site fournisseur exact.
Quatre lignes de proxies ont `source_count = 0`. Des pièces sont datées de
fin 2025 ou 2026 : elles ne peuvent pas être utilisées comme une connaissance
disponible en janvier 2025. Cette passe a vérifié **le contenu local et ses
liaisons**, pas l'actualité des pages Internet ni la véracité externe de chaque
affirmation. Les scores de confiance sont des appréciations, pas des intervalles
statistiques estimés sur des retards industriels.

Le graphe `supply_graph_poc.json` contient **203 indicateurs de valeur par défaut**,
des délais de transport de cinq jours et des stocks PF usine nuls par défaut.
Il conserve aussi des mentions de fichiers anciens. Il faut remonter aux Excel
pour attribuer une valeur à l'industriel. Ce graphe historique ne représente pas
nécessairement l'état de la référence demande/DC actuellement figée.

## 7. Quelle source utiliser pour quelle question ?

| Question | Source prioritaire et règle de lecture |
|---|---|
| Combien de matière est physiquement présente ? | Photos Stocks, article/site/date/unité ; ne pas remplacer une absence par zéro. |
| Qu'est-ce qui a fait varier le stock ? | Mouvements signés rapprochés des photos ; conserver les exceptions identifiées. |
| Qu'était-il prévu de recevoir ou consommer ? | Une version datée du Flow MRP ; distinguer J existant de H entrant. |
| Quels engagements existaient au démarrage ? | En-cours avec leurs dates explicites ; éviter de les commander une seconde fois. |
| Quelle demande prévoir à une date donnée ? | Dernière version Flow Customer connue à cette date et couvrant la semaine. |
| Quelle demande est injectée dans la référence acceptée ? | demand_PF avec convention négatifs à zéro, inchangée ici. |
| Quelle consommation théorique pour produire ? | BOM primaires, coefficient et unité ; registre physique séparé pour la consommation exécutée. |
| Quel fournisseur, prix et lot standard ? | FIA primaires ; copies Data_poc/demand_PF comme contrôle, pas nouvelle preuve. |
| Quelle sécurité et quelle taille de fabrication ? | Ancienne et nouvelle politique conservées avec la version choisie ; date d'effet industrielle inconnue. |
| Quel service financier a été réalisé ? | CA livré/perdu signé sur le même intervalle ; aucun mélange avec un taux physique ou projeté. |
| Quel risque fournisseur ? | Audit/contexte et dates propres ; ne pas confondre proxy et fréquence mesurée. |

Les conventions confirmées restent séparées des données : quantités physiques
UN entières ; sécurité et réception en jours ouvrés lundi–vendredi ; contrôle
des PF à l'usine avant expédition ; fermeture Avène du 4 au 15 août ; Gaillac
fabricant de 693055 sans BOM amont fournie ; `tau_process` reste une convention
de planification. L'indication d'environ un an de stock sur la chaîne Permixon
est un objectif de chaîne, pas un an à imposer séparément à chaque nœud.

## 8. Ordre de travail recommandé après cet audit

1. **Fiabiliser les comparaisons physiques** : mêmes intervalles, mêmes unités,
   sorties additives, traitement séparé de l'anomalie 773474/Gaillac et des
   décalages de juin. Cela évite de calibrer le moteur contre un total incohérent.
2. **Tester le calendrier des en-cours**, sans perdre les dates explicites des
   engagements, puis comparer les effets aux autres références.
3. **Résoudre le rapprochement BOM/scan3** par groupes matières/conditionnement,
   sans coefficient arbitraire ni déclaration de partage non démontrée.
4. **Versionner les politiques et la prévision** : dire quelle règle était
   disponible à quelle date, au lieu de mélanger paramètres actuels et année 2025.
5. **Reprendre ensuite les essais MRP annuels**, avec comparaison de toutes les
   références et conservation de la référence demande/DC. Aucun de ces essais
   n'a été lancé dans cette passe de connaissance.

## 9. Preuves et entretien de cette connaissance

Le [registre durable](reference/source_knowledge.json) conserve le catalogue,
les 22 empreintes, les paramètres extraits, les conclusions et leurs limites.
Il rassemble les résultats pour éviter une collection de nouvelles notes.
Le [dossier local de preuves](../artifacts/testing/source_knowledge_20261008/)
contient les six rapports détaillés et les calculs de cette passe.

Les contrôles exécutés sont des lectures de sources, calculs en mémoire,
rapprochements indépendants et vérifications d'empreintes. Le rapport
demande/finance a été reproduit sans différence sur ses 22 sections contrôlées.
Le facteur deux et le calendrier ont été contre-vérifiés par un agent distinct.
Le [doctor](../artifacts/testing/toolbox/doctor-78120460a26b42faaf346acd83087458/manifest.json)
est passé ; il vérifie l'environnement, pas la calibration industrielle.
Le [manifeste final](../artifacts/testing/source_knowledge_20261008/manifest.json)
consigne les empreintes finales et les documents produits.

**Non exécutés :** simulation, tests globaux, navigateur, recalcul Excel,
rafraîchissement des preuves Internet et tests altérant volontairement des
fichiers. Rien de cela n'est compté comme une vérification réussie.

À la réception d'un nouveau fichier, comparer son contenu métier et ses dates,
pas seulement son nom ou sa date de modification. Mettre à jour ce document et
le registre ; conserver une conclusion ancienne comme historique lorsqu'une
cellule source a changé. Une empreinte différente signale la nécessité d'un
nouveau rapprochement, pas automatiquement une erreur du fichier.
