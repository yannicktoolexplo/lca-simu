# Refaire le MRP : des clients jusqu’aux fournisseurs

Ce guide explique **ce que fait le programme actuel**, avec des mots simples,
puis les calculs nécessaires pour le reconstruire. Il décrit la référence
`coherent-MRP-20261014`, relue sur le commit `38264f0f2` le 9 novembre 2026.
Il ne prétend pas que cette référence reproduit déjà les courbes industrielles.

**La phrase la plus importante :** le MRP prépare les choses avant qu’elles
manquent. Il calcule quoi fabriquer, quoi déplacer, quoi acheter et quand.
Un plan n’est pas encore une fabrication, un camion ou une livraison.

Deux lectures sont possibles : les phrases et les exemples pour comprendre ;
les formules, les tableaux et l’algorithme pour programmer. Tous les exemples
inventés sont signalés. Les articles sont désignés par leurs codes.

## 1. Le chemin, très simplement

Imagine cinq étagères : chez le client, à Muret, dans une usine de produits
finis, à Gaillac, puis chez les fournisseurs.

**Les questions remontent de l’aval vers l’amont :**

```text
Clients : « combien allez-vous demander ? »
  → Muret : « que reste-t-il à recevoir pour vous couvrir ? »
  → Avène ou Gien : « quels produits finis devons-nous fabriquer ? »
  → Composants et Gaillac : « quelles matières devons-nous rendre disponibles ? »
  → Fournisseurs : « quoi commander et à quelle date ? »
```

**Les produits se déplacent dans le sens inverse :**

```text
Fournisseurs → matières utilisables → fabrication
  → transport → contrôle à réception → Muret
  → transport → client → demande servie
```

| Lieu dans ce guide | Identifiant dans les données | Fonction |
|---|---|---|
| Client représenté | `C-XXXXX` | Reçoit les produits finis et consomme la demande arrivée |
| Muret | `DC-1920` | Centre de distribution des deux produits finis |
| Avène | `M-1810` | Fabrique le produit fini `268091` |
| Gien | `M-1430` | Fabrique le produit fini `268967` |
| Gaillac | `SDC-1450` | Fabrique les semi-finis `693055` et `773474` |
| Fournisseur | Identifiant commençant par `SDC-VD` | Reçoit une commande d’un composant acheté |

Un **produit fini**, abrégé PF, est ce que le client demande. Un **semi-fini**
est un produit fabriqué qui sert de composant à une autre fabrication.
Une **nomenclature**, appelée BOM dans les fichiers, est la recette chiffrée.
Un **ordre de fabrication**, abrégé OF, est un engagement de fabrication.

## 2. Oui : les produits finis partent directement vers Muret

Dans cette référence, après achèvement d’un lot de PF à l’usine, la quantité
utilisable est expédiée vers Muret **sans attendre que Muret redemande ce lot**.
La règle est appelée `push_released_available_v1`.

```text
Quantité à envoyer à Muret = tout le stock utilisable de PF à l’usine
```

Cela exclut les produits encore en fabrication, bloqués ou déjà réservés.
Les deux routes usine–Muret ont une revue quotidienne, une fiabilité nominale
de 1 et aucun multiple physique de chargement imposé. Un lot terminé dans la
journée peut donc partir ce même jour, sous réserve des contraintes physiques.
Ce départ n’est pas conditionné par un seuil de stock à Muret.

**Directement ne veut pas dire instantanément :**

| PF | Après la fin du lot | Transport jusqu’à Muret | Puis blocage à Muret |
|---|---|---|---|
| `268091` | Départ possible le jour même | 2 jours calendaires dans l’exécution nominale | 10 jours lundi–vendredi après réception |
| `268967` | Départ possible le jour même | 2 jours calendaires dans l’exécution nominale | 15 jours lundi–vendredi après réception |

Les routes portent une valeur de 2,5 jours dans le graphe. L’arrondi Python
utilisé ici donne `round(2.5) = 2`, pas 3. Le nominal désactive le tirage
aléatoire des délais. Il faut conserver cette convention pour refaire ce calcul.

Le contrôle est à **Muret**, après le transport. On ne rajoute pas ces 10 ou
15 jours à l’usine. À la libération, le même lot devient utilisable : aucun
deuxième camion, aucune deuxième fabrication ni nouvelle consommation matière.

Exemple de calendrier : un PF reçu à Muret un mercredi avec un traitement de
10 jours lundi–vendredi devient utilisable le mercredi deux semaines plus tard.
Le mercredi de réception n’est pas compté parmi les 10 jours.

## 3. Les mots et les unités à ne jamais mélanger

### 3.1 Les différentes boîtes du stock

| Nom utilisé dans les formules | Ce qu’il contient | Peut être consommé ou expédié maintenant ? |
|---|---|---|
| `Libre` | Produit présent, libéré et non réservé | Oui |
| `Bloqué` | Produit présent, mais pas encore utilisable | Non |
| `Réservé` | Produit présent et affecté à un mouvement futur | Non pour une autre décision |
| `Physique` | Tout le produit présent sur le site | Seulement sa partie libre |
| `Transit` | Produit parti, pas encore physiquement reçu | Non |
| `Encours` | Travail déjà fait dans un lot inachevé | Non |
| `Ferme` | Ordre engagé, avec quantité et date de disponibilité | Couvre le plan ; pas utilisable tout de suite |
| `Proposition` | Ordre calculé mais encore révisable | Non |

```text
Physique = Libre + Bloqué + Réservé
```

`Transit` et `Encours` ne sont pas ajoutés à cette égalité de stock sur site.
Les quantités réservées ne sont pas soustraites une deuxième fois d’une valeur
`Libre` qui les exclut déjà. Chaque quantité possède un seul état physique.

### 3.2 Quantités et arrondis

`UN` signifie unité physique entière, `G` gramme, `KG` kilogramme et `M` mètre.
Une unité de produit fini n’est ni un kilogramme ni une palette.

```text
1 KG = 1 000 G
quantité_en_KG = quantité_en_G / 1 000
quantité_en_G = quantité_en_KG × 1 000
```

Le moteur ne déduit pas une conversion entre masse et volume sans donnée de
densité. Les coefficients de recette sont convertis dans l’unité du stock
du composant avant tout calcul.

| Opération | Arrondi |
|---|---|
| Prévision et calcul intermédiaire | Les fractions sont autorisées |
| PF physiquement servi ou expédié | Partie entière inférieure de la quantité faisable |
| Quantité de commande en UN | Entier supérieur, puis règle de lot |
| Composant UN consommé par une opération de fabrication | Entier supérieur du besoin de cette opération |
| Besoin net d’achat en masse | Kg le plus proche, moitié vers le haut ; quantum 1 000 G si le stock est en G |

Les stocks, les recettes et les mouvements en masse ne sont pas tous arrondis
au kg : cet arrondi concerne la **décision nette d’achat**. Son résidu est
reporté au besoin suivant. Pour éviter de créer un lot à cause d’une erreur
de virgule flottante, le noyau de netting utilise une arithmétique décimale.

### 3.3 Comment lire les formules

| Écriture | Définition |
|---|---|
| `t` | Jour où l’on décide, donc « aujourd’hui » |
| `d` | Date future d’un besoin |
| `j` | Jour parcouru dans une somme |
| `n` | Site, par exemple Muret |
| `a` | Article quelconque |
| `p` | Article parent fabriqué |
| `c` | Composant de cet article parent |
| `f` | Fournisseur |
| `w` | Semaine civile lundi–dimanche |
| `x[d sachant t]` | Valeur pour la date `d`, avec les seules informations connues à `t` |
| `somme(...)` | Additionner toutes les valeurs de l’ensemble indiqué |
| `max(0, x)` | Garder `x` s’il est positif ; sinon prendre zéro |
| `min(x, y)` | Prendre le plus petit |
| `ceil(x)` | Arrondir à l’entier supérieur |
| `floor(x)` | Prendre l’entier inférieur |

Chaque quantité d’une même formule doit avoir la même unité. Sauf indication
contraire, les formules d’un paragraphe portent sur **le même article au même
site**. On ne retire jamais le stock d’Avène d’un besoin de Muret sans un
transfert daté entre les deux.

## 4. Le temps : une date pour chaque événement

Les jours du modèle sont des entiers : jour 0 = mercredi 1er janvier 2025.
Le MRP regarde **364 jours futurs**, même pour une exécution de seulement
56 jours. Fin d’exécution et fin d’horizon de planification sont distinctes.

| Date | Sens |
|---|---|
| Date du besoin | Jour où l’article doit être utilisable |
| Date de commande | Achat effectivement engagé chez un fournisseur |
| Date de lancement | Campagne de fabrication engagée ou transfert lancé |
| Date de travail | Jour d’une consommation réelle de composants |
| Date de fin de lot | Jour où le lot entier devient un produit physique |
| Date de départ | Débit physique du site expéditeur |
| Date de réception | Entrée physique au site destinataire |
| Date disponible | Fin du blocage ; l’article peut être utilisé |
| Date de connaissance | Premier jour où l’information est admise dans la décision |

**Jours calendaires :** lundi, mardi, mercredi, jeudi, vendredi, samedi, dimanche.
**Jours lundi–vendredi :** on saute samedi et dimanche. Aucun calendrier de
jours fériés industriels n’est ajouté sans source.

```text
AjouterOuvrés(date, nombre)
  = avancer après cette date jusqu’à avoir rencontré « nombre » jours lundi–vendredi

RetirerOuvrés(date, nombre)
  = reculer avant cette date en ne comptant que lundi–vendredi
```

Le jour de réception est exclu du décompte du traitement. Avec un délai nul,
la disponibilité reste le jour de réception. Exemple : reçu vendredi,
traitement 2 jours ouvrés → disponible mardi.

Trois « semaines » différentes sont présentes :

| Usage | Calendrier exact |
|---|---|
| Demande et versions MRP | Semaines civiles lundi–dimanche |
| Quota des lots de fabrication | Tranches jour 0–6, 7–13, etc., donc ancrées au mercredi initial |
| Revues de certaines routes internes | Jours dont le numéro est divisible par 7, donc mercredi dans cette origine |

## 5. Au départ : on reprend les stocks et les engagements existants

Le calcul ne part pas d’étagères arbitrairement pleines. Il reprend une seule
fois les stocks source et les ordres déjà ouverts. L’échelle initiale active
vaut 1 ; les ajouts automatiques de stocks et de transit estimé sont désactivés.

| Couple | Stock physique initial configuré |
|---|---:|
| `268091` / Muret | 430 538 UN |
| `268967` / Muret | 1 101 534 UN |
| PF à leurs usines et chez le client | 0 UN |
| `693055` / Gaillac | 1 800 KG |
| `773474` / Gaillac | 9 600 KG |

Le physique initial n’est pas forcément libre. Des positions MRP du 5 janvier
sont utilisées, par hypothèse explicite, pour séparer le libre et le bloqué dès
le 1er janvier. Une date de libération inconnue reste inconnue.
Exemple `693055` à Gaillac : 590 KG utilisables, 1 200 KG bloqués jusqu’au
12 janvier, 10 KG sans date de disponibilité connue.

Les 91 lignes présentes dans le carnet configuré comprennent 69 achats et
22 productions, dont trois compléments hypothétiques au carnet extrait.
Les compteurs historiques « 104 lignes, 88 résolues, 16 non résolues » décrivent
l’extraction initiale, pas ces 91 lignes après compléments. Les lignes non
rattachées à un site ne sont pas affectées silencieusement à un autre site.

Chaque ordre initial conserve quantité, fournisseur si identifié, réception
physique et disponibilité source. Sa création ou son départ ne sont pas inventés.
Une arrivée moins un délai fournit au mieux une **date reconstruite** de commande.
Les dates explicites d’un ordre initial priment sur la politique générique de
réception. Ces ordres ne sont pas recréés chaque année ni refacturés à l’ouverture.

**Production initiale :** en mode `wip`, les composants déjà incorporés sont
considérés prélevés avant le début ; on ne les consomme pas à nouveau.
Exception : pour le conditionnement initial de `268091`, les composants
`338928`, `338929`, `426331` restent à prélever aux dates de conditionnement.
Ce travail consomme aussi de la capacité usine. Les arrondis UN sont calculés
sur le cumul de l’ordre, puis répartis entre fragments pour ne pas les répéter.

Les compléments de carnet et leurs limites sont repris en section 17.

## 6. Le client : demande arrivée et service simulé

### 6.1 Lire la demande hebdomadaire

Le chemin courant utilise `Flow_Data_Customer_Demand.xlsx` : feuille
`Historique`, colonne `Actual Demand`. Les sorties source doivent être des
entiers non positifs, puis le moteur change le signe :

```text
DemandeSemaine = − valeur_source_Actual_Demand
```

Une valeur positive, fractionnaire, absente ou non finie est refusée, pas
transformée silencieusement en zéro.

Le détail quotidien n’étant pas fourni, on répartit le total entier sur les
sept jours calendaires. Pour le jour `k` de la semaine, numéroté de 0 à 6 :

```text
DemandeJour[k] = floor(DemandeSemaine × (k + 1) / 7)
                − floor(DemandeSemaine × k / 7)
```

Exemple : 10 UN par semaine donnent `1, 1, 2, 1, 2, 1, 2`, total 10.
**Le total hebdomadaire vient du réel ; les dates quotidiennes sont reconstruites.**
Les portions de semaine hors de la période ne sont pas redistribuées.

### 6.2 Servir seulement ce qui est déjà chez le client

`RetardAvant` est la demande arrivée les jours précédents et non encore servie.
`DemandeJour` est la nouvelle demande arrivée aujourd’hui. `LibreClient` est
le produit utilisable **déjà reçu chez le client**.

```text
ÀServir = RetardAvant + DemandeJour
Servi = floor(min(LibreClient, ÀServir))
RetardAprès = ÀServir − Servi
LibreClientAprès = LibreClient − Servi
```

Exemple : retard 30, nouvelle demande 10, stock client 15 → il faut 40,
on sert 15 et il reste 25 en retard. Un camion encore entre Muret et le client
ne compte pas comme servi. Une prévision non réalisée ne devient pas du retard.

Le programme suit un retard agrégé par article/client. Cela ne constitue pas
un historique industriel de commandes clients individuellement identifiées.

### 6.3 Ce que Muret a le droit d’envoyer au client

La politique active est `known_demand_only_v1` : Muret expédie pour la demande
déjà arrivée, sans envoyer la prévision ni le stock de sécurité chez le client.
Après le service du jour :

```text
BesoinEnvoiClient = max(0,
    RetardAprès − LibreClientAprès
    − somme(quantités des envois client déjà engagés et encore ouverts))

DépartClient = floor(min(LibreMuret, BesoinEnvoiClient, autres limites physiques))
```

Un engagement ouvert est soustrait une seule fois, même s’il est tardif.
Le besoin est recalculé immédiatement avant le départ pour éviter un surplus.

Exemple : retard 25, client vide, 8 UN déjà en route → besoin de nouvel envoi
17. Si Muret n’a que 10 UN libres, départ 10. Les 7 restantes ne sont pas
transformées en camion fictif : elles restent à couvrir.

Le transport Muret–client dure 2 jours calendaires dans le nominal, avec revue
quotidienne et fiabilité 1. **Même si Muret a du stock, une nouvelle demande
connue aujourd’hui peut être servie deux jours plus tard.** Le MRP prépare le
stock à Muret ; la règle physique active n’anticipe pas les commandes chez le client.

## 7. Prévoir sans compter deux fois les commandes

### 7.1 Choisir la prévision connue

Une prévision possède une semaine cible et une version publiée. Pour une date
future, prendre la dernière version connue aujourd’hui qui renseigne cette date.
Une nouvelle version incomplète n’efface pas les anciennes dates qu’elle omet.
La date de connaissance source est le lundi de la semaine de publication :
l’heure de publication exacte n’est pas fournie.

Si la période n’a jamais été fournie, le programme prend la période la plus
proche de la dernière version connue ; en cas d’égalité, la plus ancienne.
C’est un repli estimé et tracé, pas une observation égale à zéro.

### 7.2 Retirer les commandes déjà arrivées cette semaine

`PrévisionSemaine` est la prévision hebdomadaire connue. `CommandesDéjàArrivées`
est le cumul de la demande physique de cette semaine jusqu’à aujourd’hui.
`JoursRestants` compte les jours calendaires strictement après aujourd’hui
et avant la fin de cette semaine.

```text
PrévisionRestante = max(0, PrévisionSemaine − CommandesDéjàArrivées)
PrévisionJourFutur = PrévisionRestante / JoursRestants
```

Exemple : prévu 700, reçu en commandes 360 lundi–mercredi → restant 340,
réparti jeudi–dimanche à 85 par jour. Si les commandes ont déjà atteint 750,
la prévision restante est zéro. On retire les commandes arrivées, **pas les
livraisons**. Une commande en retard a déjà consommé sa part de prévision.

Quand aucun jour ne reste, le reliquat prévisionnel expire. Pour la première
semaine partielle, le moteur ne reconstruit pas une demande antérieure inconnue.

### 7.3 Construire les besoins futurs

À la fin du jour `t`, pour chaque date `d` entre `t+1` et `t+364` :

```text
BesoinClient[d] = PrévisionJourFutur[d | t]
BesoinClient[t+1] = BesoinClient[t+1] + RetardAprès
```

Le retard est ajouté **une seule fois**, au premier jour futur. Le plan remonte
ensuite client → Muret → usine. Une nouvelle proposition aval crée un besoin
amont à sa **date de lancement**, pas à la date de consommation finale du client.
Le stock et les engagements déjà couvrants ne sont pas redemandés à l’amont.

## 8. Le calcul commun : stock, engagements et nouvelles propositions

Ce calcul est utilisé à plusieurs étages. Son nom technique est le **netting** :
« qu’est-ce qui manque après avoir utilisé ce qui existe ou arrive déjà ? »

### 8.1 Les ressources admises

1. Le stock libre maintenant.
2. Les ordres engagés, à leur date disponible : confirmations, transit, stock
   reçu mais encore bloqué, production déjà engagée.
3. Le surplus des propositions déjà calculées dans le même plan.

Un stock bloqué sans date de libération connue n’est pas une réception future
datée inventée. Une proposition ne devient pas un engagement physique.

### 8.2 Affecter chaque quantité une fois

Trier les besoins par `(date, identifiant)` et les ressources par
`(date disponible, identifiant)`. Affecter les plus anciennes ressources aux
plus anciens besoins. C’est une affectation premier besoin–première ressource,
souvent appelée FIFO.

**Le moteur conserve aussi les réceptions fermes tardives.** Elles couvrent
leur besoin avec un retard ; il ne rachète pas automatiquement la même quantité.

```text
ResteAprèsFermes[d] = max(0, BesoinProtégé[d] − QuantitéAllouéeDepuisFermes[d])
BesoinNet[d] = max(0, ResteAprèsFermes[d] − SurplusEncoreDisponible[d])

RetardAllocation = max(0, DateDisponibleRessource − DateBesoin)
UnitésJoursRetard = somme(QuantitéAllouée × RetardAllocation)
```

Exemple : besoin 10 mardi, 5 en stock, 5 déjà commandées pour vendredi →
aucune nouvelle commande. Les 5 reçues vendredi couvrent avec 3 jours de retard,
soit 15 unités-jours. Cette couverture de plan ne les rend pas utilisables mardi.

### 8.3 Créer une proposition seulement pour le reste

Lotifier le besoin net, affecter le lot au besoin et conserver son surplus
pour les besoins suivants. Refaire les allocations avec les propositions pour
calculer leurs véritables dates et retards.

Exemple inventé : besoins successifs 3 et 6, lot minimum 10, aucune ressource →
une proposition de 10 couvre les deux, surplus final 1. Pas deux commandes de 10.

**Ne pas remplacer tout cela par une simple soustraction de totaux annuels :**
10 unités arrivant en juin ne sont pas disponibles en février.

## 9. Muret : pourquoi une réserve de sécurité ne devient pas une vente

Les sécurités actives de Muret sont **20 jours lundi–vendredi pour `268091`**
et **25 pour `268967`**. Le facteur nominal vaut 100 %. La réserve fixe de
ces deux PF à Muret vaut zéro. Le client n’a pas de réserve propre dans le plan
actif, même si un ancien champ du scénario porte 14 jours.

### 9.1 Calculer la réserve future

`N` est le nombre de jours de sécurité. `FinSécurité(d,N)` est la date obtenue
en avançant de N jours lundi–vendredi après `d`. `Fixe` est la sécurité fixe.

```text
Plancher[d] = max(Fixe,
    somme(BesoinBrut[j] pour d < j ≤ FinSécurité(d,N)))
```

Les besoins du samedi et du dimanche compris entre les deux bornes sont inclus.
Le calendrier ouvré sert à trouver la borne de fin, pas à effacer les demandes
du week-end. Le besoin du jour `d` n’est pas ajouté dans sa propre réserve.
Si la fenêtre dépasse les prévisions connues, le programme utilise le plancher
de repli constant, pas zéro.

### 9.2 Ne pas rajouter la réserve chaque jour

`Cumul[d]` est le total des besoins bruts jusqu’à `d`. `Enveloppe[d]` est le
total protégé, qui ne redescend pas. Sa valeur avant le premier point vaut zéro.

```text
Cumul[d] = somme(BesoinBrut[j] pour j ≤ d)
Enveloppe[d] = max(Enveloppe[point précédent], Cumul[d] + Plancher[d])
BesoinProtégé[d] = Enveloppe[d] − Enveloppe[point précédent]
```

Exemple inventé : besoins 10 puis 10 ; planchers 20 puis 10.
Les enveloppes sont 30 puis 30. Les tranches à couvrir sont 30 puis 0,
pas 30 puis 20. La réserve n’est donc pas commandée deux fois.

Après le calcul des propositions sur cette enveloppe, le moteur refait les
bilans sur les **besoins physiques originaux**. La réserve ne consomme rien.

Le repli est constant **dans le snapshot calculé aujourd’hui**. Il est
recalculé au prochain jour de décision. Pour le reproduire :

```text
DuréeSécuritéCalendaire = nombre de jours écoulés après t
                         pour rencontrer N jours lundi–vendredi
W = ceil(DuréeSécuritéCalendaire)
Repli = max(Fixe, somme(BesoinBrut[j] pour t < j ≤ t + W))
```

Le jour de semaine de `t` vaut `(2 + t) % 7`, avec lundi = 0 et mercredi = 2.
On avance après `t` ; un samedi ou dimanche ajoute un jour écoulé sans consommer
un jour de sécurité. Si N est fractionnaire, le dernier jour ouvré contribue
sa fraction, puis `ceil` borne la fenêtre. Les paramètres source du tableau
sont entiers. Exemple : vendredi, N = 1 → durée calendaire 3, jusqu’au lundi.
L’implémentation est `simulation/engine/model_semantics.py:safety_calendar_days`.

## 10. L’usine : planifier un OF, puis réellement fabriquer

### 10.1 Le plan daté commande le lancement

Chaque soir, le programme calcule les besoins datés de PF, les stocks,
engagements, protections et lots. Le lendemain, il re-net ce snapshot avec les
quantités réellement disponibles pour autoriser un lancement.

```text
ÀLancerAujourd’hui = somme(propositions admissibles
                           dont DateLancement ≤ aujourd’hui)
```

Une campagne active poursuit d’abord son exécution. On ne crée pas simplement
une autre campagne parce qu’une première est bloquée. Au jour 0, il n’existe
pas de snapshot de la veille : pas de nouvelle campagne normale ; les ordres
d’ouverture ont leur propre parcours.

Un signal préparatoire lissé existe aussi :

```text
IntentionBrute = SignalAval + 0,25 × (CibleLocale − StockLocalReconnu)
IntentionLissée = 0,20 × IntentionLisséePrécédente + 0,80 × IntentionBrute
```

`SignalAval` est le maximum du signal aval propagé et du signal prévisionnel
multiniveau. `CibleLocale` est le maximum des protections locales configurées.
La couverture PF générique active vaut zéro ; les sécurités source subsistent.
**Cette intention locale n’autorise pas directement les OF : le plan daté la
remplace pour les lancements.** Le feedback additionnant directement la cible
usine et la cible/stock Muret est désactivé.

### 10.2 Combien mettre dans chaque lot ?

Si le besoin net est nul, ne créer aucun lot, même s’il existe un minimum.
Pour un besoin strictement positif et un multiple strictement positif :

```text
MinimumEffectif = ceil(Minimum / Multiple) × Multiple
MaximumEffectif = floor(Maximum / Multiple) × Multiple    si Maximum défini
Lot = ceil(max(BesoinNet, MinimumEffectif) / Multiple) × Multiple
Lot = ceil(Lot)                                         si unité UN
Lot = min(Lot, MaximumEffectif)                         si Maximum défini
```

Sans multiple, omettre les opérations de multiple. Pour un lot fixe :

```text
NombreLots = ceil(BesoinNet / LotFixe)
QuantitéCampagne = NombreLots × LotFixe
```

Un maximum borne un lot ou une campagne selon la couche, **pas tout le besoin
de la journée**. Le plan daté crée plusieurs propositions si nécessaire et
réutilise les surplus. Une configuration de minimum/multiple/maximum impossible
est refusée.

| Fabrication | Lot actif | Capacité de travail par jour | Quota de lancement |
|---|---|---:|---:|
| `268091` / Avène | Minimum 28 800 ; multiple 14 400 ; maximum déclaré 142 485 UN, réalisable 129 600 UN | 203 550 UN/jour | 20 lots par tranche de 7 jours du modèle |
| `268967` / Gien | Lot fixe 107 800 UN | 154 000 UN/jour | 20 |
| `773474` / Gaillac | Lot fixe 3 200 KG | Non modélisée | 20 |
| `693055` / Gaillac | Lot fixe 600 KG | Non modélisée | Pas de plafond hebdomadaire configuré |

Exemple : besoin net 130 000 UN de `268091`. Le maximum réalisable est
`floor(142485 / 14400) × 14400 = 129600`. Le plan peut proposer 129 600,
puis au moins 28 800 pour couvrir le reliquat. Il ne coupe pas le besoin total
à 129 600. Une nouvelle campagne variable reste plafonnée à 129 600.

Le quota de 20 compte les lots engagés lors du lancement, pas uniquement les
lots terminés. La tranche vaut `floor(jour / 7)` : elle ne commence pas le lundi.

### 10.3 Le travail est limité par ce qui existe réellement

`Recette[c,p]` est la quantité du composant c par unité du parent p.

```text
PossibleParComposant[c] = LibreComposant[c] / Recette[c,p]
PossibleParMatières = min(PossibleParComposant[c] pour chaque composant requis)
CapacitéRestante = CapacitéJour − TravailDéjàFait − ConditionnementInitialDuJour

TravailExécuté = min(ResteDuLotPhysique, CapacitéRestante, PossibleParMatières)
```

Le moteur réduit si nécessaire le travail jusqu’à une quantité physiquement
réalisable après arrondis des composants UN. Les fabrications se disputent un
même stock de composant : on ne réutilise pas la même matière deux fois.

À Gaillac, une capacité absente est traitée comme **non limitante** dans ce
calcul, sauf arrêt explicite. Ce n’est pas une capacité industrielle infinie
démontrée. Les matières, les lots et le signal continuent de limiter l’exécution.

Le travail déjà fait s’accumule dans l’encours. **Le lot de sortie n’existe
physiquement que quand son objectif complet est atteint.** Les composants
sont consommés lors du travail, pas lors d’une simple réservation.

La politique intrajournalière active autorise le lot physique suivant de la
**même campagne** s’il reste matière et capacité. Elle ne crée pas automatiquement
une seconde campagne indépendante ni un second quota dans la journée.

### 10.4 Ce que le programme ne doit pas laisser croire

- `tau_process = 3` est une **marge de planification** pour dater les propositions.
  Ce n’est pas une attente physique obligatoire de trois jours après fabrication.
- Le calcul des dates n’est pas un ordonnancement complet à capacité finie.
- Une campagne et son quota peuvent être engagés avant qu’un travail positif
  soit réalisé. La variante attendant le premier prélèvement existe dans le
  code, mais n’est pas activée dans ce bundle.
- Avène est fermé du 4 au 15 août 2025. La fermeture prospective est une
  hypothèse distincte, décrite en section 20.

## 11. La recette : passer du produit fini aux composants

### 11.1 Le coefficient par unité

`QuantitéBaseParent` est la quantité de parent à laquelle la recette se rapporte.
`QuantitéRecette` est la quantité de composant indiquée pour cette base.

```text
Recette[c,p] = convertir_dans_unité_du_stock_composant(
                  QuantitéRecette[c,p] / QuantitéBaseParent[p])

BesoinRecette[c,d] = somme(QuantitéNouvellePropositionParent[p,d]
                           × Recette[c,p])
```

La date de besoin du composant est la date de lancement proposée du parent.
Pour une campagne déjà engagée, les composants du travail encore à faire sont
demandés une fois au prochain jour ; les composants déjà incorporés à l’encours
ne sont pas demandés à nouveau.

```text
BesoinCampagneRestante[c,t+1] = ResteÀExécuterParent × Recette[c,p]
RéceptionFermeSortieCampagne = ResteÀExécuterParent + EncoursDéjàExécuté
```

Une passe amont→aval retarde ensuite la promesse de fin d’une campagne si ses
composants alloués arrivent tard. Elle ne crée pas du stock et ne remplace pas
le contrôle physique du jour. Si ce décalage change les propositions et rend
l’explosion obsolète, le programme échoue plutôt que conserver un plan incohérent.

### 11.2 Le prélèvement n’est pas toujours la simple théorie globale

```text
ConsommationThéorique[c] = TravailExécutéParent × Recette[c,p]
PrélèvementPhysique[c] = ceil(ConsommationThéorique[c])   si composant UN
PrélèvementPhysique[c] = ConsommationThéorique[c]         si masse ou longueur
```

Le plafond UN s’applique par opération. Un lot fractionné en plusieurs
opérations peut donc consommer plus d’UN que l’arrondi d’une théorie globale.
Les deux quantités doivent rester visibles.

Exemple réel de paramètres pour une campagne de 129 600 UN de `268091` :

```text
693055 : 129600 × 406 / 1000 G = 52617,6 G = 52,6176 KG
001757 : 129600 × 1624 / 1000 G = 210,4704 KG
426331 : 129600 × 11 / 1000 UN = 1425,6 UN théoriques
         → 1426 UN prélevées si l’opération se fait en un seul passage
```

Proposer un transfert de 600 KG de `693055` ne veut donc pas dire que cette
campagne consomme 600 KG. Le surplus restera dans le stock commun.

### 11.3 Recettes actives des deux produits finis

Toutes les valeurs suivantes sont pour **1 000 UN de parent**.

| Composant de `268091` | Quantité de recette | Unité |
|---|---:|---|
| 001757 | 1 624 | G |
| 001848 | 1 218 | G |
| 001893 | 7,714 | KG |
| 002612 | 2,03 | KG |
| 016332 | 487,2 | G |
| 029313 | 40,6 | G |
| 039668 | 40,6 | G |
| 049371 | 1 502,2 | G |
| 055703 | 81,2 | G |
| 099439 | 2 030 | G |
| 693055 | 406 | G |
| 007923 | 3 248 | G |
| 338928 | 1 000 | UN |
| 338929 | 1 000 | UN |
| 426331 | 11 | UN |

| Composant de `268967` | Quantité de recette | Unité |
|---|---:|---|
| 038005 | 17 499,176 | G |
| 042342 | 60 342 | UN |
| 773474 | 9 654,718 | G |
| 333362 | 1 000 | UN |
| 344135 | 1 000 | UN |
| 708073 | 7 930 | G |
| 730384 | 212 | M |
| 734545 | 8 | UN |

Les formats supplémentaires confirmés ne justifient aucun facteur global de
4,55 ou de 5 appliqué à ces recettes. Leur ventilation n’est pas connue.

## 12. Plusieurs produits utilisent la même matière

La règle de base est de sommer les besoins distincts au même article/site :

```text
BesoinComposantTotal = BesoinRecetteDesProduitsModélisés + AutresUsagesDistincts
```

Ils partagent le même stock. La fabrication des produits modélisés est servie
avant les autres usages. Les autres usages peuvent donc avoir leur propre
retard sans que la recette des PF change.

Leurs demandes physiques sont des entrées datées de la table
`observed_external_component_demands`, avec provenance et conventions de
répartition. Elles ne sont pas obtenues en prenant une lettre de colonne MRP
pour une sortie réelle. Les besoins prévus, les mouvements enregistrés et
les résiduels de rapprochement ci-dessous gardent des rôles distincts.

**Mais la référence conservée comporte aussi deux adaptations historiques
actives. Il faut les reproduire pour retrouver son calcul, ou déclarer qu’on
construit un autre modèle.** Elles ne sont pas des règles universelles du MRP.

### 12.1 Réconciliation de planification E4

Sur neuf couples du protocole, le plan utilise le maximum du besoin propre
calculé et du besoin industriel de la dernière version connue, **pour chaque
fenêtre hebdomadaire couverte et chaque article/site** :

```text
ComplémentPlanifié = max(0, BesoinIndustrielConnu − BesoinPropre)
BesoinPlanifié = BesoinPropre + ComplémentPlanifié
               = max(BesoinPropre, BesoinIndustrielConnu)
```

Les réserves restent séparées. Ce complément de plan n’est pas une consommation
physique ajoutée immédiatement au stock. Le maximum ne se calcule ni séparément
chaque jour ni sur l’horizon annuel entier. Hors des fenêtres source couvertes,
les besoins existants restent inchangés.
Le complément est réparti sur les jours futurs couverts de la fenêtre :
`ComplémentJour = ComplémentPlanifié / NombreJoursCouverts`, avec conservation
du total dans l’arithmétique utilisée. Les besoins propres existants gardent
leurs dates ; ce sont les autres besoins prévisionnels remplacés qui changent.

### 12.2 Réconciliation physique historique F3

Le mode par défaut `legacy_residual` peut demander en clôture du dimanche un
complément de consommation pour rapprocher les budgets hebdomadaires enregistrés
et la BOM déjà réellement exécutée. La colonne source appelée
`Sorties_article_scan3` est explicitement une mesure de consommation enregistrée,
pas une production certaine de PF.

Pour un budget hebdomadaire non cumulatif :

```text
NouveauRésiduel = max(0, BudgetScan3Semaine − ConsommationPropreSemaine)
```

Pour les couples cumulatifs du protocole :

```text
NouveauRésiduel = max(0,
    BudgetScan3Cumulé − ConsommationPropreCumulée − RésiduelsDéjàDemandés)
```

`RésiduelsDéjàDemandés` comprend aussi ceux qui attendent encore du stock.
Sinon, le programme redemanderait plusieurs fois le même déficit.
L’absence de budget ne vaut pas zéro et ne supprime pas le retard existant.
La première semaine partielle garde sa convention source explicite, sans
prorata automatique de 5/7.

Le mode `audit_only`, qui garde cet écart comme audit sans le prélever,
existe mais n’est pas le défaut livré. **Le calcul 2025 de cette référence
est donc un rapprochement historique assisté par des observations ; ce n’est
pas un rejeu industriel autonome.**

### 12.3 Programme industriel remplaçant certaines prévisions d’achat

Pour `338929` à Avène, `333362` et `042342` à Gien, dans les seules semaines
documentées, le programme industriel connu remplace les prévisions révocables.
Les besoins des campagnes déjà engagées restent datés :

```text
EngagéSemaine = somme(besoins composants déjà engagés de la semaine)
ComplémentSemaine = max(0, ProgrammeIndustrielSemaine − EngagéSemaine)
BesoinPlanifiéSemaine = max(EngagéSemaine, ProgrammeIndustrielSemaine)
```

Les autres besoins prévisionnels couverts sont retirés ; les réserves restent.
Hors semaine documentée, le modèle conserve ses besoins. Une semaine absente
n’est pas remplacée par zéro.
Le complément hebdomadaire est réparti de façon conservante entre les jours
de la fenêtre, sans déplacer les besoins des campagnes déjà engagées.

## 13. Gaillac : fabriquer puis transférer un semi-fini

### 13.1 Les deux recettes amont

`773474` utilise **8,94 KG de `021081` pour 1 000 G de sortie** dans le bundle.
Un lot de 3 200 KG implique donc 28 608 KG de `021081` selon cette recette.
Ce coefficient inhabituel est la donnée active ; le guide ne le remplace pas
par un rendement supposé.

La recette industrielle de `693055` n’est pas fournie. La simulation utilise
un jeton technique `VIRTUAL_693055_INPUT` par 600 000 G de sortie, avec 730
jetons initiaux. **Ce jeton n’est pas une matière industrielle réelle.**
Capacité et coût réels de fabrication restent inconnus ; le coût configuré
zéro signifie « non estimé », pas « fabrication gratuite ».

### 13.2 Le voyage du semi-fini

| Flux | Lot de fabrication | Blocage après fin à Gaillac | Transport | Traitement à destination |
|---|---:|---:|---:|---:|
| `693055` → Avène | 600 KG | 28 jours lundi–vendredi | 7 jours calendaires, hypothèse | 7 jours lundi–vendredi |
| `773474` → Gien | 3 200 KG | 33 jours lundi–vendredi | 10 jours calendaires | 6 jours lundi–vendredi |

```text
DisponibleGaillac = AjouterOuvrés(DateFinLot, BlocageGaillac)
RéceptionDestination = DateDépart + TransportCalendaire
DisponibleDestination = AjouterOuvrés(RéceptionDestination, TraitementDestination)
```

Ces délais de libération source sont des conventions explicites du modèle,
pas une identification certaine de toutes les étapes industrielles. Les
70 jours de référence FIA de `693055` ne deviennent pas 70 jours de transport
en plus des délais du tableau.

Les deux liaisons sont revues lorsque `jour % 7 = 0`, donc les mercredis avec
l’origine actuelle. Le besoin de transfert vient du netting de la destination.
Il crée un besoin au site origine, daté à son départ prévu.

**Lot de fabrication, proposition de transfert et camion sont différents :**

- `693055` : proposition de transfert par multiple de 600 KG, mais pas de multiple
  physique de chargement imposé. Une sortie physique de 1 190 KG est possible.
- `773474` : fabrication par 3 200 KG et multiple physique de chargement de
  3 200 KG ; le plan de transfert n’a pas un multiple de commande explicitement
  identique dans la politique interne.

### 13.3 Protection particulière de `693055` à Avène

Le plugin actif garde le plancher de sécurité **uniquement à la clôture du
samedi**, puis le met à zéro entre les revues. Les besoins physiques quotidiens
restent présents. C’est une politique candidate particulière au couple,
pas un effacement des besoins des autres jours.

## 14. Acheter un composant : avancer le besoin sans consommer plus tôt

`Sécurité` est le nombre de jours lundi–vendredi du couple article/site.
`Fixe` est la réserve en quantité. L’achat externe n’utilise pas exactement
le même mécanisme de sécurité qu’un transfert interne.

```text
DateProtégée[d] = max(t, RetirerOuvrés(d, Sécurité))
BesoinAnticipé[u] = somme(BesoinPhysique[d] dont DateProtégée[d] = u)
BesoinAnticipé[t] = BesoinAnticipé[t] + Fixe
```

La réserve fixe est ajoutée **une seule fois** dans le plan. La date du besoin
de planification est avancée ; la consommation physique garde sa vraie date.
Les engagements tardifs sont conservés par le netting de la section 8.

**Exception de mode :** les six politiques de fournisseur sélectionné et les
stocks gérés décrits plus loin emploient une protection de stock avec couverture
datée. Ils ne se réduisent donc pas à avancer tous les besoins de la même façon.
Le champ `protection_mode` de l’annexe précise la branche à utiliser.

### 14.1 Regrouper puis lotifier

Le regroupement de besoin vaut **un jour** : seules les échéances identiques
sont regroupées. Ce n’est pas une revue d’achat hebdomadaire.

Après netting et arrondi du besoin en masse, appliquer minimum, multiple,
maximum par ordre et réutilisation des surplus, comme en section 10.
Pour la plupart des offres, le standard fournisseur est utilisé comme minimum
et multiple. C’est une convention du simulateur ; le fichier FIA ne démontre
pas toujours que le standard est un minimum contractuel.

Deux exceptions actives : les standards de `338929` à Avène et `333362` à Gien
ne sont pas contraignants ; seules les UN entières restent imposées.
Pour `708073` à Gien, le standard effectif est **5 000 KG**, après correction
d’un champ brut mal étiqueté. Ne pas recopier le 5 000 000 KG du graphe brut.

### 14.2 Trouver le jour de commande

`DélaiFournisseur` est le temps commande→réception physique. `Traitement` est
le délai réception→disponibilité. Pour chaque jour de commande admissible `r` :

```text
RéceptionCandidate[r] = r + DélaiFournisseur
DisponibleCandidate[r] = AjouterOuvrés(RéceptionCandidate[r], Traitement)

DateCommande = dernière date r admissible telle que
              DisponibleCandidate[r] ≤ DateProtégée
```

Si aucun jour ne respecte l’échéance, choisir le premier jour encore possible
et enregistrer le retard. Ne jamais créer une commande nouvelle dans le passé.
Les délais fournisseur nominaux sont déterministes et lus une seule fois.

Exemple inventé : besoin utilisable un vendredi, traitement 2 jours ouvrés,
transport fournisseur 3 jours calendaires, sécurité nulle. Une réception le
mercredi permet une disponibilité vendredi ; la commande correspondante est
le dimanche précédent si ce jour est autorisé par la revue.

## 15. Quel fournisseur choisir ?

Le programme ne choisit pas universellement « le moins cher ». Il possède
trois branches distinctes.

### 15.1 Principal et secours : `001848` à Avène

| Rôle | Fournisseur | Prix | Commande→réception | Standard |
|---|---|---:|---:|---:|
| Principal | VD0951020A | 1,58 €/KG | 56 jours calendaires | 6 000 KG |
| Secours | VD0519670A | 4,20 €/KG | 21 jours calendaires | 4 000 KG |

Le programme construit le plan principal puis cherche les allocations qu’un
nouvel achat de secours pourrait rendre disponibles plus tôt. Le rôle des
fournisseurs est confirmé ; ce déclencheur précis reste expérimental.

Dans la branche additive active, le calcul reçoit des besoins **déjà avancés
par la sécurité**. Il ne faut donc pas présenter ce test comme le simple manque
physique aux dates de consommation originales.

Pour une allocation non protégée, le secours peut intervenir si :

```text
DateBesoinAnticipée < PremièreDisponibilitéNouvelAchatPrincipal
et
DateAllouéeActuelle > max(DateBesoinAnticipée, DisponibilitéSecours)
```

La quantité à couvrir est la somme des allocations améliorables. La réserve
fixe seule ne déclenche pas le secours. Les engagements fermes sont protégés
du rachat : même tardifs, ils ne sont pas automatiquement doublés par un secours.
Il n’existe pas de seuil nominal supplémentaire « X jours » ou « Y % ».

Le lot de secours et son surplus sont crédités avant de recalculer le principal.
Exemple inventé, après anticipation : stock 1 000 KG, besoin 3 000 puis 2 000 ;
secours possible avant le premier besoin, lot de 4 000. On achète 4 000 :
`1000 + 4000 − 3000 − 2000 = 0`. Pas besoin d’ajouter un lot principal de 6 000.

Avant libération, les propositions futures peuvent utiliser le plus petit
standard admissible sans engager de fournisseur. À la libération, la quantité
est redimensionnée selon l’offre réellement choisie, puis le plan est recalculé.

### 15.2 Fournisseur explicitement sélectionné

| Couple | Fournisseur retenu par la politique candidate |
|---|---|
| `055703` / Avène | VD0914320A |
| `039668` / Avène | VD1096202A |
| `708073` / Gien | VD0520115A |
| `001757` / Avène | VD0951020A |
| `002612` / Avène | VD0910216A |
| `007923` / Avène | VD0956464A |

Les autres offres ne deviennent pas automatiquement un secours si le sélectionné
ne fournit pas. Ces choix sont configurés ; ils ne prouvent pas une exclusivité ERP.

### 15.3 Parts conventionnelles pour les autres multi-sources

Les offres sont triées par **coût de transport unitaire**, puis délai, puis
identifiant. Parts configurées : 70/30 avec deux offres, 70/20/10 avec trois,
70/20/5/5 avec quatre. Ce ne sont pas des quotas industriels observés.

```text
CibleFournisseur = min(ResteAprèsAchatsPrécédents,
                       BesoinNetGroupé × PartFournisseur / SommeParts)
```

Chaque cible est lotifiée. Un premier gros lot peut couvrir tout le besoin :
les quantités effectivement achetées ne respectent pas forcément les pourcentages.
Le mode facultatif de score coût–risque existe, mais n’est pas actif ici.

## 16. Engager, recevoir et éventuellement reporter une promesse

### 16.1 De la proposition au produit utilisable

```text
Proposition révisable
  → commande engagée, réception promise
  → réception physique, stock bloqué
  → fin du traitement, stock utilisable
```

Un achat agrégé ne fournit pas un départ camion industriel observé. Son statut
peut être « commandé, départ inconnu ». Il ne faut pas inventer une étape
fournisseur supplémentaire puis ajouter à nouveau le délai FIA.

Le programme vérifie aussi la capacité partagée fournisseur/article et la
fiabilité. Pour les données nominales, la fiabilité vaut 1 et les incidents
sont désactivés : quantité reçue égale quantité engagée, sous contrainte de capacité.

### 16.2 Calendrier d’achat hebdomadaire actif

Pour `338929` à Avène et `333362` à Gien, la revue d’achat est le **dimanche**,
à partir du 5 janvier 2025. Les besoins sont toujours calculés et exécutés
physiquement chaque jour. Regrouper les besoins d’une même date et n’autoriser
les achats que le dimanche sont deux règles différentes.

### 16.3 Exception : certaines promesses peuvent changer de date

« Garder un engagement » signifie garder son identité et sa quantité, pas
interdire tous les reports. Le bundle contient deux politiques expérimentales :

- Nouvelles promesses de `338929` à Avène et `333362` à Gien : report possible
  le dimanche, avant réception, avec permission explicite et sans départ observé.
  La permission expire à la réception physique **originale**, même après report.
- Sept achats initiaux, identifiés par les lignes source
  `97, 94, 92, 96, 95, 93, 101` : permissions configurées de modification.
  Après un report, retour possible vers la date contractuelle initiale,
  jamais avant. Les statuts « non parti » de ces lignes sont hypothétiques.

Algorithme d’un report :

```text
Retirer provisoirement cette réception du plan.
Conserver stock, besoins et toutes les autres réceptions.
Solde[j] = Solde[j−1] + AutresRéceptionsDisponibles[j] − Besoins[j]
Chercher le premier j où Solde[j] < Plancher[j].
Proposer une disponibilité à ce déficit protégé,
ou à la borne de couverture continue connue si aucun déficit n’apparaît,
sans passer avant la date contractuelle autorisée.
```

Un trou de prévision limite le report ; il n’est pas traité comme zéro.
Une réception déjà physiquement détenue reste figée. Après modification des
dates, le réseau est recalculé avant toute nouvelle commande. La quantité,
l’identité et le coût de l’ordre ne sont pas créés une deuxième fois.

## 17. Les cas d’ouverture et surcharges à ne pas oublier

Ces règles font partie de l’exécution actuelle même si elles ne sont pas les
règles générales d’un MRP industriel.

| Cas configuré | Ce qui est fait | Statut |
|---|---|---|
| `001848` à Gien | Deux achats initiaux supplémentaires de 7 000 KG, reçus les jours 33 et 54, utilisables 69 et 90 | Hypothèse tirée du premier plan connu au jour 4, rétropolée à l’ouverture |
| `002612` à Gaillac | Réception supplémentaire de 1 250 KG au jour 4, disponible au jour 9 | Hypothèse source ; stock initial 414 KG conservé |
| `338929` à Avène | Deux compléments de 122 234 et 300 793 UN, introduits au jour 4 ; réceptions jours 15 et 29, disponibilités 23 et 37 | Réceptions prévues du premier plan, pas fermeté industrielle prouvée |
| `344135` à Gien | Ancienne référence `EX-344135`, 107 800 UN initiales, utilisables entre jours 0 et 120 si aucun stock nouveau n’est utilisable | Hypothèse de transition explicitement configurée hors graphe |

Pour la transition, si du stock nouveau existe, il est prioritaire pour le
passage. L’ancien n’est pas compté simultanément comme un deuxième stock du
nouvel article. Ce n’est pas une modification de la BOM.

Trois stocks gérés hors recette ont aussi des politiques locales candidates :

| Couple | Physique initial | Lot local | Protection supplémentaire | Fournisseur ; délai calendaire ; réception ouvrée |
|---|---:|---:|---:|---|
| `001848` / Gien | 31 660,43 KG | 7 000 KG | 26 jours candidats | VD0951020A ; 56 ; 26 |
| `001893` / Gaillac | 1 094 KG | 950 KG | 0, source industrielle absente | VD0518684A ; 56 ; 5 |
| `002612` / Gaillac | 414 KG | 1 250 KG | 0, source industrielle absente | VD0910216A ; 35 ; 5 |

La prévision de ces articles prépare des réceptions mais ne crée pas, seule,
une consommation. Pour `001893` à Gaillac, 375 KG sont exclus du disponible
initial avec statut/date inconnus ; le libre initial vaut donc 719 KG.

## 18. Tableau des paramètres d’achat courants

Tous les délais de la colonne **sécurité** et **traitement** sont en jours
lundi–vendredi. Le délai fournisseur est en jours calendaires. La réserve
fixe et les lots sont dans l’unité de la ligne. Les montants sont des prix
normalisés par KG, UN ou M selon la ligne, pas des montants par commande.

Les offres non sélectionnées restent dans l’annexe JSON, avec les unités
et bases de prix brutes. Un prix par 1 000 ne multiplie pas la quantité achetée.

| Site | Article / unité | Sécurité ; réserve fixe | Traitement | Offre : prix ; délai ; standard |
|---|---|---|---:|---|
| Gien | 038005 / KG | 20 ; 0 | 14 | VD0520132A : 4,57 ; 154 ; 10 000 |
| Gien | 042342 / UN | 5 ; 0 | 14 | VD0914690A : 0,00221 ; 21 ; 30 000 000 |
| Gien | 333362 / UN | 10 ; 110 000 | 5 | VD0525412A : 0,27321 ; 60 ; standard 5 000 non contraignant |
| Gien | 344135 / UN | 10 ; 0 | 4 | VD0993480A : 0,00403 ; 35 ; 120 000 |
| Gien | 708073 / KG | 10 ; 2 000 | 5 | VD0520115A : 3,59 ; 28 ; 5 000 corrigé |
| Gien | 730384 / M | 10 ; 23 500 | 5 | VD0508918A : prix absent/nul ; 56 ; 92 500 |
| Gien | 734545 / UN | 10 ; 0 | 1 | VD1095770A : 0,42644 ; 21 ; 6 300 |
| Avène | 001757 / KG | 20 ; 0 | 13 | VD0951020A : 5,43 ; 84 ; 100 |
| Avène | 001848 / KG | 20 ; 0 | 13 | Principal : 1,58 ; 56 ; 6 000 / secours : 4,20 ; 21 ; 4 000 |
| Avène | 001893 / KG | 15 ; 0 | 24 | VD0518684A : 4,40 ; 56 ; 22 800 / VD0910216A : 4,64 ; 28 ; 23 920 / VD1091642A : 5,105 ; 42 ; 20 900 |
| Avène | 002612 / KG | 20 ; 0 | 9 | Sélectionné VD0910216A : 0,82 ; 35 ; 22 500 |
| Avène | 007923 / KG | 15 ; 0 | 6 | Sélectionné VD0956464A : 1,82 ; 15 ; 19 140 |
| Avène | 016332 / KG | 7 ; 0 | 1 | VD0514881A : 27,62 ; 49 ; 1 100 |
| Avène | 029313 / KG | 7 ; 0 | 1 | VD0519670A : 2,07 ; 56 ; 300 |
| Avène | 039668 / KG | 7 ; 0 | 1 | VD1096202A : 12,21 ; 35 ; 450 |
| Avène | 049371 / KG | 40 ; 888 | 9 | VD0520132A : 14,65 ; 147 ; 1 600 |
| Avène | 055703 / KG | 30 ; 0 | 13 | Sélectionné VD0914320A : 20,35 ; 21 ; 300 |
| Avène | 099439 / KG | 7 ; 0 | 1 | VD0505677A : 9,17 ; 35 ; 4 200 |
| Avène | 338928 / UN | 10 ; 0 | 6 | VD0901566A : 0,14131 ; 70 ; 25 000 |
| Avène | 338929 / UN | 10 ; 0 | 6 | VD0914360C : 0,21585 ; 42 ; standard 5 000 non contraignant |
| Avène | 426331 / UN | 10 ; 0 | 1 | VD0989480A : 0,50393 ; 28 ; 19 200 |
| Gaillac | 021081 / KG | 0 ; 900 000 | 75 | Quatre fournisseurs ; prix 12,10 / 12,10 / 12,15 / 15 ; délai 120 ; standard 20 000 |

Les quatre fournisseurs de `021081`, dans l’ordre conventionnel d’allocation,
sont VD0949099A, VD0960508A, VD0972460A, VD0975221A. Pour `001893` à Avène,
l’ordre d’allocation est VD0910216A, VD1091642A, VD0518684A ; cet ordre ne suit
donc pas simplement les prix croissants du tableau.

Les 33 capacités fournisseur/article effectives du nominal viennent de
`supplier_neutral_floors.csv`. Malgré le mot « floors », le code **remplace**
les capacités heuristiques par ces valeurs : il ne prend pas seulement leur
maximum. Ce sont des capacités de scénario, pas des mesures industrielles.
Elles sont partagées lorsqu’un même fournisseur/article dessert plusieurs sites.

## 19. Risques et coûts : ce qui change la décision, ce qui ne la change pas

### 19.1 Nominal et scénarios de risque

Le nominal ne charge aucun calendrier d’incidents, désactive les risques
endogènes et n’applique pas de risque aux achats initiaux. Ses délais fournisseur
sont déterministes ; la fiabilité des offres du bundle vaut 1.

Le moteur possède néanmoins des mécanismes optionnels modifiant capacité,
disponibilité, qualité, délai ou prix. Une réimplémentation du nominal ne doit
pas les activer implicitement.

`Borner(x, minimum, maximum)` signifie garder x entre les deux limites.
`QuantitéNetteVoulue` est la quantité utilisable visée par le plan.
`FiabilitéPlanifiée` est la fiabilité que la politique autorise le MRP à
anticiper ; elle vaut 1 dans le nominal décrit ici.

```text
RendementEffectif = borner(FiabilitéNominale × FacteurFiabilité × FacteurQualité,
                          minimum 0,01, maximum 1)

CapacitéRestanteFournisseur = CapacitéJour × Disponibilité × FacteurCapacité
                            − QuantitéDéjàEngagéeAujourd’hui

DemandéBrut = QuantitéNetteVoulue / FiabilitéPlanifiée

Si le standard est contraignant et positif :
  LotsDemandés = ceil(DemandéBrut / Standard)
  LotsPossibles = floor(max(0, CapacitéRestanteFournisseur) / Standard)
  QuantitéCommandée = min(LotsDemandés, LotsPossibles) × Standard
Sinon :
  QuantitéCommandée = min(DemandéBrut, max(0, CapacitéRestanteFournisseur))

QuantitéCommandée = floor(QuantitéCommandée)                si unité UN
QuantitéReçue = floor(QuantitéCommandée × RendementEffectif) si unité UN
QuantitéReçue = QuantitéCommandée × RendementEffectif        si masse/longueur
```

Si aucun lot ne tient dans la capacité, la quantité engagée vaut zéro ; le
besoin n’est pas effacé. Le code applique aussi une tolérance numérique de
1e−9 autour des plafonds/planchers de nombre de lots pour éviter un lot dû
seulement à une erreur de représentation. Les multiples de chargement, quand
ils existent, sont vérifiés après ce dimensionnement.

La commande peut être grossie pour compenser une fiabilité connue du MRP.
Le flag de grossissement des pertes détermine si une perte temporaire est
anticipée ou subie après dimensionnement. Les multiplicateurs de risque se
composent par multiplication ; les jours de retard supplémentaires s’ajoutent.

Une capacité générique n’est pas toujours raccordée à chaque branche : les
nouveaux achats agrégés appellent actuellement le calcul de délai avec un délai
de qualité optionnel égal à zéro. La présence du risque `quality_delay` dans
le moteur ne prouve donc pas son activation pour ces achats.

Les seuils facultatifs de risque de stock ne sont pas des déclencheurs du
fournisseur de secours. Ne pas les mélanger avec la section 15.

### 19.2 Coûts

Il n’y a pas de formule de Wilson, de lot économique ni d’optimisation globale
coût–stock–rupture dans ces décisions. Les quantités proviennent des besoins,
des protections, des engagements et des lots. Les prix influencent certaines
sélections de fournisseurs, pas la demande du client.

```text
PrixNormalisé = PrixSource / BaseDePrix
CoûtNouvelAchat = QuantitéReçue × PrixNormalisé × FacteurPrixDuScénario
```

Le carnet déjà existant n’est pas facturé à nouveau. Un prix absent peut activer
le repli économique de 0,01 par unité : ce n’est pas un prix industriel observé.
Les valeurs de portage, de stockage et le multiplicateur nominal de transport
0,2 sont des hypothèses de préparation. Elles ne créent pas de consommation.
Un chiffre d’affaires perdu ne fournit pas, à lui seul, une quantité non livrée.

## 20. Après 2025 : un scénario déclaré, pas de nouvelles observations

Les commandes clients historiques sont conservées jusqu’au jour 364 inclus,
soit le 31 décembre 2025. Le jour 365 est le 1er janvier 2026.
À partir de là, on utilise un profil de 52 semaines, soit 364 jours, aligné sur
les jours de semaine, avec une croissance de 5 % par cycle.

```text
(Cycle, Position) = division_avec_reste(jour + 2, 364)
JourBase = Position − 2
DemandeSemaineScénario = floor(DemandeSemaineBase × 1,05^Cycle)
```

La demande quotidienne est ensuite la différence de deux cumuls entiers de
la section 6. Ce ne sont pas des totaux d’années civiles simplement multipliés.
Les commandes physiques synthétiques ne deviennent connues que le jour prévu.

Le scénario prévisionnel cohérent est publié au jour 365 pour les dates cibles
à partir du jour 369, lundi 5 janvier 2026 : la prévision hebdomadaire est alors
le même total synthétique que la future demande, réparti pour planifier.
Les jours de transition précédents peuvent conserver des prévisions source
ou leur prolongement déclaré. Rien de cela n’est connu implicitement en 2025.

Le profil des autres usages, lui, bascule à partir du jour 362 selon le contrat
de référence : il est gelé en demandes, répété sur 364 jours puis augmenté de
5 % par cycle. Il n’est pas recalculé à partir de la BOM future effectivement
consommée. Ne pas confondre cette borne avec la borne de la demande client.

Pour les années suivantes, les deux premières semaines ouvrées complètes d’août
à Avène sont une fermeture supposée. Les stocks et ordres d’ouverture ne sont
jamais répétés au début d’un nouveau cycle.

## 21. L’ordre quotidien exact à programmer

Ce n’est pas seulement une liste de formules. Changer l’ordre des opérations
change ce qui peut partir, être consommé ou être servi le même jour.

```text
AVANT LE PREMIER JOUR
  Charger unités, réseau, recettes, politiques et paramètres effectifs.
  Appliquer les surcharges de référence, puis les arguments explicites.
  Charger une seule fois stocks, encours et engagements initiaux.
  Séparer libre, bloqué, réservé, transit et encours.
  Installer les adaptateurs historiques actifs et le calendrier de protection.

POUR CHAQUE JOUR t
  1. Mettre à jour les informations désormais connues et les calendriers.
  2. Libérer les stocks initiaux bloqués dont la date est atteinte.
  3. Lire la demande du jour, consommer sa part de prévision et préparer les signaux.
  4. Traiter les départs programmés, réceptions physiques et disponibilités dues.
     Retirer une réception de la file future avant de la créditer en stock.
  5. Exécuter les conditionnements d’ouverture, puis les fabrications.
     Autoriser les nouvelles campagnes à partir du snapshot de la veille
     re-netté avec la disponibilité réelle du jour.
  6. Servir la demande client depuis son stock déjà arrivé ; garder le retard.
  7. Servir les autres usages sur le stock restant ; garder leur retard séparé.
  8. Calculer un plan réseau daté aval→amont avec l’information connue.
     Appliquer les reports de promesses autorisés ; recalculer le plan si modifié.
  9. Engager achats et transferts admissibles aujourd’hui.
     Pousser le PF libre vers Muret ; expédier du dépôt seulement la demande connue.
 10. Recalculer le réseau après ces engagements et mouvements.
     Conserver ce snapshot révisable pour les fabrications du lendemain.
 11. Exporter bilans, disponibilités, décisions, lots, coûts et retards.
```

Le réseau de planification doit être sans cycle, traité client→dépôt→usine→
composants. Un article/site ne peut pas être simultanément acheté et fabriqué
sans une politique de partage explicite. Les liens de recette doivent avoir
des coefficients strictement positifs.

Pour chaque article/site, utiliser successivement : besoins datés → protection
appropriée → allocation des ressources fermes → propositions lotifiées → dates
admissibles → propagation des nouvelles propositions à l’amont. Une campagne
active utilise sa propre identité ; elle ne redevient pas une nouvelle proposition.

La grille de lancement combine les périodes par leur plus petit commun multiple :

```text
PériodeAdmissible = ppcm(PériodeLiaison, PériodeArticleSite)
DateAdmissible si numéro_du_jour % PériodeAdmissible = 0
```

Les calendriers explicites d’achat du dimanche ou de fermeture complètent cette
grille. Pour la fabrication, le calcul planifié doit aussi éviter les fermetures
sur l’intervalle de marge `tau_process`. Cette inversion de dates n’est pas une
preuve d’une durée physique de fabrication.

## 22. Les données minimales pour reconstruire le système

Un lecteur peut refaire la logique avec ce guide. Pour retrouver les mêmes
nombres, il lui faut aussi les **mêmes entrées**, unités et conventions.

| Table à reconstruire | Champs indispensables |
|---|---|
| Articles | Identifiant, unité canonique, type PF/SF/composant |
| Sites | Identifiant, rôle, articles stockés, procédés autorisés |
| Stocks | Site, article, quantité, unité, état physique, date de libération connue ou inconnue |
| Lots | Identifiant stable, quantité restante, état, origine, parents, réservations et événements |
| Demandes clients | Article, client, semaine ou jour, quantité, date d’arrivée de la demande |
| Prévisions | Version, date de connaissance, période cible, quantité, source et statut estimé |
| Recettes | Site, parent, quantité de base, composant, quantité, unité, version/date d’effet |
| Fabrication | Minimum/multiple/maximum ou lot fixe, capacité, quotas, calendrier, marge planifiée |
| Routes | Origine, destination, article, délai, période de revue, multiple physique, fiabilité |
| Protection | Article/site, sécurité en jours ouvrés, réserve fixe, mode actif, date d’effet |
| Offres | Fournisseur, article/site, prix/base/unité/devise, délai, standard et son statut contraignant |
| Engagements | Identité, quantité restante, fournisseur ou procédé, dates et statuts, permission éventuelle de report |
| Autres usages | Article/site, besoin, date, version/connaissance, origine distincte de la BOM propre |
| Paramètres de référence | Surcharges, adaptateurs, modes, origine du temps et arguments explicites |

L’[annexe des paramètres lisibles](reference/MRP_PARAMETRES_LISIBLES.json)
contient les 35 nœuds, 42 liaisons, recettes, stocks, politiques et surcharges
du chargement courant. Elle conserve les valeurs brutes et leur provenance.
**Les arguments explicites priment sur les anciens défauts du scénario.**
Par exemple, l’ancien facteur d’initialisation 0,02 présent dans le graphe
n’est pas le facteur effectif : l’argument actif impose 1.

Cette annexe n’est pas un remplacement autonome des historiques. Pour les
versions de prévisions, consommations et budgets complets, transmettre aussi
les actifs indiqués dans `source_assets` et le classeur client courant. Elle
décrit les pointeurs des tables historiques plutôt que recopier des millions
de valeurs dans un guide.

### 22.1 Fichiers qui définissent la référence courante

| Fichier | Rôle |
|---|---|
| `config/mrp_reference_20261013.json` | Désigne la référence et contrôle les empreintes des actifs |
| `config/mrp_reference_20261013/graph.json.gz` | Réseau, états, recettes, offres, séries historiques et politiques |
| `config/mrp_reference_20261013/engine_arguments.json` | Arguments qui remplacent les défauts du graphe |
| `config/mrp_reference_20261013/protocol.json` | Paires de réconciliation et protection hebdomadaire |
| `config/mrp_reference_20261013/supplier_neutral_floors.csv` | 33 capacités fournisseur/article du scénario |
| `config/mrp_reference_20261013/external_component_demand_daily.csv.gz` | Profil gelé d’autres usages utilisé dans le prospectif |
| `config/cases/data_poc.json` | Alias, transition de référence, standards corrigés et revues des routes internes |
| `data/source/Flow_Data_Customer_Demand.xlsx` | Demande réelle hebdomadaire et prévisions courantes |

Le chargement `current_reference.resolve_inputs()` vérifie le bundle puis
applique ce classeur client. Le vieux `demand_PF.xlsx` présent dans le graphe
ne redevient pas la demande physique courante.

### 22.2 Vérifications minimales d’une réimplémentation

Les exemples inventés ci-dessous sont des **résultats attendus**, pas une
preuve que tous les tests correspondants existent dans le dépôt.

| Cas | Résultat attendu |
|---|---|
| Demande hebdomadaire entière 10, distribution sur 7 jours | 1,1,2,1,2,1,2 ; total 10 |
| Prévision 700, demande déjà arrivée 360 mercredi | 340 restants, 85/jour sur jeudi–dimanche |
| Besoin 10 mardi, libre 5, ferme 5 vendredi | Pas de nouvel achat ; 5 tardives de 3 jours |
| Besoins 3 puis 6, lot minimum 10 | Une proposition 10, surplus final 1 |
| Besoins 10 puis 10, planchers 20 puis 10 | Enveloppes 30 puis 30 ; tranches 30 puis 0 |
| Réception vendredi, traitement 2 jours ouvrés | Disponible mardi, pas lundi |
| PF 100 utilisables à l’usine, Muret sans besoin net | Push de 100 si aucune autre limite physique |
| Retard client 25, client vide, engagements ouverts 8 | Besoin d’envoi nouveau 17, avant limite de stock Muret |
| Arrivée physique d’un lot bloqué 100 puis libération | Une seule réception ; +100 au libre à la libération sans +100 au physique |
| Achat de secours 4 000 et stock 1 000 couvrant besoins 3 000 puis 2 000 | Aucun achat primaire supplémentaire nécessaire |

Ajouter les cas de stock nul, capacité nulle, réception au-delà de l’horizon,
plusieurs parents partageant la même matière, ordres initiaux et arrondis UN
par passage. Une capacité absente ne doit pas être interprétée comme nulle.

Pour chaque bilan physique de site/article, vérifier :

```text
PhysiqueFin = PhysiqueDébut + Réceptions + SortiesDeFabrication
              − Prélèvements − Départs − Pertes + AjustementsSignés
```

Une libération de blocage ne figure pas comme une deuxième réception. Une
réservation n’est pas une consommation. Une proposition ne modifie pas le bilan.

Conserver les deux suivis de lots, les identités d’engagements et les états de
fin : en transit, bloqués, encours et retards ne disparaissent pas à la fin
d’une fenêtre d’exécution.

## 23. Où contrôler les règles dans le code et les résultats

Les chemins ci-dessous sont relatifs à `etudecas/`. Les fonctions sont une
meilleure clé de recherche que les numéros de lignes, qui peuvent évoluer.

| Sujet | Fonction ou fichier de référence |
|---|---|
| Entrée active et surcharges | `simulation/current_reference.py` : `resolve_inputs`, `run_engine`, `install_projection` |
| Lecture du classeur client | `simulation_prep/inject_mrp_seed_data_v2.py` : `build_customer_demand_payloads` |
| Historique quotidien client | `simulation/engine/run_first_simulation.py` : `SourceCustomerHistory.quantity` |
| Versions et consommation de prévision | Même fichier : `RollingMrpForecast.source_for_day`, `observe_demand`, `consumption_audit` |
| Plan aval→amont | Même fichier : `plan_component_network` |
| FIFO et propositions datées | `simulation/engine/mrp_planning.py` : `_allocate`, `plan_dated_requirements` |
| Enveloppe de sécurité | Même fichier : `prospective_stock_protection`, `plan_with_stock_protection` |
| Anticipation achats | Même fichier : `plan_anticipated_requirements` |
| Choix et lots fournisseurs | Même fichier : `plan_sourced_requirements` |
| Dates de lancement | `run_first_simulation.py` : `dated_supply_release_calendar` |
| Dates de disponibilité | Même fichier : `supplier_receipt_available_day` |
| Campagnes et travail physique | `simulation/lot_trace/campaigns.py` ; `run_first_simulation.py` boucle de fabrication |
| Arrondis et multiples physiques | `simulation/lot_policy/engine_adapter.py` |
| Push usine–Muret | `run_first_simulation.py` : `finished_goods_dispatch_need` |
| Expédition client connue | Même fichier : `customer_known_demand_need`, `cap_known_customer_dispatch` |
| Reports de promesses | Même fichier : `apply_supplier_promise_postponement`, `apply_opening_purchase_postponement` et `mrp_planning.py` fonctions de report |
| Réconciliation plan/physique | `simulation/reference_mrp/reconciliation.py`, `historical_adapter.py` |
| Protection samedi à Avène | `simulation/reference_mrp/weekly_protection.py` |
| Surcharges de cas | `case_config.py`, `config/cases/data_poc.json` |

| Résultat à inspecter | Fichier CSV dans le dossier `data` d’une simulation |
|---|---|
| Demande et service réellement simulés | `production_demand_service_daily.csv` |
| Prévision remplacée par les commandes | `mrp_forecast_consumption_daily.csv` |
| Besoins, propositions, ressources, retard | `mrp_dated_plan_daily.csv`, `mrp_dated_plan_weekly.csv` |
| Décisions de lancement et engagements | `mrp_orders_daily.csv`, `production_plan_events.csv` |
| Travail effectivement exécuté | `production_constraint_daily.csv`, `production_output_products_daily.csv` |
| Composants réellement consommés | `production_input_consumption_daily.csv` et généalogie de lots |
| Libre, bloqué, réservé, physique | `production_stock_availability_daily.csv` |
| Expéditions et arrivées | `production_supplier_shipments_daily.csv`, `production_input_replenishment_arrivals_daily.csv` |
| Ordres et stocks repris à l’ouverture | `initialization_pipeline.csv`, `initialization_observed_stock.csv` |

Le profil de sortie compact ne fournit pas tous les CSV détaillés : son absence
ne doit jamais être comptée comme une vérification réussie.

## 24. Ce qui est établi, conventionnel ou encore inconnu

| Niveau | Exemples |
|---|---|
| Règle programmée vérifiée par lecture | Push PF vers Muret, client connu seulement, FIFO daté, sécurité, lots, calendriers actifs |
| Donnée ou décision explicitement retenue | Sources de demande, stocks, recettes, sécurités Muret 20/25, réception PF à Muret |
| Convention du simulateur | Répartition quotidienne, arrondi 2,5→2, cadence ancrée J0, parts fournisseurs, capacité Gaillac non bornée |
| Reconstruction ou politique candidate | F3/E4, stocks/initiaux complétés, reports de promesses, plancher samedi, fournisseurs sélectionnés |
| Inconnue industrielle | Dates et identités réelles de lots/transferts, sens complet des délais, capacités réelles Gaillac, ventilation par format |

Un même point de stock peut être compatible avec plusieurs événements.
Décrire les règles, fermer les bilans ou passer des contrôles numériques ne
démontre pas que le scénario a reproduit l’histoire industrielle. Aucun aléa
réel n’est identifié par ce guide et la référence n’est pas promue.

Pour reproduire **ce programme**, conserver les conventions et adaptations
décrites. Pour construire **un MRP industriel cible**, faire confirmer les
politiques candidates avant de les transformer en règles de gestion.
