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

**Lecture de ce schéma.** Sens des questions de planification, du client vers les fournisseurs, pour les articles et les dates à couvrir avec les informations déjà connues.

**Les produits se déplacent dans le sens inverse :**

```text
Fournisseurs → matières utilisables → fabrication
  → transport → contrôle à réception → Muret
  → transport → client → demande servie
```

**Lecture de ce schéma.** Sens des mouvements physiques : fournisseurs, fabrication, Muret puis client. Chaque étape garde sa propre date ; une flèche ne signifie pas un déplacement instantané.

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

**Rappel des variables de ce calcul.**

**Périmètre :** Pour un PF à son usine, le jour du départ vers Muret : 268091 à Avène ou 268967 à Gien. Cette quantité est encore soumise aux contraintes physiques du départ.

- `Quantité à envoyer à Muret` : Quantité du produit fini que la règle propose d'expédier de l'usine vers Muret aujourd'hui. **Unité :** UN du PF.
- `tout le stock utilisable de PF à l’usine` : Quantité du même produit fini présente à l'usine, libérée et non réservée ; elle exclut l'encours et le stock bloqué. **Unité :** UN du PF.

**Opérateurs et signes :** `=` : vaut la valeur calculée, ou met à jour la quantité dans les lignes successives.

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

**Rappel des variables de ce calcul.**

**Périmètre :** Transport d’un produit fini de son usine vers Muret, dans l’exécution quotidienne nominale.

- `2.5` : Durée moyenne de transport inscrite dans le graphe avant arrondi. **Unité :** jours calendaires.
- `2` : Durée entière retenue pour ce transport par le calcul. **Unité :** jours calendaires.

**Opérateurs et signes :** `round` : Arrondir à l’entier le plus proche ; à mi-chemin exact, choisir l’entier pair : 2 pour 2,5 ; `=` : Le résultat est égal à la quantité calculée.

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

**Rappel des variables de ce calcul.**

**Périmètre :** Photo du stock d'un même article sur un même site au même instant. Le transit et l'encours sont suivis séparément.

- `Physique` : Quantité totale de l'article physiquement présente sur le site. **Unité :** unité de stock de l'article au site : UN, G, KG ou M.
- `Libre` : Part présente, libérée et non réservée, utilisable immédiatement. **Unité :** même unité de stock que Physique.
- `Bloqué` : Part présente qui n'est pas encore utilisable. **Unité :** même unité de stock que Physique.
- `Réservé` : Part présente déjà affectée à un mouvement futur et indisponible pour une autre décision. **Unité :** même unité de stock que Physique.

**Opérateurs et signes :** `=` : vaut la valeur calculée, ou met à jour la quantité dans les lignes successives ; `+` : additionner les valeurs de même unité.

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

**Rappel des variables de ce calcul.**

**Périmètre :** Conversion de la même masse d'un article, au même site et au même instant ; la conversion ne crée aucun mouvement de stock.

- `quantité_en_KG` : Valeur de la masse exprimée en kilogrammes. **Unité :** KG.
- `quantité_en_G` : Valeur de la même masse exprimée en grammes. **Unité :** G.
- `KG` : Symbole du kilogramme, unité de masse. **Unité :** kilogramme.
- `G` : Symbole du gramme, unité de masse. **Unité :** gramme.
- `1 000` : Facteur de conversion : un kilogramme contient mille grammes. **Unité :** G par KG.

**Opérateurs et signes :** `=` : vaut la valeur calculée, ou met à jour la quantité dans les lignes successives ; `×` : multiplier les valeurs en conservant les unités indiquées ; `/` : diviser la première valeur par la seconde.

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

**Rappel des variables de ce calcul.**

**Périmètre :** Calcul d'une date pour le calendrier lundi–vendredi, sans ajout de jours fériés. Le jour de départ du décompte est exclu ; avec zéro jour à compter, la date reste inchangée.

- `date` : Date de départ du calcul, avant l'avance ou le recul. **Unité :** date, exprimable en numéro de jour du modèle.
- `nombre` : Nombre de jours lundi–vendredi à compter après ou avant la date de départ. **Unité :** jours lundi–vendredi.
- `AjouterOuvrés(date, nombre)` : Date obtenue après avoir avancé du nombre demandé de jours lundi–vendredi. **Unité :** date, exprimable en numéro de jour du modèle.
- `RetirerOuvrés(date, nombre)` : Date obtenue après avoir reculé du nombre demandé de jours lundi–vendredi. **Unité :** date, exprimable en numéro de jour du modèle.

**Opérateurs et signes :** `AjouterOuvrés` : Avance en ne comptant que lundi à vendredi, après la date initiale ; `RetirerOuvrés` : Recule en ne comptant que lundi à vendredi, avant la date initiale ; `=` : vaut la valeur calculée, ou met à jour la quantité dans les lignes successives.

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

**Rappel des variables de ce calcul.**

**Périmètre :** Pour un produit fini, son client et une semaine civile lundi–dimanche du classeur client. La valeur source est un entier non positif ; le calcul en inverse le signe.

- `DemandeSemaine` : Quantité totale positive ou nulle demandée au cours de la semaine. **Unité :** UN du PF pour la semaine.
- `valeur_source_Actual_Demand` : Valeur signée lue dans Actual Demand de la feuille Historique, pour le même PF, le même client et la même semaine. **Unité :** UN du PF pour la semaine, valeur non positive.

**Opérateurs et signes :** `=` : vaut la valeur calculée, ou met à jour la quantité dans les lignes successives ; `−` : soustraire la valeur de même unité.

Une valeur positive, fractionnaire, absente ou non finie est refusée, pas
transformée silencieusement en zéro.

Le détail quotidien n’étant pas fourni, on répartit le total entier sur les
sept jours calendaires. Pour le jour `k` de la semaine, numéroté de 0 à 6 :

```text
DemandeJour[k] = floor(DemandeSemaine × (k + 1) / 7)
                − floor(DemandeSemaine × k / 7)
```

**Rappel des variables de ce calcul.**

**Périmètre :** Répartition reconstruite d'une demande hebdomadaire entière, pour un PF et son client, sur les sept jours calendaires de la même semaine lundi–dimanche.

- `DemandeJour[k]` : Quantité de la demande hebdomadaire attribuée au jour k. **Unité :** UN du PF pour ce jour.
- `DemandeSemaine` : Quantité totale à répartir sur la semaine. **Unité :** UN du PF pour la semaine.
- `k` : Position du jour dans la semaine : 0 pour lundi, jusqu'à 6 pour dimanche ; k + 1 est la borne de cumul après ce jour. **Unité :** indice entier sans unité, de 0 à 6.
- `7` : Nombre de jours calendaires de la semaine utilisée pour la répartition. **Unité :** nombre de jours de la semaine.

**Opérateurs et signes :** `floor` : Prend l'entier inférieur de chaque cumul ; leur différence donne des UN entières et conserve le total hebdomadaire ; `=` : vaut la valeur calculée, ou met à jour la quantité dans les lignes successives ; `+` : additionner les valeurs de même unité ; `−` : soustraire la valeur de même unité ; `×` : multiplier les valeurs en conservant les unités indiquées ; `/` : diviser la première valeur par la seconde.

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

**Rappel des variables de ce calcul.**

**Périmètre :** Pour un PF chez un client, au moment du service du jour. Seul le stock libre déjà reçu chez ce client peut servir la demande.

- `ÀServir` : Demande arrivée totale à servir aujourd'hui, y compris le retard antérieur. **Unité :** UN du PF.
- `RetardAvant` : Demande arrivée les jours précédents qui reste non servie avant le service du jour. **Unité :** UN du PF.
- `DemandeJour` : Nouvelle demande physique arrivée aujourd'hui. **Unité :** UN du PF pour ce jour.
- `Servi` : Quantité effectivement servie depuis le stock libre du client aujourd'hui. **Unité :** UN entières du PF.
- `LibreClient` : Quantité du PF déjà présente, libérée et non réservée chez le client avant le service. **Unité :** UN du PF.
- `RetardAprès` : Demande arrivée qui reste non servie après le service du jour. **Unité :** UN du PF.
- `LibreClientAprès` : Stock libre restant chez le client après le service du jour. **Unité :** UN du PF.

**Opérateurs et signes :** `min` : Retient la plus petite quantité entre stock libre et demande à servir ; `floor` : Arrondit la quantité servie à l'entier inférieur pour conserver des UN physiques entières ; `=` : vaut la valeur calculée, ou met à jour la quantité dans les lignes successives ; `+` : additionner les valeurs de même unité ; `−` : soustraire la valeur de même unité.

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

**Rappel des variables de ce calcul.**

**Périmètre :** Pour un PF et un client, après le service du jour puis juste avant un départ de Muret. Le calcul utilise uniquement la demande déjà arrivée et les engagements client encore ouverts.

- `BesoinEnvoiClient` : Quantité de nouvel envoi nécessaire pour couvrir la demande connue encore non couverte. **Unité :** UN du PF.
- `RetardAprès` : Demande arrivée restant non servie après le service du jour chez le client. **Unité :** UN du PF.
- `LibreClientAprès` : Stock libre restant chez ce client après le service du jour. **Unité :** UN du PF.
- `quantités des envois client déjà engagés et encore ouverts` : Quantités restantes des envois du même PF vers ce client déjà engagés, comptées une seule fois même si leur arrivée est tardive. **Unité :** UN du PF par engagement.
- `DépartClient` : Quantité effectivement expédiée aujourd'hui de Muret vers ce client. **Unité :** UN entières du PF.
- `LibreMuret` : Stock du même PF présent, libéré et non réservé à Muret au moment du départ. **Unité :** UN du PF.
- `autres limites physiques` : Plafonds physiques applicables au départ, exprimés en quantité expédiable du même PF. **Unité :** UN du PF.

**Opérateurs et signes :** `max` : Retient zéro si les ressources déjà présentes ou engagées couvrent le retard ; sinon retient le manque ; `somme` : Additionne les quantités restantes de tous les engagements client ouverts concernés ; `min` : Retient la plus petite quantité entre stock Muret, besoin d'envoi et limites physiques ; `floor` : Arrondit la quantité expédiée à l'entier inférieur pour conserver des UN physiques entières ; `=` : vaut la valeur calculée, ou met à jour la quantité dans les lignes successives ; `−` : soustraire la valeur de même unité.

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

**Rappel des variables de ce calcul.**

**Périmètre :** Pour un PF, son client et la semaine civile courante, avec la dernière prévision connue aujourd'hui. La répartition ne porte que sur les jours futurs de cette semaine ; si aucun jour ne reste, le reliquat expire.

- `PrévisionRestante` : Part de la prévision hebdomadaire que les commandes déjà arrivées n'ont pas encore remplacée. **Unité :** UN prévues du PF pour le reste de la semaine.
- `PrévisionSemaine` : Quantité prévue pour toute la semaine, dans la version connue aujourd'hui. **Unité :** UN prévues du PF pour la semaine.
- `CommandesDéjàArrivées` : Cumul de la demande physique arrivée depuis le début de cette semaine jusqu'à aujourd'hui inclus, qu'elle soit déjà servie ou encore en retard. **Unité :** UN du PF.
- `PrévisionJourFutur` : Quantité prévisionnelle affectée à chacun des jours restants de la semaine ; les fractions sont autorisées. **Unité :** UN prévues du PF par jour.
- `JoursRestants` : Nombre de jours calendaires strictement après aujourd'hui et jusqu'au dimanche de la semaine inclus ; le quotient s'applique si ce nombre est positif. **Unité :** jours calendaires.

**Opérateurs et signes :** `max` : Empêche une prévision restante négative lorsque les commandes arrivées dépassent la prévision ; `=` : vaut la valeur calculée, ou met à jour la quantité dans les lignes successives ; `−` : soustraire la valeur de même unité ; `/` : diviser la première valeur par la seconde.

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

**Rappel des variables de ce calcul.**

**Périmètre :** Plan d'un PF pour un client établi à la fin du jour t, pour les dates d de t+1 à t+364. Les besoins sont des quantités datées ; ils ne sont pas du service physique déjà réalisé.

- `BesoinClient[d]` : Quantité du PF à couvrir chez le client à la date future d. **Unité :** UN prévues du PF pour la date d.
- `PrévisionJourFutur[d | t]` : Prévision pour le jour d calculée avec les seules informations connues au jour t, après consommation de prévision par les commandes arrivées. **Unité :** UN prévues du PF pour le jour d.
- `BesoinClient[t+1]` : Besoin du premier jour futur ; la deuxième ligne lui ajoute une seule fois le retard connu en fin de jour t. **Unité :** UN du PF pour le jour t+1.
- `RetardAprès` : Demande arrivée restant non servie après le service au jour t. **Unité :** UN du PF.
- `t` : Jour de décision où les informations disponibles sont arrêtées. **Unité :** numéro entier de jour du modèle.
- `d` : Date future du besoin, entre le lendemain de t et la fin de l'horizon de 364 jours. **Unité :** numéro entier de jour du modèle.
- `t+1` : Lendemain du jour de décision, premier jour de l'horizon futur. **Unité :** numéro entier de jour du modèle.

**Opérateurs et signes :** `[d | t]` : Distingue la date cible d de la date de connaissance t ; une information connue après t est exclue du calcul ; `=` : vaut la valeur calculée, ou met à jour la quantité dans les lignes successives ; `+` : additionner les valeurs de même unité.

La seconde ligne met à jour le besoin déjà calculé à la première ligne : elle ajoute le retard une seule fois. Ce n’est pas une équation à résoudre pour retrouver le même symbole des deux côtés.

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

**Rappel des variables de ce calcul.**

**Périmètre :** Pour un même article au même site dans un plan daté, besoins traités dans l'ordre des dates. Une ressource ferme tardive peut couvrir un besoin avec retard sans devenir utilisable plus tôt.

- `ResteAprèsFermes[d]` : Quantité du besoin protégé à la date d qui reste à couvrir après allocation du stock libre et des ressources fermes admises au plan. **Unité :** unité de stock de l'article au site, UN pour un PF.
- `BesoinProtégé[d]` : Quantité à couvrir à la date d, protection de stock comprise selon la politique locale. **Unité :** même unité de stock de l'article au site.
- `QuantitéAllouéeDepuisFermes[d]` : Part du besoin daté d couverte par les ressources fermes admises, y compris le stock libre initial du plan. **Unité :** même unité de stock de l'article au site.
- `BesoinNet[d]` : Quantité restant à couvrir par de nouvelles propositions après les ressources fermes et les surplus déjà calculés. **Unité :** même unité de stock de l'article au site.
- `SurplusEncoreDisponible[d]` : Quantité non encore affectée des propositions précédentes du même plan, réutilisable pour le besoin d. **Unité :** même unité de stock de l'article au site.
- `RetardAllocation` : Nombre de jours entre le besoin et la disponibilité de la ressource qui le couvre, sans valeur négative. **Unité :** jours calendaires.
- `DateDisponibleRessource` : Date où la ressource allouée devient utilisable sur le site du besoin. **Unité :** numéro de jour du modèle.
- `DateBesoin` : Date où la quantité allouée aurait dû être utilisable. **Unité :** numéro de jour du modèle.
- `UnitésJoursRetard` : Total des quantités allouées multipliées par leurs jours de retard, sur les allocations considérées. **Unité :** unité de l'article × jour ; UN·jour pour un PF.
- `QuantitéAllouée` : Quantité couverte par une allocation particulière à une ressource. **Unité :** unité de stock de l'article au site.
- `d` : Date du besoin traité dans le plan. **Unité :** numéro entier de jour du modèle.

**Opérateurs et signes :** `max` : Retient la plus grande valeur et ramène les restes ou retards négatifs à zéro ; `somme` : Additionne le produit quantité × retard de chacune des allocations considérées pour le même article/site ; `=` : vaut la valeur calculée, ou met à jour la quantité dans les lignes successives ; `−` : soustraire la valeur de même unité ; `×` : multiplier les valeurs en conservant les unités indiquées.

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

**Rappel des variables de ce calcul.**

**Périmètre :** Réserve de sécurité d'un PF à Muret, calculée pour une date d dans le plan connu aujourd'hui. Les besoins calendaires du week-end compris dans la fenêtre restent inclus.

- `Plancher[d]` : Réserve cible à préserver après les besoins du jour d. **Unité :** UN du PF.
- `Fixe` : Quantité de réserve fixe configurée pour ce PF à Muret, nulle pour les deux PF de la référence active. **Unité :** UN du PF.
- `BesoinBrut[j]` : Quantité de besoin datée du jour j avant ajout de cette réserve. **Unité :** UN du PF pour le jour j.
- `d` : Date après laquelle la fenêtre de sécurité commence ; son besoin propre est exclu de cette réserve. **Unité :** numéro entier de jour du modèle.
- `j` : Jour calendaire parcouru dans la somme, strictement après d et jusqu'à la borne de sécurité incluse. **Unité :** numéro entier de jour du modèle.
- `N` : Nombre de jours de sécurité source : 20 pour 268091 à Muret, 25 pour 268967, utilisés à 100 % dans le nominal. **Unité :** jours lundi–vendredi.
- `FinSécurité(d,N)` : Date obtenue en avançant de N jours lundi–vendredi après d ; elle ferme la fenêtre des besoins à additionner. **Unité :** numéro de jour du modèle.

**Opérateurs et signes :** `max` : Retient la plus grande quantité entre la réserve fixe et le total des besoins de la fenêtre ; `somme` : Additionne les besoins de tous les jours calendaires j satisfaisant d < j ≤ FinSécurité(d,N) ; `FinSécurité` : Cherche la borne future en ne comptant que lundi à vendredi, après d ; ce calendrier ne supprime aucun besoin du week-end à l'intérieur de la fenêtre ; `=` : vaut la valeur calculée, ou met à jour la quantité dans les lignes successives ; `≤` : inférieur ou égal ; `<` : strictement inférieur.

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

**Rappel des variables de ce calcul.**

**Périmètre :** Pour un PF à Muret dans un même plan daté, aux points successifs classés par date. L'enveloppe avant le premier point vaut zéro ; la protection est une exigence de planification, sans consommation physique.

- `Cumul[d]` : Total des besoins bruts du plan jusqu'à la date d incluse. **Unité :** UN du PF.
- `BesoinBrut[j]` : Quantité de besoin du jour j avant ajout de la réserve de sécurité. **Unité :** UN du PF pour le jour j.
- `Enveloppe[d]` : Total cumulé à couvrir, suffisant pour les besoins et le plancher de sécurité ; il ne descend jamais. **Unité :** UN du PF.
- `Enveloppe[point précédent]` : Valeur de l'enveloppe au point daté immédiatement précédent ; zéro avant le premier point. **Unité :** UN du PF.
- `Plancher[d]` : Réserve cible calculée pour la date d, distincte de la demande physique. **Unité :** UN du PF.
- `BesoinProtégé[d]` : Nouvelle tranche de l'enveloppe à couvrir à la date d, sans rajouter la même réserve à chaque point. **Unité :** UN du PF pour la date d.
- `d` : Date du point courant du plan. **Unité :** numéro entier de jour du modèle.
- `j` : Date parcourue dans la somme des besoins du plan, jusqu'à d inclus. **Unité :** numéro entier de jour du modèle.
- `point précédent` : Point du plan immédiatement avant le point d dans l'ordre chronologique. **Unité :** repère daté du même plan.

**Opérateurs et signes :** `somme` : Additionne les besoins bruts du plan aux jours j ne dépassant pas d ; `max` : Retient la plus grande valeur entre l'enveloppe précédente et les besoins cumulés augmentés du plancher ; `=` : vaut la valeur calculée, ou met à jour la quantité dans les lignes successives ; `+` : additionner les valeurs de même unité ; `−` : soustraire la valeur de même unité ; `≤` : inférieur ou égal.

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

**Rappel des variables de ce calcul.**

**Périmètre :** Repli de sécurité d'un PF à Muret, recalculé au jour de décision t puis constant dans ce plan. La fenêtre commence strictement après t ; tous ses jours calendaires sont pris en compte.

- `DuréeSécuritéCalendaire` : Temps calendaire écoulé après t pour compter N jours lundi–vendredi ; un éventuel dernier jour ouvré fractionnaire contribue sa fraction. **Unité :** jours calendaires, éventuellement fractionnaires.
- `t` : Jour où l'on calcule le plan et son repli de sécurité. **Unité :** numéro entier de jour du modèle.
- `N` : Nombre de jours de sécurité source du PF à Muret : 20 pour 268091 ou 25 pour 268967 dans le nominal. **Unité :** jours lundi–vendredi.
- `W` : Durée calendaire arrondie au jour entier supérieur, utilisée pour borner la somme. **Unité :** jours calendaires entiers.
- `Repli` : Plancher constant de remplacement utilisé dans ce plan lorsque la fenêtre future dépasse les prévisions connues. **Unité :** UN du PF.
- `Fixe` : Réserve fixe du PF à Muret, nulle pour les deux PF de la référence active. **Unité :** UN du PF.
- `BesoinBrut[j]` : Quantité de besoin du jour j avant ajout de la réserve. **Unité :** UN du PF pour le jour j.
- `j` : Jour calendaire parcouru, strictement après t et jusqu'à t + W inclus. **Unité :** numéro entier de jour du modèle.

**Opérateurs et signes :** `ceil` : Arrondit la durée calendaire à l'entier supérieur pour obtenir la borne de la fenêtre ; `max` : Retient la plus grande quantité entre réserve fixe et somme des besoins de la fenêtre ; `somme` : Additionne les besoins de tous les jours calendaires j tels que t < j ≤ t + W, week-ends inclus ; `=` : vaut la valeur calculée, ou met à jour la quantité dans les lignes successives ; `+` : additionner les valeurs de même unité ; `≤` : inférieur ou égal ; `<` : strictement inférieur.

Le jour de semaine de `t` vaut `(2 + t) % 7`, avec lundi = 0 et mercredi = 2.
On avance après `t` ; un samedi ou dimanche ajoute un jour écoulé sans consommer
un jour de sécurité. Si N est fractionnaire, le dernier jour ouvré contribue
sa fraction, puis `ceil` borne la fenêtre. Les paramètres source du tableau
sont entiers. Exemple : vendredi, N = 1 → durée calendaire 3, jusqu’au lundi.
L’implémentation est `simulation/engine/model_semantics.py:safety_calendar_days`.

**Rappel des variables de ce calcul.**

**Périmètre :** Repérer le jour de semaine du jour de calcul, avec lundi numéroté 0 et dimanche 6.

- `t` : Nombre de jours calendaires écoulés depuis le 1er janvier 2025, qui est le jour0. **Unité :** numéro de jour du modèle.
- `2` : Numéro du mercredi initial dans la convention lundi 0, mardi 1, mercredi 2. **Unité :** indice de jour de semaine sans unité.
- `7` : Nombre de jours du cycle lundi–dimanche. **Unité :** jours calendaires.
- `N` : Nombre de jours lundi–vendredi de sécurité cité dans l’exemple voisin N=1. **Unité :** jours ouvrés lundi–vendredi.

**Opérateurs et signes :** `+` : Avancer le numéro de jour de semaine à partir du mercredi initial ; `%` : Garder le reste de la division par 7 pour obtenir un indice de 0 à 6.

## 10. L’usine : planifier un OF, puis réellement fabriquer

### 10.1 Le plan daté commande le lancement

Chaque soir, le programme calcule les besoins datés de PF, les stocks,
engagements, protections et lots. Le lendemain, il re-net ce snapshot avec les
quantités réellement disponibles pour autoriser un lancement.

```text
ÀLancerAujourd’hui = somme(propositions admissibles
                           dont DateLancement ≤ aujourd’hui)
```

**Rappel des variables de ce calcul.**

**Périmètre :** Pour un article fabriqué à son usine, au début du jour de lancement : le plan calculé la veille est réexaminé avec la disponibilité réelle du jour. Les campagnes déjà actives conservent leur identité.

- `ÀLancerAujourd’hui` : Quantité totale portée par les nouvelles propositions admissibles dont le lancement est dû au plus tard aujourd'hui. **Unité :** unité de l'article fabriqué au site ; UN pour un PF, G dans les données brutes des deux semi-finis ; KG après conversion cohérente.
- `propositions admissibles` : Quantités des propositions du même article/site dont les conditions de lancement sont satisfaites après réexamen du plan. **Unité :** même unité de l'article fabriqué au site, par proposition.
- `DateLancement` : Date de lancement prévue pour la proposition considérée. **Unité :** numéro de jour du modèle.
- `aujourd’hui` : Jour courant où le programme examine l'autorisation de lancer. **Unité :** numéro entier de jour du modèle.

**Opérateurs et signes :** `somme` : Additionne les quantités des seules propositions admissibles dont la date de lancement ne dépasse pas aujourd'hui ; `=` : vaut la valeur calculée, ou met à jour la quantité dans les lignes successives ; `≤` : inférieur ou égal.

Une campagne active poursuit d’abord son exécution. On ne crée pas simplement
une autre campagne parce qu’une première est bloquée. Au jour 0, il n’existe
pas de snapshot de la veille : pas de nouvelle campagne normale ; les ordres
d’ouverture ont leur propre parcours.

Un signal préparatoire lissé existe aussi :

```text
IntentionBrute = SignalAval + 0,25 × (CibleLocale − StockLocalReconnu)
IntentionLissée = 0,20 × IntentionLisséePrécédente + 0,80 × IntentionBrute
```

**Rappel des variables de ce calcul.**

**Périmètre :** Signal préparatoire pour un même article fabriqué au même site, sur un pas de calcul quotidien d'un jour. Les intentions sont des quantités demandées pour ce pas, équivalentes à des débits en unité/jour ; elles ne donnent pas directement l'autorisation d'un OF, qui relève du plan daté.

- `IntentionBrute` : Quantité de production demandée pour le pas quotidien avant lissage, issue du signal aval et de l'écart à la cible locale. **Unité :** unité de l'article pour ce pas d'un jour ; équivalent UN/jour pour un PF.
- `SignalAval` : Plus grand des deux signaux de quantité pour ce pas reçus par le contrôleur : signal aval propagé et signal prévisionnel multiniveau. **Unité :** même unité de quantité pour le pas quotidien que IntentionBrute.
- `CibleLocale` : Plus grande des protections locales configurées, exprimée en quantité de l'article au site. **Unité :** unité de l'article fabriqué au site ; UN pour un PF.
- `StockLocalReconnu` : Quantité de sortie reconnue par le contrôleur pour ce même article et ce même site ; ce signal de calcul n'est pas une mesure du stock libre immédiatement expédiable. **Unité :** même unité de quantité que CibleLocale.
- `IntentionLissée` : Quantité préparatoire demandée pour le pas quotidien après combinaison de l'intention précédente et de l'intention brute. **Unité :** unité de l'article pour ce pas d'un jour ; équivalent UN/jour pour un PF.
- `IntentionLisséePrécédente` : Quantité lissée conservée du calcul journalier précédent pour le même article/site. **Unité :** même unité de quantité pour un pas quotidien que IntentionLissée.
- `0,25` : Coefficient de commande qui reprend 25 % de l'écart de stock sur le pas d'un jour ; son équivalent en débit est un gain de 0,25 par jour, sans constituer un taux physique industriel. **Unité :** sans unité pour la quantité par pas ; équivalent par jour pour le débit.
- `0,20` : Poids de l'intention lissée précédente dans le nouveau lissage. **Unité :** sans unité.
- `0,80` : Poids de l'intention brute actuelle dans le nouveau lissage. **Unité :** sans unité.

**Opérateurs et signes :** `=` : vaut la valeur calculée, ou met à jour la quantité dans les lignes successives ; `+` : additionner les valeurs de même unité ; `−` : soustraire la valeur de même unité ; `×` : multiplier les valeurs en conservant les unités indiquées.

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

**Rappel des variables de ce calcul.**

**Périmètre :** Dimensionnement d'un lot pour un même article fabriqué à un même site, pour un besoin net strictement positif et un multiple strictement positif. Les lignes conditionnelles ne s'appliquent que si le maximum est défini ou si l'unité est UN.

- `MinimumEffectif` : Plus petite quantité multiple de Multiple qui atteint le minimum configuré. **Unité :** unité de l'article fabriqué au site ; UN pour un PF, G dans les données brutes des deux semi-finis ; KG après conversion cohérente.
- `Minimum` : Quantité minimale de lot configurée pour cet article/site. **Unité :** même unité de l'article fabriqué au site.
- `Multiple` : Pas de quantité strictement positif auquel le lot doit se conformer. **Unité :** même unité de l'article fabriqué au site.
- `MaximumEffectif` : Plus grande quantité multiple de Multiple qui ne dépasse pas le maximum configuré, lorsque ce maximum existe. **Unité :** même unité de l'article fabriqué au site.
- `Maximum` : Plafond configuré pour le lot ou la campagne selon la couche, s'il est renseigné ; il ne borne pas le besoin total de la journée. **Unité :** même unité de l'article fabriqué au site.
- `Lot` : Quantité proposée pour le lot, successivement calculée au multiple, arrondie en UN si nécessaire, puis limitée au maximum effectif lorsqu'il existe. **Unité :** même unité de l'article fabriqué au site ; UN entières si unité UN.
- `BesoinNet` : Quantité encore à couvrir après allocation des ressources et surplus du plan. **Unité :** même unité de l'article fabriqué au site.

**Opérateurs et signes :** `ceil` : Prend l'entier supérieur du nombre de multiples ; appliqué directement à Lot en UN, garantit une quantité entière supérieure ou égale ; `floor` : Prend l'entier inférieur du nombre de multiples autorisé par le maximum ; `max` : Retient la plus grande quantité entre besoin net et minimum effectif ; `min` : Retient la plus petite quantité entre le lot calculé et le maximum effectif ; `=` : vaut la valeur calculée, ou met à jour la quantité dans les lignes successives ; `×` : multiplier les valeurs en conservant les unités indiquées ; `/` : diviser la première valeur par la seconde.

Sans multiple, omettre les opérations de multiple. Pour un lot fixe :

```text
NombreLots = ceil(BesoinNet / LotFixe)
QuantitéCampagne = NombreLots × LotFixe
```

**Rappel des variables de ce calcul.**

**Périmètre :** Dimensionnement d'une campagne à lots fixes pour un même article fabriqué au même site et son besoin net. Le lot fixe est strictement positif ; un besoin nul ne crée aucun lot.

- `NombreLots` : Nombre entier de lots fixes nécessaire pour couvrir le besoin net. **Unité :** nombre de lots.
- `BesoinNet` : Quantité de l'article encore à couvrir après allocation des ressources et surplus du plan. **Unité :** unité de l'article fabriqué au site ; UN pour un PF, G dans les données brutes des deux semi-finis ; KG après conversion cohérente.
- `LotFixe` : Quantité produite par chaque lot fixe de cet article/site. **Unité :** même unité de l'article fabriqué au site, par lot.
- `QuantitéCampagne` : Quantité totale de la campagne formée par ces lots fixes. **Unité :** même unité de l'article fabriqué au site.

**Opérateurs et signes :** `ceil` : Arrondit le nombre de lots à l'entier supérieur pour couvrir le besoin net ; `=` : vaut la valeur calculée, ou met à jour la quantité dans les lignes successives ; `×` : multiplier les valeurs en conservant les unités indiquées ; `/` : diviser la première valeur par la seconde.

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

**Rappel des variables de ce calcul.**

**Périmètre :** Maximum de lot réalisable du produit fini 268091 à Avène, dans le calcul du nombre de multiples admissibles.

- `142485` : Maximum déclaré d’un lot de cet article. **Unité :** UN de produit fini.
- `14400` : Multiple de quantité auquel le lot doit se conformer. **Unité :** UN par multiple.
- `129600` : Plus grand lot composé de multiples entiers qui ne dépasse pas le maximum déclaré. **Unité :** UN de produit fini.

**Opérateurs et signes :** `/` : Calculer le nombre de multiples contenu dans le maximum ; `floor` : Garder le nombre entier inférieur de multiples ; `×` : Reconvertir ce nombre de multiples en UN ; `=` : Le résultat est égal à la quantité calculée.

Le quota de 20 compte les lots engagés lors du lancement, pas uniquement les
lots terminés. La tranche vaut `floor(jour / 7)` : elle ne commence pas le lundi.

**Rappel des variables de ce calcul.**

**Périmètre :** Numéro de la tranche servant au quota de lots pour un même article/site ; ce n’est pas une semaine civile.

- `jour` : Numéro de jour reporté par le modèle, avec le 1er janvier 2025 numéroté 0. **Unité :** jours calendaires depuis l’origine.
- `7` : Longueur d’une tranche de comptage du quota de fabrication. **Unité :** jours calendaires.

**Opérateurs et signes :** `/` : Exprimer le jour en nombre de tranches de 7 jours ; `floor` : Retenir le numéro entier de tranche :0 pour les jours 0 à 6,1 pour7à13.

### 10.3 Le travail est limité par ce qui existe réellement

`Recette[c,p]` est la quantité du composant c par unité du parent p.

```text
PossibleParComposant[c] = LibreComposant[c] / Recette[c,p]
PossibleParMatières = min(PossibleParComposant[c] pour chaque composant requis)
CapacitéRestante = CapacitéJour − TravailDéjàFait − ConditionnementInitialDuJour

TravailExécuté = min(ResteDuLotPhysique, CapacitéRestante, PossibleParMatières)
```

**Rappel des variables de ce calcul.**

**Périmètre :** Exécution physique d'un parent p dans une usine pendant le jour courant. Toutes les quantités de travail portent sur ce parent et cette journée ; chaque composant c garde son unité de stock et n'est disponible qu'une fois.

- `PossibleParComposant[c]` : Quantité du parent p théoriquement réalisable avec le seul stock libre du composant c. **Unité :** unité du parent p ; UN pour un PF, G dans les données brutes des deux semi-finis ; KG après conversion cohérente.
- `LibreComposant[c]` : Quantité du composant c présente, libérée et non réservée au site au moment du travail. **Unité :** unité de stock du composant c au site : UN, G, KG ou M.
- `Recette[c,p]` : Quantité du composant c nécessaire par unité du parent p, convertie dans l'unité du stock de c. **Unité :** unité du composant c par unité du parent p.
- `PossibleParMatières` : Quantité maximale théorique de parent réalisable avec tous les composants requis, avant l'ajustement physique des arrondis UN. **Unité :** unité du parent p.
- `CapacitéRestante` : Quantité de travail sur le parent encore réalisable pendant la journée après le travail déjà exécuté et le conditionnement initial. **Unité :** unité du parent p pour la journée.
- `CapacitéJour` : Quantité maximale de travail configurée pour le parent et le site pendant cette journée ; une capacité absente à Gaillac est non limitante dans ce calcul, sans prouver une capacité industrielle infinie. **Unité :** unité du parent p pour la journée ; capacité journalière issue du débit en UN/jour pour un PF.
- `TravailDéjàFait` : Quantité de travail déjà exécutée aujourd'hui et imputée à cette capacité journalière. **Unité :** unité du parent p pour la journée.
- `ConditionnementInitialDuJour` : Quantité de travail de conditionnement des ordres d'ouverture qui utilise la capacité de cette même journée. **Unité :** unité du parent p pour la journée.
- `TravailExécuté` : Quantité de travail retenue par les limites de lot, de capacité et de matières ; le moteur la réduit si nécessaire pour respecter les arrondis physiques des composants UN. **Unité :** unité du parent p pour la journée.
- `ResteDuLotPhysique` : Quantité de parent qu'il reste à exécuter pour terminer le lot physique courant. **Unité :** unité du parent p.
- `c` : Identifiant de chacun des composants requis pour fabriquer le parent p sur ce site. **Unité :** identifiant sans unité.
- `p` : Identifiant de l'article parent fabriqué, produit fini ou semi-fini. **Unité :** identifiant sans unité.

**Opérateurs et signes :** `min` : Retient la plus petite limite : d'abord parmi les composants requis, puis entre reste du lot, capacité encore disponible et possibilités matières ; `=` : vaut la valeur calculée, ou met à jour la quantité dans les lignes successives ; `−` : soustraire la valeur de même unité ; `/` : diviser la première valeur par la seconde.

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

**Rappel des variables de ce calcul.**

**Périmètre :** Explosion des nouvelles propositions de fabrication, pour un composant et son site consommateur, à la date proposée de lancement des parents.

- `c` : Indice de l'article composant requis au site de fabrication du parent. **Unité :** identifiant d'article.
- `p` : Indice de l'article parent fabriqué à ce site ; plusieurs parents peuvent partager c. **Unité :** identifiant d'article.
- `d` : Date proposée de lancement du parent, qui date ici le besoin du composant. **Unité :** date (indice de jour calendaire).
- `QuantitéRecette[c,p]` : Quantité source du composant c requise pour la base de recette du parent p. **Unité :** unité source du composant (G, KG, M ou UN).
- `QuantitéBaseParent[p]` : Quantité de parent p à laquelle se rapporte la quantité source de recette. **Unité :** unité du parent (UN ou unité de masse).
- `Recette[c,p]` : Quantité de composant c par unité de parent p, après conversion dans l'unité de stock du composant. **Unité :** unité de stock du composant / unité du parent.
- `QuantitéNouvellePropositionParent[p,d]` : Quantité de parent p portée par les nouvelles propositions dont le lancement est prévu à d au site considéré. **Unité :** unité du parent.
- `BesoinRecette[c,d]` : Total de composant c nécessaire aux nouvelles propositions des parents lancés à d, au même site consommateur. **Unité :** unité de stock du composant.

**Opérateurs et signes :** `convertir_dans_unité_du_stock_composant` : Convertir l'unité du numérateur composant en unité de stock, en conservant le dénominateur par unité de parent ; 1 KG vaut 1 000 G ; `/` : Diviser la quantité de composant par sa base de parent pour obtenir le coefficient par unité de parent ; `×` : Multiplier la quantité de parent par le coefficient de recette ; `somme` : Additionner les contributions de tous les parents et nouvelles propositions concernés, au même composant/site et à la même date ; `[c,p] et [c,d]` : Repérer respectivement le couple composant/parent et le couple composant/date ; le site est celui du périmètre indiqué ; `=` : Définir la valeur calculée à gauche à partir de l'expression à droite.

La date de besoin du composant est la date de lancement proposée du parent.
Pour une campagne déjà engagée, les composants du travail encore à faire sont
demandés une fois au prochain jour ; les composants déjà incorporés à l’encours
ne sont pas demandés à nouveau.

```text
BesoinCampagneRestante[c,t+1] = ResteÀExécuterParent × Recette[c,p]
RéceptionFermeSortieCampagne = ResteÀExécuterParent + EncoursDéjàExécuté
```

**Rappel des variables de ce calcul.**

**Périmètre :** Campagne déjà engagée d'un parent p à son site de fabrication ; le besoin de composants encore à incorporer est daté au prochain jour du plan.

- `c` : Article composant requis par la campagne au site de fabrication. **Unité :** identifiant d'article.
- `p` : Article parent de la campagne engagée. **Unité :** identifiant d'article.
- `t` : Jour courant de calcul du plan ; le jour 0 est le 1er janvier 2025. **Unité :** indice de jour calendaire.
- `t+1` : Jour suivant le calcul courant, auquel est demandé le composant du travail restant. **Unité :** indice de jour calendaire.
- `ResteÀExécuterParent` : Quantité de parent de cette campagne qui reste à fabriquer et dont les composants ne sont pas encore incorporés. **Unité :** unité du parent.
- `Recette[c,p]` : Quantité du composant c, dans son unité de stock, par unité de parent p. **Unité :** unité de stock du composant / unité du parent.
- `BesoinCampagneRestante[c,t+1]` : Quantité de c encore requise par la campagne et demandée une seule fois au prochain jour, sans redemander la matière déjà incorporée. **Unité :** unité de stock du composant.
- `EncoursDéjàExécuté` : Quantité de parent déjà travaillée dans la campagne, avec composants déjà incorporés, qui n'est pas encore une sortie physique achevée. **Unité :** unité du parent.
- `RéceptionFermeSortieCampagne` : Quantité totale de sortie attendue de cette campagne engagée, retenue comme réception ferme du plan ; elle n'est pas encore du stock physique libre. **Unité :** unité du parent.

**Opérateurs et signes :** `×` : Convertir le travail parent restant en quantité de composant par la recette ; `+` : Additionner les quantités de parent restant à faire et déjà exécutées ; dans t+1, avancer d'un jour calendaire ; `[c,t+1] et [c,p]` : Repérer la demande de composant du prochain jour et son coefficient pour le parent ; `=` : Définir le besoin restant ou la réception ferme attendue.

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

**Rappel des variables de ce calcul.**

**Périmètre :** Une opération physique de fabrication d'un parent p, au site consommateur et au jour de son exécution ; l'arrondi UN se fait par opération.

- `c` : Article composant prélevé au site de fabrication. **Unité :** identifiant d'article.
- `p` : Article parent réellement travaillé pendant cette opération. **Unité :** identifiant d'article.
- `TravailExécutéParent` : Quantité de parent effectivement travaillée pendant l'opération considérée. **Unité :** unité du parent.
- `Recette[c,p]` : Quantité de composant c par unité de parent p, exprimée dans l'unité du stock composant. **Unité :** unité de stock du composant / unité du parent.
- `ConsommationThéorique[c]` : Quantité de c issue de la multiplication par la recette avant l'arrondi physique éventuel. **Unité :** unité de stock du composant ; UN éventuellement fractionnaires pour la théorie.
- `PrélèvementPhysique[c]` : Quantité de c réellement retirée du stock lors de cette opération ; entière si le composant est compté en UN. **Unité :** UN entières, ou unité de masse ou de longueur du stock.
- `UN` : Unité de comptage d'une pièce physique indivisible. **Unité :** unité physique.
- `masse ou longueur` : Branche où la quantité conserve sa précision de masse ou de longueur au lieu d'être arrondie en pièces. **Unité :** G, KG ou M selon le composant.

**Opérateurs et signes :** `×` : Multiplier le travail parent par le coefficient composant par unité de parent ; `ceil` : Prendre le plus petit entier supérieur ou égal à la consommation théorique, séparément pour chaque opération UN ; `si` : Choisir la branche selon l'unité physique du composant ; `[c] et [c,p]` : Identifier le composant prélevé et sa recette pour le parent ; `=` : Définir la théorie ou la quantité physique prélevée.

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

**Nombres et unités de cet exemple.**

**Périmètre :** Exemple des recettes actives pour une campagne de 268091 à Avène de 129 600 UN ; les prélèvements présentés correspondent à un seul passage physique.

- `693055` : Article semi-fini consommé à Avène pour fabriquer 268091, même s'il est fabriqué à Gaillac. **Unité :** identifiant d'article.
- `001757` : Article composant consommé à Avène pour fabriquer 268091. **Unité :** identifiant d'article.
- `426331` : Article composant compté en pièces et consommé à Avène pour fabriquer 268091. **Unité :** identifiant d'article.
- `129600` : Quantité de parent 268091 fabriquée dans l'exemple ; le même volume sert aux trois calculs. **Unité :** UN de parent 268091.
- `406` : Quantité source de 693055 requise pour la base de recette de 1 000 UN de parent. **Unité :** G de 693055 pour 1 000 UN de 268091.
- `1624` : Quantité source de 001757 requise pour la base de recette de 1 000 UN de parent. **Unité :** G de 001757 pour 1 000 UN de 268091.
- `11` : Quantité source de 426331 requise pour la base de recette de 1 000 UN de parent. **Unité :** UN de 426331 pour 1 000 UN de 268091.
- `1000` : Dénominateur de recette : chaque quantité source indiquée se rapporte à 1 000 unités du parent ; ce n'est pas ici une conversion de masse. **Unité :** UN de parent 268091.
- `52617,6 G` : Consommation théorique de 693055 pour cette campagne, exprimée en grammes. **Unité :** G de 693055.
- `52,6176 KG` : Même consommation de 693055 exprimée en kilogrammes après division des grammes par 1 000. **Unité :** KG de 693055.
- `210,4704 KG` : Consommation théorique de 001757 pour cette campagne, soit 210 470,4 grammes convertis en kilogrammes. **Unité :** KG de 001757.
- `1425,6 UN théoriques` : Résultat de recette avant arrondi pour 426331 ; ce nombre fractionnaire n'est pas un prélèvement physique de pièces. **Unité :** UN théoriques de 426331.
- `1426 UN prélevées` : Quantité entière de 426331 retirée du stock par le plafond de 1 425,6 si toute l'opération se fait en un passage. **Unité :** UN physiques de 426331.
- `G` : Gramme, unité de masse des quantités source utilisées dans les deux premiers calculs. **Unité :** gramme.
- `KG` : Kilogramme ; un kilogramme équivaut à 1 000 grammes. **Unité :** kilogramme.
- `UN` : Unité de comptage du parent ou du composant explicitement nommé. **Unité :** pièce.

**Opérateurs et signes :** `× et /` : Multiplier les UN de parent par la quantité source de composant, puis diviser par la base de 1 000 UN de parent ; `=` : Exprimer la même masse calculée dans l'unité affichée ; la conversion G vers KG divise la valeur numérique par 1 000 ; `→ (ceil)` : Passer de la théorie à son plafond entier pour le prélèvement de pièces en une opération ; plusieurs passages ont chacun leur propre plafond ; `×` : multiplier les valeurs en conservant les unités indiquées ; `/` : diviser la première valeur par la seconde.

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

**Rappel des variables de ce calcul.**

**Périmètre :** Un même article composant au même site et à la même échéance ; sommer seulement des usages distincts partageant son stock.

- `BesoinRecetteDesProduitsModélisés` : Somme des besoins de recette des parents explicitement modélisés pour ce composant/site et cette échéance. **Unité :** unité de stock du composant.
- `AutresUsagesDistincts` : Besoins datés des autres usages du même composant/site, identifiés séparément pour éviter de compter une recette deux fois. **Unité :** même unité de stock du composant.
- `BesoinComposantTotal` : Total des deux catégories de besoins au composant/site et à l'échéance considérés. **Unité :** unité de stock du composant.

**Opérateurs et signes :** `+` : Additionner des quantités distinctes dans la même unité, au même article/site et à la même échéance ; `=` : Définir le besoin total ; cette égalité ne constitue pas à elle seule une consommation physique.

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

**Rappel des variables de ce calcul.**

**Périmètre :** Adaptation historique E4 : calcul séparé pour chacun des neuf couples article/site du protocole et chacune de ses fenêtres hebdomadaires source couvertes, avec la dernière version connue au jour de décision. Le complément quotidien concerne seulement les jours futurs couverts de cette même fenêtre.

- `BesoinPropre` : Quantité de besoin calculée par le modèle pour le couple article/site et la fenêtre hebdomadaire considérés, hors réserves. **Unité :** unité de stock de l'article sur la fenêtre.
- `BesoinIndustrielConnu` : Quantité de besoin industriel de la dernière version déjà connue pour exactement le même article/site et la même fenêtre couverte. **Unité :** même unité de stock sur la même fenêtre.
- `ComplémentPlanifié` : Quantité positive éventuelle ajoutée au plan pour atteindre le besoin industriel connu quand il dépasse le besoin propre ; elle ne constitue pas un prélèvement physique. **Unité :** unité de stock de l'article sur la fenêtre.
- `BesoinPlanifié` : Besoin total retenu pour ce couple et cette fenêtre, égal au plus grand des besoins propre et industriel connu, avec les réserves conservées séparément. **Unité :** unité de stock de l'article sur la fenêtre.
- `ComplémentJour` : Part du seul complément planifié répartie sur un jour futur couvert de la même fenêtre ; le total de ces parts conserve le complément hebdomadaire. **Unité :** quantité de l'article affectée à un pas journalier.
- `NombreJoursCouverts` : Nombre de jours futurs couverts entre lesquels est réparti le complément de la fenêtre article/site considérée. **Unité :** nombre de jours.
- `0` : Borne nulle empêchant un complément négatif. **Unité :** même unité de quantité que les besoins.

**Opérateurs et signes :** `max` : Retenir la plus grande quantité parmi les arguments, sur cette fenêtre article/site ; ne pas prendre ce maximum séparément par jour ou sur l'année ; `− et +` : Calculer l'écart entre besoins comparables, puis ajouter le seul complément au besoin propre ; `/` : Dans la formule inline ComplémentJour, répartir le complément entre les jours futurs couverts, en conservant son total ; `=` : Définir le complément et le besoin planifié, ou exprimer deux écritures équivalentes du même total ; `+` : additionner les valeurs de même unité ; `−` : soustraire la valeur de même unité.

Les réserves restent séparées. Ce complément de plan n’est pas une consommation
physique ajoutée immédiatement au stock. Le maximum ne se calcule ni séparément
chaque jour ni sur l’horizon annuel entier. Hors des fenêtres source couvertes,
les besoins existants restent inchangés.
Le complément est réparti sur les jours futurs couverts de la fenêtre :
`ComplémentJour = ComplémentPlanifié / NombreJoursCouverts`, avec conservation
du total dans l’arithmétique utilisée. Les besoins propres existants gardent
leurs dates ; ce sont les autres besoins prévisionnels remplacés qui changent.

**Rappel des variables de ce calcul.**

**Périmètre :** Répartition du complément de planification E4 pour le même article/site et la même fenêtre hebdomadaire couverte.

- `ComplémentJour` : Part du complément à planifier sur un jour de cette fenêtre, pas un prélèvement physique immédiat. **Unité :** unité du composant par jour couvert.
- `ComplémentPlanifié` : Quantité de la fenêtre restant à ajouter après comparaison des besoins propres et industriels connus. **Unité :** unité du composant.
- `NombreJoursCouverts` : Nombre de jours futurs renseignés dans cette fenêtre et admis dans la répartition. **Unité :** nombre de jours calendaires couverts.

**Opérateurs et signes :** `/` : Partager le total de la fenêtre entre ses jours couverts en conservant le total ; `=` : Le résultat est égal à la quantité calculée.

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

**Rappel des variables de ce calcul.**

**Périmètre :** Adaptation historique F3 non cumulative en mode legacy_residual : un seul article/site et sa semaine source, évalués à la clôture du dimanche. La première semaine partielle conserve sa convention source.

- `BudgetScan3Semaine` : Consommation enregistrée dans Sorties_article_scan3 pour cet article/site et cette semaine source ; une valeur absente reste inconnue. **Unité :** unité de stock de l'article sur la semaine.
- `ConsommationPropreSemaine` : Quantité du même article réellement consommée par les fabrications modélisées au même site pendant cette semaine, selon le registre physique. **Unité :** même unité de stock sur la même semaine.
- `NouveauRésiduel` : Complément de consommation demandé à cette clôture pour rapprocher le budget de semaine et la consommation propre ; son exécution dépend du stock disponible. **Unité :** unité de stock de l'article.
- `0` : Borne nulle empêchant de demander un résiduel négatif. **Unité :** même unité de quantité que le budget.

**Opérateurs et signes :** `−` : Soustraire la consommation propre du budget du même article/site et de la même semaine ; `max` : Garder l'écart seulement s'il est positif, sinon zéro ; `=` : Définir une nouvelle demande résiduelle, distincte d'une consommation déjà exécutée.

Pour les couples cumulatifs du protocole :

```text
NouveauRésiduel = max(0,
    BudgetScan3Cumulé − ConsommationPropreCumulée − RésiduelsDéjàDemandés)
```

**Rappel des variables de ce calcul.**

**Périmètre :** Adaptation historique F3 pour un couple article/site déclaré cumulatif par le protocole ; tous les cumuls partagent le même début de cumul source et la même clôture hebdomadaire.

- `BudgetScan3Cumulé` : Consommation enregistrée cumulée de l'article/site depuis l'origine fixée par le protocole jusqu'à cette clôture ; un budget absent n'est pas zéro. **Unité :** unité de stock de l'article sur la fenêtre cumulée.
- `ConsommationPropreCumulée` : Consommation physique propre des fabrications modélisées, cumulée pour le même article/site sur exactement la même fenêtre. **Unité :** même unité de stock sur la même fenêtre cumulée.
- `RésiduelsDéjàDemandés` : Total des demandes résiduelles déjà créées pour ce cumul article/site, y compris celles encore en attente de stock, pour éviter de les demander à nouveau. **Unité :** unité de stock de l'article.
- `NouveauRésiduel` : Nouvelle quantité résiduelle à demander à cette clôture après déduction de la consommation propre et de tous les résiduels déjà demandés. **Unité :** unité de stock de l'article.
- `0` : Borne nulle empêchant une nouvelle demande négative. **Unité :** même unité de quantité que les cumuls.

**Opérateurs et signes :** `−` : Déduire les quantités propres et déjà demandées du même budget cumulé article/site ; `max` : Retenir l'écart positif restant, sinon zéro ; `=` : Définir le nouveau résiduel ; le retard des résiduels précédents conserve son identité.

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

**Rappel des variables de ce calcul.**

**Périmètre :** Pour 338929 à Avène, 333362 à Gien ou 042342 à Gien : une semaine source documentée d'un seul couple article/site, avec le programme déjà connu à la décision. Les besoins engagés gardent leurs dates.

- `besoins composants déjà engagés de la semaine` : Quantités de l'article/site déjà requises par les campagnes engagées, dont les dates de besoin appartiennent à la semaine considérée. **Unité :** UN de l'article pour cette semaine.
- `EngagéSemaine` : Total de ces besoins composants engagés pour le couple et la semaine considérés. **Unité :** UN de l'article sur la semaine.
- `ProgrammeIndustrielSemaine` : Quantité du programme industriel connu de ce même article/site pour la même semaine documentée. **Unité :** UN du même article sur la même semaine.
- `ComplémentSemaine` : Quantité prévisionnelle complémentaire au-delà des engagements, répartie de façon conservante sur la fenêtre sans déplacer les besoins engagés. **Unité :** UN de l'article sur la semaine.
- `BesoinPlanifiéSemaine` : Total retenu pour la semaine, égal au plus grand des engagements et du programme industriel ; les réserves restent séparées. **Unité :** UN de l'article sur la semaine.
- `0` : Borne nulle empêchant un complément hebdomadaire négatif. **Unité :** UN du même article.

**Opérateurs et signes :** `somme` : Additionner les besoins composants engagés du même article/site dont les dates sont dans cette semaine ; `−` : Soustraire les besoins déjà engagés du programme de la même semaine ; `max` : Retenir le plus grand argument en quantité, sur cette seule semaine documentée ; `=` : Définir les totaux hebdomadaires ; une semaine absente ne devient pas une semaine de besoin nul.

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

**Rappel des variables de ce calcul.**

**Périmètre :** Voyage d'un lot semi-fini de Gaillac vers Avène pour 693055 ou vers Gien pour 773474 ; dates et durées sont propres au lot et à sa liaison.

- `DateFinLot` : Date de fin physique du lot fabriqué à Gaillac, avant son blocage de libération. **Unité :** date (indice de jour calendaire).
- `BlocageGaillac` : Durée de blocage après fin à Gaillac : 28 pour 693055 ou 33 pour 773474, comptés du lundi au vendredi. **Unité :** jours lundi–vendredi.
- `DisponibleGaillac` : Date à laquelle le lot est libéré et utilisable à Gaillac après le blocage ; ce n'est pas automatiquement son départ. **Unité :** date (indice de jour calendaire).
- `DateDépart` : Date du départ physique du lot de Gaillac sur sa liaison vers la destination. **Unité :** date (indice de jour calendaire).
- `TransportCalendaire` : Durée départ→réception : 7 jours pour 693055 vers Avène, hypothèse déclarée, ou 10 jours pour 773474 vers Gien. **Unité :** jours calendaires.
- `RéceptionDestination` : Date d'arrivée physique à Avène ou Gien ; le lot peut encore être bloqué après cette réception. **Unité :** date (indice de jour calendaire).
- `TraitementDestination` : Durée réception→disponibilité à destination : 7 pour 693055 à Avène ou 6 pour 773474 à Gien, comptés du lundi au vendredi. **Unité :** jours lundi–vendredi.
- `DisponibleDestination` : Date à laquelle le lot reçu devient utilisable au site destinataire après son traitement. **Unité :** date (indice de jour calendaire).

**Opérateurs et signes :** `AjouterOuvrés` : Avancer après la date de départ du calcul en ne comptant que les jours lundi–vendredi jusqu'à épuiser la durée indiquée ; `+` : Ajouter une durée de transport en jours calendaires à la date du départ physique ; `=` : Définir chacune des dates successives, sans confondre fin, départ, réception et disponibilité.

Ces délais de libération source sont des conventions explicites du modèle,
pas une identification certaine de toutes les étapes industrielles. Les
70 jours de référence FIA de `693055` ne deviennent pas 70 jours de transport
en plus des délais du tableau.

Les deux liaisons sont revues lorsque `jour % 7 = 0`, donc les mercredis avec
l’origine actuelle. Le besoin de transfert vient du netting de la destination.
Il crée un besoin au site origine, daté à son départ prévu.

**Rappel des variables de ce calcul.**

**Périmètre :** Autorisation de revue des transferts Gaillac→Avène ou Gaillac→Gien, avec l’origine de temps de cette référence.

- `jour` : Numéro de jour du modèle depuis le mercredi 1er janvier 2025 numéroté 0. **Unité :** jours calendaires depuis l’origine.
- `7` : Période de revue de la liaison interne considérée. **Unité :** jours calendaires.
- `0` : Reste exigé pour autoriser une revue : jours 0, 7, 14, etc. **Unité :** sans unité.

**Opérateurs et signes :** `%` : Calculer le reste de la division entière ; `=` : Ici tester que le reste vaut zéro ; ce n’est pas une affectation.

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

**Rappel des variables de ce calcul.**

**Périmètre :** Protection additive d'achat externe d'un seul article/site, dans le plan calculé au jour t ; avancer la date de planification conserve les dates de consommation physique.

- `t` : Jour courant de décision, qui borne au présent les besoins avancés ; le jour 0 est le 1er janvier 2025. **Unité :** indice de jour calendaire.
- `d` : Date originale du besoin physique de l'article au site destinataire. **Unité :** date (indice de jour calendaire).
- `u` : Date de besoin anticipé qui regroupe les besoins physiques ayant la même date protégée. **Unité :** date (indice de jour calendaire).
- `Sécurité` : Durée de protection source du couple article/site, retirée à la date physique en comptant seulement lundi–vendredi. **Unité :** jours lundi–vendredi.
- `DateProtégée[d]` : Date avancée de planification du besoin physique daté d, sans jamais remonter avant t. **Unité :** date (indice de jour calendaire).
- `BesoinPhysique[d]` : Quantité à consommer réellement à d au même article/site, conservée à cette date dans le bilan physique. **Unité :** unité de stock de l'article.
- `BesoinAnticipé[u]` : Total des quantités de besoins physiques dont la date protégée est u, utilisé pour planifier les achats. **Unité :** unité de stock de l'article.
- `BesoinAnticipé[t]` : Besoin anticipé regroupé au jour courant, auquel la réserve fixe est ajoutée une seule fois dans le plan. **Unité :** unité de stock de l'article.
- `Fixe` : Réserve de sécurité en quantité du couple article/site, distincte d'une consommation physique. **Unité :** unité de stock de l'article.

**Opérateurs et signes :** `RetirerOuvrés` : Reculer avant d en ne comptant que les jours lundi–vendredi jusqu'à retirer la durée de sécurité ; `max` : Retenir la plus tardive entre le jour courant et la date avancée ; `somme ... dont` : Additionner les seuls besoins physiques dont la date protégée correspond exactement à u ; `+` : Ajouter la réserve fixe une seule fois à la quantité anticipée au jour t ; `[d], [u] et [t]` : Repérer les valeurs par date de besoin physique, date de planification ou jour courant ; `=` : Définir une date protégée ou une quantité anticipée ; dans la dernière ligne, mettre à jour la valeur déjà regroupée à t.

La dernière ligne met à jour le cumul déjà calculé pour aujourd’hui : elle y ajoute la réserve fixe une seule fois.

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

**Rappel des variables de ce calcul.**

**Périmètre :** Recherche d'une commande nouvelle pour une offre fournisseur, un article et son site destinataire ; seules les dates de commande admissibles au calendrier et encore possibles sont examinées.

- `r` : Date candidate de commande, autorisée par la revue et les calendriers, au plus tôt au jour courant. **Unité :** date (indice de jour calendaire).
- `DélaiFournisseur` : Durée nominale entre commande et réception physique pour l'offre considérée, sans y ajouter à nouveau un transport déjà inclus. **Unité :** jours calendaires.
- `RéceptionCandidate[r]` : Date de réception physique prévue si la commande est passée à r. **Unité :** date (indice de jour calendaire).
- `Traitement` : Durée à compter après la réception physique pour rendre l'article utilisable au site destinataire. **Unité :** jours lundi–vendredi.
- `DisponibleCandidate[r]` : Date de disponibilité utilisable résultant de la commande candidate r, après réception et traitement. **Unité :** date (indice de jour calendaire).
- `DateProtégée` : Échéance anticipée du besoin d'achat pour cet article/site, déjà calculée avec sa protection. **Unité :** date (indice de jour calendaire).
- `DateCommande` : Dernière date candidate admissible donnant une disponibilité au plus tard à l'échéance ; si aucune n'y parvient, le parcours décrit choisit la première date encore possible et trace le retard. **Unité :** date (indice de jour calendaire).

**Opérateurs et signes :** `+` : Ajouter la durée commande→réception en jours calendaires à la date candidate ; `AjouterOuvrés` : Avancer après la réception en ne comptant que lundi–vendredi pour le traitement ; `dernière date ... telle que` : Choisir la date la plus tardive parmi les candidates qui satisfont le calendrier et l'échéance ; `≤` : Exiger une disponibilité avant ou à la date protégée ; `[r]` : Associer chaque date de réception ou disponibilité à la commande candidate r qui la produit ; `=` : Définir les dates candidates puis la date de commande retenue.

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

**Rappel des variables de ce calcul.**

**Périmètre :** Test expérimental de secours pour 001848 à Avène, sur une allocation non protégée dans la branche additive ; le besoin testé est déjà avancé par la sécurité.

- `DateBesoinAnticipée` : Échéance protégée de l'allocation de 001848 à Avène, déjà anticipée ; ce n'est pas la date originale de consommation physique. **Unité :** date (indice de jour calendaire).
- `PremièreDisponibilitéNouvelAchatPrincipal` : Première date utilisable qu'un nouvel achat au fournisseur principal VD0951020A pourrait atteindre depuis la décision actuelle. **Unité :** date (indice de jour calendaire).
- `DateAllouéeActuelle` : Date utilisable actuellement affectée à cette allocation par le plan principal. **Unité :** date (indice de jour calendaire).
- `DisponibilitéSecours` : Date utilisable que pourrait offrir un nouvel achat auprès du secours VD0519670A pour cette allocation. **Unité :** date (indice de jour calendaire).

**Opérateurs et signes :** `<` : Vérifier que l'échéance anticipée précède strictement la première disponibilité d'un nouvel achat principal ; `max` : Retenir la plus tardive entre l'échéance anticipée et la disponibilité du secours ; `>` : Vérifier que l'allocation actuelle arrive strictement après cette borne, donc que le secours peut améliorer son service ; `et` : Exiger simultanément les deux conditions pour cette allocation non protégée.

La quantité à couvrir est la somme des allocations améliorables. La réserve
fixe seule ne déclenche pas le secours. Les engagements fermes sont protégés
du rachat : même tardifs, ils ne sont pas automatiquement doublés par un secours.
Il n’existe pas de seuil nominal supplémentaire « X jours » ou « Y % ».

Le lot de secours et son surplus sont crédités avant de recalculer le principal.
Exemple inventé, après anticipation : stock 1 000 KG, besoin 3 000 puis 2 000 ;
secours possible avant le premier besoin, lot de 4 000. On achète 4 000 :
`1000 + 4000 − 3000 − 2000 = 0`. Pas besoin d’ajouter un lot principal de 6 000.

**Rappel des variables de ce calcul.**

**Périmètre :** Exemple inventé d’achat de secours, après anticipation des dates, pour un même composant au même site.

- `1000` : Stock utilisable présent avant cet achat. **Unité :** KG.
- `4000` : Quantité achetée au secours et disponible avant le premier besoin. **Unité :** KG.
- `3000` : Premier besoin à couvrir. **Unité :** KG.
- `2000` : Second besoin, couvert grâce au surplus du même lot de secours. **Unité :** KG.
- `0` : Quantité restant après couverture des deux besoins. **Unité :** KG.

**Opérateurs et signes :** `+` : Ajouter le lot de secours au stock utilisable ; `−` : Retirer successivement les quantités nécessaires pour les deux besoins ; `=` : Le résultat est égal à la quantité calculée.

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

**Rappel des variables de ce calcul.**

**Périmètre :** Branche des parts conventionnelles pour un article/site multi-source, au jour de décision et pour un même groupe de besoins nets ; le fournisseur est traité après ceux déjà examinés.

- `ResteAprèsAchatsPrécédents` : Quantité du groupe de besoins restant à couvrir après les achats et surplus crédités des fournisseurs précédemment traités. **Unité :** unité de stock de l'article.
- `BesoinNetGroupé` : Quantité nette initiale du groupe de besoins de cet article/site servant de base à la répartition. **Unité :** unité de stock de l'article.
- `PartFournisseur` : Poids conventionnel attribué au fournisseur courant parmi les offres triées ; il ne constitue pas une part industrielle observée. **Unité :** sans unité, dans la même échelle que les autres parts.
- `SommeParts` : Somme des poids conventionnels des offres incluses dans cette répartition. **Unité :** sans unité, même échelle que PartFournisseur.
- `CibleFournisseur` : Quantité visée pour ce fournisseur avant sa lotification, bornée par ce qui reste à couvrir. **Unité :** unité de stock de l'article.

**Opérateurs et signes :** `× et /` : Appliquer au besoin net groupé la fraction PartFournisseur/SommeParts ; `min` : Retenir la plus petite quantité entre ce partage théorique et le besoin encore découvert ; `=` : Définir une cible avant lotification ; les achats physiques finaux peuvent s'écarter des parts ; `×` : multiplier les valeurs en conservant les unités indiquées ; `/` : diviser la première valeur par la seconde.

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

**Lecture de ce schéma.** Cycle d'un nouvel achat pour un article, un fournisseur et un site destinataire ; les états sont successifs et conservent l'identité de l'engagement.

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

**Rappel des variables de ce calcul.**

**Périmètre :** Essai de report d'une seule réception dont l'engagement possède une permission explicite, pour son article/site, dans la fenêtre de besoins continûment connue du plan courant.

- `cette réception` : Réception de l'ordre autorisé à être reporté ; elle est retirée seulement du plan d'essai, en gardant identité et quantité de l'engagement. **Unité :** événement daté et quantité dans l'unité de l'article.
- `stock` : Stock reconnu de l'article au site à l'entrée du calcul d'essai, conservé quand on retire la réception étudiée. **Unité :** unité de stock de l'article.
- `j` : Jour successif examiné dans la fenêtre de couverture connue du même article/site. **Unité :** indice de jour calendaire.
- `j−1` : Jour immédiatement précédent dans cette projection journalière. **Unité :** indice de jour calendaire.
- `Solde[j−1]` : Solde projeté après le jour précédent, initialisé avec le stock reconnu au début de la projection. **Unité :** unité de stock de l'article.
- `AutresRéceptionsDisponibles[j]` : Quantités des réceptions autres que celle étudiée qui deviennent utilisables à j pour le même article/site. **Unité :** unité de stock de l'article.
- `Besoins[j]` : Quantité de besoins datés à j conservée dans le plan d'essai du même article/site. **Unité :** unité de stock de l'article.
- `Solde[j]` : Solde projeté après les disponibilités et besoins du jour j en l'absence de la réception étudiée. **Unité :** unité de stock de l'article.
- `Plancher[j]` : Réserve minimale protégée à j pour cet article/site, à laquelle est comparé le solde. **Unité :** unité de stock de l'article.
- `premier j où Solde[j] < Plancher[j]` : Première date où l'absence de la réception fait passer le solde sous la protection exigée. **Unité :** date (indice de jour calendaire).
- `borne de couverture continue connue` : Fin de la fenêtre sans trou d'information utilisable pour borner le report lorsqu'aucun déficit protégé n'apparaît. **Unité :** date (indice de jour calendaire).
- `date contractuelle autorisée` : Date limite la plus précoce permise par le contrat de report de cet engagement. **Unité :** date (indice de jour calendaire).
- `disponibilité` : Nouvelle date utilisable proposée par le planificateur pour l'ordre étudié, sous les permissions de report ; le réseau est ensuite recalculé. **Unité :** date (indice de jour calendaire).

**Opérateurs et signes :** `+ et −` : Ajouter au solde les seules autres réceptions utilisables, puis déduire les besoins du jour ; dans j−1, reculer d'un jour ; `<` : Détecter un solde strictement inférieur au plancher du même jour ; `[j] et [j−1]` : Repérer chaque quantité par sa date dans la projection journalière ; `Chercher le premier` : Parcourir les jours dans l'ordre chronologique et retenir le premier déficit protégé ; `ou ... si aucun ... sans passer avant` : Utiliser la borne de couverture connue en l'absence de déficit, puis respecter la limite contractuelle du report ; `=` : Définir le solde de chaque jour du plan d'essai, sans créer de mouvement physique ; `+` : additionner les valeurs de même unité ; `−` : soustraire la valeur de même unité.

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

**Rappel des variables de ce calcul.**

**Périmètre :** Dimensionnement d'un nouvel achat pour une offre fournisseur et un article au jour courant ; la capacité fournisseur/article est partagée entre sites servis. Nominal et scénarios de risque restent distincts. Le pas de calcul vaut un jour.

- `FiabilitéNominale` : Fraction nominale de quantité attendue pour l'offre ; elle vaut 1 dans le bundle nominal décrit. **Unité :** sans unité.
- `FacteurFiabilité` : Multiplicateur de fiabilité du scénario effectivement activé, neutre quand aucun risque correspondant n'est appliqué. **Unité :** sans unité.
- `FacteurQualité` : Multiplicateur de qualité du scénario effectivement activé, neutre dans le nominal sans incident. **Unité :** sans unité.
- `RendementEffectif` : Fraction de la quantité commandée effectivement reçue après composition et bornage de la fiabilité et de la qualité. **Unité :** sans unité.
- `0,01 et 1` : Bornes inférieure et supérieure du rendement effectif. **Unité :** sans unité.
- `CapacitéJour` : Capacité maximale journalière configurée du fournisseur pour cet article, avant multiplicateurs ; dans cette écriture elle désigne la quantité correspondant au pas d'un jour. **Unité :** unité de l'article sur le pas de 1 jour (débit configuré en unité de l'article / jour).
- `Disponibilité` : Fraction de la capacité fournisseur disponible pour le jour courant dans le scénario activé. **Unité :** sans unité.
- `FacteurCapacité` : Multiplicateur de capacité du scénario activé, neutre dans le nominal sans risque correspondant. **Unité :** sans unité.
- `QuantitéDéjàEngagéeAujourd’hui` : Quantité de l'article déjà engagée auprès de ce fournisseur pendant le jour courant, tous sites destinataires partageant cette capacité compris. **Unité :** unité de l'article sur le pas journalier.
- `CapacitéRestanteFournisseur` : Quantité brute encore commandable pendant ce même jour après prise en compte des facteurs et des engagements déjà pris ; ce n'est pas un taux à soustraire d'une quantité. **Unité :** unité de l'article sur le pas journalier.
- `QuantitéNetteVoulue` : Quantité utilisable visée par le plan pour le nouvel achat au site destinataire. **Unité :** unité de l'article.
- `FiabilitéPlanifiée` : Fraction de fiabilité que la politique autorise le MRP à anticiper pour grossir l'achat ; elle vaut 1 dans le nominal décrit. **Unité :** sans unité.
- `DemandéBrut` : Quantité brute demandée avant contrainte de standard, capacité et arrondi en UN, pour viser la quantité nette souhaitée. **Unité :** unité de l'article.
- `Standard` : Quantité par lot standard de l'offre, utilisée ici seulement lorsqu'elle est positive et déclarée contraignante. **Unité :** unité de l'article / lot standard.
- `LotsDemandés` : Nombre entier de lots standards nécessaire pour atteindre la demande brute. **Unité :** nombre de lots standards.
- `LotsPossibles` : Nombre entier de lots standards que permet la capacité encore disponible pendant le jour courant. **Unité :** nombre de lots standards.
- `QuantitéCommandée` : Quantité brute finalement engagée après standard éventuel, capacité et arrondi entier si l'article est en UN. **Unité :** unité de l'article ; UN physiques entières si applicable.
- `QuantitéReçue` : Quantité issue de cet achat après rendement effectif, enregistrée lors de sa réception future ; le rendement ne change pas sa date en lui-même. **Unité :** unité de l'article ; UN physiques entières si applicable.
- `0` : Borne nulle empêchant d'utiliser une capacité restante négative. **Unité :** même unité de quantité que la capacité du pas journalier.
- `UN et masse/longueur` : Branches d'unité : pièces indivisibles, ou quantités de masse ou de longueur conservant leur précision. **Unité :** UN, G, KG ou M selon l'article.

**Opérateurs et signes :** `borner` : Ramener le produit des facteurs dans l'intervalle fermé de 0,01 à 1 ; `×` : Composer les facteurs sans unité, appliquer une fraction à une quantité ou convertir un nombre de lots en quantité via le standard ; `−` : Déduire de la capacité du pas journalier les quantités déjà engagées pendant le même jour ; `/` : Diviser par la fiabilité planifiée pour grossir le besoin, ou par le standard pour obtenir un nombre de lots ; `ceil` : Prendre le plus petit entier supérieur ou égal au nombre de lots demandés ; `floor` : Prendre le plus grand entier inférieur ou égal au nombre de lots possibles ou à la quantité de pièces commandée ou reçue ; `max et min` : Borner d'abord la capacité disponible par zéro puis retenir le plus petit besoin ou nombre de lots compatible avec cette capacité ; `Si ... Sinon ... si unité` : Choisir la branche selon le caractère contraignant et positif du standard, puis selon l'unité physique de l'article ; `=` : Définir les facteurs et quantités successifs ; les deux dernières affectations en UN imposent des pièces entières.

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

**Rappel des variables de ce calcul.**

**Périmètre :** Coût d'un nouvel approvisionnement externe d'un article auprès d'une offre fournisseur dans le scénario actif ; les engagements du carnet initial ne sont pas refacturés.

- `PrixSource` : Montant source facturé pour la base de quantité indiquée par l'offre. **Unité :** euros pour la base de prix.
- `BaseDePrix` : Quantité à laquelle se rapporte PrixSource, convertie AVANT la division dans la même unité canonique que QuantitéReçue ; par exemple une base de 1 000 G devient 1 KG si la quantité reçue est en KG. **Unité :** unité canonique compatible avec QuantitéReçue : KG, G, UN ou M selon l’article.
- `PrixNormalisé` : Montant source divisé par la base déjà convertie dans l’unité canonique de la quantité reçue. **Unité :** euros / unité canonique de quantité de l'article.
- `QuantitéReçue` : Quantité effectivement reçue pour ce nouvel achat, exprimée dans l'unité utilisée par le prix normalisé. **Unité :** unité de quantité de l'article.
- `FacteurPrixDuScénario` : Multiplicateur de prix du scénario actif ; une valeur de 1 laisse le prix normalisé inchangé. **Unité :** sans unité.
- `CoûtNouvelAchat` : Montant imputé au nouvel achat externe pour la quantité reçue, distinct des coûts opérationnels de fabrication ou stockage. **Unité :** euros.

**Opérateurs et signes :** `/` : Ramener le montant source à une unité de quantité de l'article ; `×` : Multiplier la quantité reçue par son prix unitaire compatible et par le facteur de prix sans unité ; `=` : Définir le prix normalisé puis le coût de ce nouvel achat.

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

**Rappel des variables de ce calcul.**

**Périmètre :** Scénario de demande client après 2025, pour chaque article client ; le profil de 52 semaines est répété sur 364 jours et augmenté de 5 % par cycle. Il s'agit d'une hypothèse déclarée.

- `jour` : Jour simulé de la demande ; 0 correspond au 1er janvier 2025, 364 au 31 décembre 2025 et 365 au 1er janvier 2026. **Unité :** indice de jour calendaire.
- `2` : Décalage d'alignement du profil sur les jours de semaine de l'origine mercredi ; il est ajouté puis retiré pour retrouver le jour de base. **Unité :** jours calendaires.
- `364` : Longueur du profil répété, soit 52 semaines de 7 jours. **Unité :** jours calendaires par cycle.
- `Cycle` : Quotient entier de jour + 2 par 364, qui indique le nombre de cycles de croissance appliqués. **Unité :** nombre de cycles, sans unité.
- `Position` : Reste de cette division, compris entre 0 et 363, qui repère le jour dans le profil aligné. **Unité :** position en jours dans le cycle.
- `JourBase` : Jour du profil de base associé à cette position, après retrait du décalage de deux jours. **Unité :** indice de jour du profil de base.
- `DemandeSemaineBase` : Total hebdomadaire de l'article client dans la semaine de base sélectionnée par le profil. **Unité :** UN de l'article sur la semaine de base.
- `1,05` : Facteur de croissance supposé de 5 % à chaque cycle de 364 jours. **Unité :** sans unité.
- `DemandeSemaineScénario` : Total hebdomadaire synthétique entier de l'article pour la semaine du scénario, ensuite réparti en demandes quotidiennes entières. **Unité :** UN de l'article sur la semaine du scénario.

**Opérateurs et signes :** `division_avec_reste` : Produire le quotient entier Cycle et le reste Position de la division de jour + 2 par 364 ; `+ et −` : Appliquer puis retirer le décalage d'alignement de deux jours ; `^` : Élever le facteur de croissance 1,05 au nombre de cycles Cycle ; `×` : Appliquer le facteur de croissance cumulé au total hebdomadaire de base ; `floor` : Prendre le plus grand entier inférieur ou égal au total synthétique obtenu ; `(Cycle, Position) et =` : Affecter les deux résultats de la division, puis définir le jour de base et la demande hebdomadaire du scénario ; `=` : vaut la valeur calculée, ou met à jour la quantité dans les lignes successives ; `+` : additionner les valeurs de même unité ; `−` : soustraire la valeur de même unité.

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

**Repères de cet algorithme.**

**Périmètre :** Ordre d'exécution de la simulation du réseau entier : initialisation unique, puis un pas quotidien pour chaque article/site, jusqu'au client ; chaque décision n'utilise que l'information déjà connue.

- `t` : Jour courant de simulation ; t = 0 est le 1er janvier 2025, la veille est t−1 et le lendemain t+1. **Unité :** indice de jour calendaire.

**Opérateurs et signes :** `AVANT LE PREMIER JOUR` : Effectuer l'initialisation une seule fois ; les stocks et engagements initiaux ne sont pas rechargés à chaque cycle ; `POUR CHAQUE JOUR t` : Parcourir les jours dans l'ordre chronologique et exécuter toutes les étapes du pas t ; `1 à 11, puis, avant et après` : Imposer l'ordre des opérations : information, événements, travail, service, planification, engagements, nouveau plan et exports ; cet ordre détermine ce qui est réalisable le même jour ; `aval→amont` : Parcourir le réseau de planification du client au dépôt, aux usines puis aux composants et fournisseurs, en propageant les besoins ; `re-netté` : Réallouer les ressources encore disponibles et les engagements aux besoins du plan, sans les compter deux fois.

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

**Rappel des variables de ce calcul.**

**Périmètre :** Grille périodique de lancement d'un article/site et de sa liaison dans le calendrier du modèle ; les calendriers explicites d'achat ou de fermeture s'y ajoutent.

- `PériodeLiaison` : Intervalle périodique de revue ou lancement configuré pour la liaison considérée. **Unité :** nombre entier de jours calendaires.
- `PériodeArticleSite` : Intervalle périodique configuré pour cet article au site considéré. **Unité :** nombre entier de jours calendaires.
- `PériodeAdmissible` : Période commune obtenue pour respecter simultanément les deux grilles. **Unité :** nombre entier de jours calendaires.
- `numéro_du_jour` : Indice du jour testé depuis l'origine du modèle, où 0 est le mercredi 1er janvier 2025. **Unité :** indice de jour calendaire.
- `DateAdmissible` : Date satisfaisant cette grille périodique avant prise en compte des autres calendriers et contraintes. **Unité :** date et condition d'admissibilité.
- `0` : Reste nul qui indique l'appartenance du jour à la grille commune. **Unité :** reste en jours.

**Opérateurs et signes :** `ppcm` : Prendre le plus petit commun multiple des deux périodes entières ; `%` : Calculer le reste de la division du numéro de jour par la période commune ; `=` : Dans la première ligne, définir la période ; dans la seconde, tester si le reste est nul ; `si` : Déclarer le jour admissible à cette grille lorsque la condition de reste nul est satisfaite.

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

**Rappel des variables de ce calcul.**

**Périmètre :** Bilan physique d'un seul article dans un seul site sur une même période de contrôle ; tous les mouvements sont exécutés pendant cette période et convertis dans la même unité de stock.

- `PhysiqueDébut` : Quantité physiquement détenue au site pour cet article au début de la période, tous statuts physiques concernés compris. **Unité :** unité de stock de l'article.
- `Réceptions` : Quantités réellement arrivées au site pendant la période ; une libération de blocage n'est pas comptée comme une nouvelle réception. **Unité :** unité de stock de l'article.
- `SortiesDeFabrication` : Quantités de cet article devenues des lots physiques achevés au site pendant la période, distinctes du simple travail en encours. **Unité :** unité de stock de l'article.
- `Prélèvements` : Quantités réellement retirées du stock pour fabrication ou autres usages pendant la période ; une réservation seule ne figure pas ici. **Unité :** unité de stock de l'article.
- `Départs` : Quantités expédiées physiquement hors du site pendant la période. **Unité :** unité de stock de l'article.
- `Pertes` : Quantités physiquement perdues ou rebutées au site pendant la période et comptabilisées comme sorties. **Unité :** unité de stock de l'article.
- `AjustementsSignés` : Corrections physiques explicites et tracées pendant la période, positives pour un ajout ou négatives pour un retrait. **Unité :** unité de stock de l'article, avec signe.
- `PhysiqueFin` : Quantité physiquement détenue du même article au même site à la fin de la période, après tous les mouvements comptabilisés. **Unité :** unité de stock de l'article.

**Opérateurs et signes :** `+` : Ajouter les entrées physiques et les ajustements avec leur signe ; `−` : Déduire les prélèvements exécutés, les départs et les pertes physiques de la période ; `=` : Exprimer la conservation du stock physique au même article/site entre début et fin de période.

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

## 25. Du besoin au lot physique

Le MRP calcule une quantité à préparer. La **lotification** transforme cette
quantité en campagnes et en lots fabricables. Imagine une recette préparée par
fournées : avoir travaillé sur une partie de la fournée ne donne pas encore
une fournée terminée à expédier.

Les règles MRP des chapitres précédents donnent le besoin net. Les règles
ci-dessous dimensionnent ensuite la fabrication ; elles ne garantissent ni
les matières, ni la capacité, ni le transport nécessaires.

### 25.1 Dimensionner la campagne

Une **campagne** est le travail engagé pour un article sur un site. Elle peut
contenir plusieurs lots physiques de taille fixe. Avec un besoin strictement
positif et une politique de lot fixe active :

```text
QuantitéCampagne = ceil(BesoinNet / TailleLotFixe) × TailleLotFixe
```

**Rappel des variables de ce calcul.**

**Périmètre :** Une décision de lancement pour un même article et un même site ; TailleLotFixe est strictement positive.

- `QuantitéCampagne` : Quantité totale proposée pour cette campagne. **Unité :** unité de sortie de l'article : UN, G ou KG selon son paramétrage.
- `BesoinNet` : Quantité positive restant à couvrir après le calcul MRP. **Unité :** même unité de sortie que QuantitéCampagne.
- `TailleLotFixe` : Quantité d'un lot physique complet de cet article. **Unité :** même unité de sortie que QuantitéCampagne.

**Opérateurs et signes :** `/` : calculer le nombre de lots nécessaires ; `ceil` : arrondir ce nombre à l'entier supérieur ; `×` : revenir à une quantité de produit ; `=` : donner la quantité calculée.

Avec un besoin de 120 UN et un lot fixe de 100 UN, la campagne contient deux
lots, soit 200 UN. Les 80 UN supplémentaires sont un surplus à suivre dans le
stock et dans les calculs MRP suivants ; ce ne sont pas 80 UN de demande client.
Avec un besoin nul, cette règle ne crée pas de campagne positive.

Pour une politique minimum/multiple/maximum, sans lot fixe, le moteur procède
dans cet ordre. Le calcul suivant suppose un multiple positif et un maximum
positif, avec au moins un lot admissible entre le minimum et le maximum :

```text
QuantitéAvantArrondi = max(BesoinNet, MinimumLot)
QuantitéArrondie = ceil(QuantitéAvantArrondi / MultipleLot) × MultipleLot
MaximumAdmissible = floor(MaximumLot / MultipleLot) × MultipleLot
QuantitéCampagne = min(QuantitéArrondie, MaximumAdmissible)
```

**Rappel des variables de ce calcul.**

**Périmètre :** Une proposition positive pour un même article/site, politique sans lot fixe, minimum/multiple/maximum compatibles ; toutes les quantités utilisent la même unité de sortie.

- `BesoinNet` : Quantité restant à couvrir par la proposition. **Unité :** unité de sortie de l'article.
- `MinimumLot` : Plus petite quantité autorisée par la politique de fabrication. **Unité :** même unité de sortie.
- `MultipleLot` : Pas de quantité auquel le lot doit se conformer. **Unité :** même unité de sortie.
- `MaximumLot` : Plafond déclaré pour un lot de cette politique. **Unité :** même unité de sortie.
- `QuantitéAvantArrondi` : Besoin relevé au minimum de fabrication. **Unité :** même unité de sortie.
- `QuantitéArrondie` : Quantité relevée au multiple supérieur. **Unité :** même unité de sortie.
- `MaximumAdmissible` : Plus grand multiple entier ne dépassant pas le maximum déclaré. **Unité :** même unité de sortie.
- `QuantitéCampagne` : Quantité de la campagne proposée par cet appel. **Unité :** même unité de sortie.

**Opérateurs et signes :** `max` : retenir la plus grande valeur ; `min` : retenir la plus petite ; `/` : exprimer la quantité en nombre de multiples ; `ceil` : arrondir ce nombre vers le haut ; `floor` : arrondir ce nombre vers le bas ; `×` : retrouver la quantité correspondante ; `=` : donner chaque résultat intermédiaire.

Si le besoin dépasse ce plafond, cet appel laisse un besoin résiduel à couvrir :
il ne fabrique pas tout en dépassant le maximum. Sans multiple ou sans maximum,
les branches correspondantes du programme sont omises. Une politique incohérente
est rejetée. Ces règles sont celles de `launch_campaign_qty` dans le
[moteur](../simulation/engine/run_first_simulation.py).

### 25.2 Fabriquer sans rendre l'encours disponible trop tôt

La campagne est découpée en lots physiques. Avec une taille fixe positive,
la cible suivante et l'avancement de ce lot sont calculés ainsi :

```text
CibleLot = min(ResteCampagne, TailleLotFixe)
TravailAccepté = min(TravailProposé, max(0, CibleLot − TravailDéjàExécuté))
TravailAprès = TravailDéjàExécuté + TravailAccepté
```

**Rappel des variables de ce calcul.**

**Périmètre :** Le prochain lot d'une même campagne article/site ; son travail cumulé est distinct du stock de produits achevés. TravailProposé a déjà été limité par les contraintes physiques du jour.

- `ResteCampagne` : Quantité de la campagne restant à réaliser lors de la création du prochain lot. **Unité :** unité de sortie de l'article.
- `TailleLotFixe` : Quantité cible d'un lot complet lorsque cette politique est active. **Unité :** même unité de sortie.
- `CibleLot` : Quantité à achever avant de créer le lot terminé. **Unité :** même unité de sortie.
- `TravailProposé` : Quantité de travail physiquement réalisable proposée pour ce lot dans cette passe. **Unité :** quantité équivalente de sortie, pour la passe considérée.
- `TravailDéjàExécuté` : Travail cumulé sur ce lot avant la passe, y compris les jours antérieurs. **Unité :** même quantité équivalente de sortie.
- `TravailAccepté` : Travail ajouté dans la passe sans dépasser la cible du lot. **Unité :** même quantité équivalente de sortie.
- `TravailAprès` : Travail cumulé après cette passe. **Unité :** même quantité équivalente de sortie.

**Opérateurs et signes :** `min` : limiter au reste à réaliser ; `max(0, …)` : empêcher un reste négatif ; `−` : retirer le travail déjà effectué de la cible ; `+` : ajouter uniquement le travail accepté ; `=` : donner le résultat de chaque étape.

Sans taille fixe, la cible du prochain lot est le reste de la campagne déjà
dimensionnée. Le travail des jours successifs reste dans l'**encours**.
À l'achèvement, le moteur crée le lot enfant une seule fois et lui rattache
toutes les matières consommées pendant sa fabrication.

La capacité n'est pas offerte de nouveau à chaque passe de calcul :

```text
CapacitéRestante = max(0, CapacitéJour − TravailDéjàFaitCeJour − ConditionnementInitialCeJour)
```

**Rappel des variables de ce calcul.**

**Périmètre :** Le même budget quotidien de production, partagé entre les passes qui le consomment ; les quantités de travail doivent être exprimées sur la même base que cette capacité.

- `CapacitéJour` : Budget physique de travail retenu pour la journée. **Unité :** quantité équivalente de sortie sur cette journée.
- `TravailDéjàFaitCeJour` : Travail de production ayant déjà consommé ce budget aujourd'hui. **Unité :** même quantité équivalente de sortie.
- `ConditionnementInitialCeJour` : Travail des conditionnements d'ouverture déjà imputé à cette journée. **Unité :** même quantité équivalente de sortie.
- `CapacitéRestante` : Budget encore utilisable pour la passe suivante. **Unité :** même quantité équivalente de sortie.

**Opérateurs et signes :** `−` : déduire les travaux déjà exécutés ; `max(0, …)` : maintenir un reste non négatif ; `=` : donner la capacité encore disponible. Le moteur rejette aussi un dépassement du budget, il ne le masque pas simplement par zéro.

Le travail consomme la recette correspondant à la quantité effectivement
exécutée. Les composants en UN sont prélevés avec l'arrondi entier requis.
Une réservation seule n'est pas une consommation. La marge `tau_process`
de planification ne devient pas ici une seconde durée de maturation physique.
Voir `ProductionBatchWip` dans les [campagnes](../simulation/lot_trace/campaigns.py)
et `production_remaining_day_capacity` dans le [moteur](../simulation/engine/run_first_simulation.py).

**Exemple fictif, calcul manuel :** un lot de 100 UN, une capacité de 40 UN
par jour et un blocage complet le deuxième jour. Les matières nécessaires sont
disponibles sur les journées effectivement travaillées.

| Jour fictif | Travail accepté | Encours non achevé en fin de jour | Lot terminé créé ce jour |
|---|---:|---:|---:|
| Premier jour | 40 UN | 40 UN | 0 UN |
| Deuxième jour, bloqué | 0 UN | 40 UN | 0 UN |
| Troisième jour | 40 UN | 80 UN | 0 UN |
| Quatrième jour | 20 UN | 0 UN | 100 UN |

Le contrôle qualité peut encore retenir ces 100 UN après leur achèvement.
Le stock utilisable, son départ, sa réception et sa disponibilité à Muret
gardent chacun leur date. Un stock aval suffisant peut absorber ce décalage ;
un client en manque peut au contraire le subir.

## 26. Suivre la matière jusqu'au client

La **généalogie** est le carnet des liens : quelle matière a alimenté quelle
fabrication, puis quelles expéditions et quels clients. Elle relie les sorties
du calcul MRP aux mouvements physiques sans remplacer les preuves industrielles.

| Identité | Ce qu'elle désigne dans le simulateur |
|---|---|
| Campagne | Engagement de fabrication pouvant contenir plusieurs lots fixes |
| Lot | Quantité partageant une origine de fabrication simulée |
| Occurrence de stock | Présence localisée d'un lot à une étape ; transport et réception gardent leurs propres traces |
| `shipment_id`, identifiant SHIP | Transaction physique d'expédition simulée ; ce n'est pas l'identité d'un camion réel |

Les allocations de chaque prélèvement restent rattachées à leurs lots parents.
Un transport conserve la quantité dans la même unité. Une fabrication conserve
les contributions de chaque composant avec son unité : on ne divise jamais des
kilogrammes par un total mélangeant kilogrammes, mètres et unités.
Si l'origine détaillée manque, le moteur marque `untraced_origin` : **origine
non retracée**, et non numéro de lot industriel inventé.

### 26.1 Passer d'un incident aux lots exposés

Les identifiants d'incident et le jour de leur décision suivent l'expédition,
les lots reçus, leurs transformations et les lots servis au client. Le contexte
initial est conservé même lorsque le départ physique est différé.
Pour une transformation, le registre calcule séparément chaque composant :

```text
PartComposantBasse = somme(QuantitéParent × PartParentBasse) / somme(QuantitéParent)
PartComposantHaute = somme(QuantitéParent × PartParentHaute) / somme(QuantitéParent)
```

**Rappel des variables de ce calcul.**

**Périmètre :** Les allocations du même composant, dans une même unité, réellement consommées pour un lot enfant ; le total consommé est positif. Les sommes incluent aussi ses parents non exposés, dont la part exposée est nulle.

- `QuantitéParent` : Quantité prélevée sur chacun des lots parents de ce composant. **Unité :** unité de ce composant, par exemple KG ou UN.
- `PartParentBasse` : Borne basse de la fraction exposée du lot parent concerné. **Unité :** fraction sans unité, entre 0 et 1.
- `PartParentHaute` : Borne haute de cette même fraction. **Unité :** fraction sans unité, entre 0 et 1.
- `PartComposantBasse` : Borne basse de la fraction exposée de tout ce composant consommé. **Unité :** fraction sans unité, entre 0 et 1.
- `PartComposantHaute` : Borne haute de cette même fraction. **Unité :** fraction sans unité, entre 0 et 1.

**Opérateurs et signes :** `somme` : additionner les allocations de ce seul composant ; `×` : pondérer chaque quantité par sa fraction exposée ; `/` : rapporter la quantité exposée au total consommé ; `=` : donner chacune des bornes.

Le registre encadre ensuite la quantité du lot enfant issue de composants
exposés. Il ne prétend pas connaître leur mélange microscopique :

```text
QuantitéEnfantBasse = QuantitéLotEnfant × max(PartComposantBasse)
QuantitéEnfantHaute = QuantitéLotEnfant × min(1, somme(PartComposantHaute))
```

**Rappel des variables de ce calcul.**

**Périmètre :** Un lot enfant et l'ensemble de ses composants, après calcul séparé de leurs fractions exposées ; les bornes parentales sont cohérentes entre 0 et 1.

- `QuantitéLotEnfant` : Quantité totale créée dans le lot enfant. **Unité :** unité de sortie du lot enfant, par exemple UN de produit fini.
- `PartComposantBasse` : Borne basse de la fraction exposée de chaque composant de ce lot. **Unité :** fraction sans unité, entre 0 et 1.
- `PartComposantHaute` : Borne haute correspondante de chaque composant. **Unité :** fraction sans unité, entre 0 et 1.
- `QuantitéEnfantBasse` : Borne basse de quantité du lot enfant attribuée à cette exposition. **Unité :** même unité de sortie que QuantitéLotEnfant.
- `QuantitéEnfantHaute` : Borne haute de cette quantité attribuée. **Unité :** même unité de sortie que QuantitéLotEnfant.

**Opérateurs et signes :** `max` : retenir la plus grande fraction basse parmi les composants ; `somme` : additionner leurs fractions hautes, sans additionner leurs quantités physiques incompatibles ; `min(1, …)` : plafonner à la totalité du lot ; `×` : convertir la fraction en quantité enfant ; `=` : donner chacune des bornes.

### 26.2 Exposition, double comptage et perte de service

Deux incidents concernant la même expédition de 100 UN ne font pas 200 UN
physiquement exposées. Le registre garde une seule expédition à sommer et
plusieurs liens d'incident. Les quantités sont regroupées par expédition
exposée unique et par unité, jamais en additionnant toutes les lignes d'incident.

De même, 20 UN servies provenant d'un lot exposé ne sont pas 20 UN perdues.
Pour attribuer un retard, une perte de service ou un surcoût à l'incident,
il faut comparer au calcul témoin apparié sans cet incident.
Les règles exactes et les CSV de liaison sont dans le
[registre risques → lots → clients](../simulation/lot_trace/RISK_IMPACT_REGISTRY.md)
et sa fonction `_derive_child_impact` dans le
[code du registre](../simulation/lot_trace/risk_impact_registry.py).

## 27. Un risque peut dépendre de l'état de la chaîne

Un **risque imposé** est un événement déclaré dans un scénario : par exemple,
une capacité réduite pendant une période donnée. Un **risque dépendant de
l'état** est créé par une règle lorsque le fonctionnement simulé dépasse un
seuil : stock trop bas, utilisation trop élevée, retards constatés ou pertes.

**Dans la référence nominale actuelle, cette deuxième famille est désactivée.**
Elle s'active avec `--supplier-state-dependent-risks`. La commande d'étude
`cascade` orchestre le même moteur physique ; elle ne rend pas automatiquement
ces risques actifs dans la carte nominale conservée.

Les seuils et amplitudes ci-dessous sont des **conventions de scénario**.
Ce ne sont ni des fréquences de panne industrielles mesurées, ni des probabilités
que nous aurions calibrées sur les courbes de 2025.

### 27.1 Mesurer une tension, puis conserver une mémoire

Pour la tension de stock, le moteur calcule une couverture :

```text
CouvertureStock = StockFournisseur / BesoinJournalierRéférence
```

**Rappel des variables de ce calcul.**

**Périmètre :** Le même article chez le même fournisseur, au jour observé ; le besoin journalier est strictement positif.

- `CouvertureStock` : Nombre de jours de besoin couverts par le stock retenu dans cette mesure. **Unité :** jours.
- `StockFournisseur` : Quantité du buffer fournisseur utilisée par la règle. **Unité :** unité de stock de l'article, par exemple UN ou KG.
- `BesoinJournalierRéférence` : Maximum du besoin aval alloué et du signal aval alloué à ce fournisseur. **Unité :** même unité d'article par jour.

**Opérateurs et signes :** `/` : diviser une quantité par un débit quotidien ; `=` : donner la couverture correspondante.

Sans besoin positif, cette division n'est pas réalisée et les compteurs de
tension de stock sont réinitialisés. La grandeur utilisée par une règle doit
rester celle du moteur ; elle ne remplace pas un statut qualité industriel.

Une condition persistante peut accumuler plusieurs observations :

```text
CompteurNouveau = CompteurPrécédent + 1 si ConditionVraie
CompteurNouveau = 0 sinon
```

**Rappel des variables de ce calcul.**

**Périmètre :** Mise à jour d'une règle donnée, pour la même clé de source/article/liaison et lors d'une observation de cette métrique.

- `CompteurNouveau` : Nombre d'observations déclenchantes successives après la mise à jour. **Unité :** nombre d'observations.
- `CompteurPrécédent` : Valeur conservée avant cette observation. **Unité :** nombre d'observations.
- `ConditionVraie` : Résultat du test de seuil de cette règle. **Unité :** booléen, vrai ou faux.
- `1` : Une observation déclenchante supplémentaire. **Unité :** observation.
- `0` : Valeur de réinitialisation si la condition est fausse. **Unité :** observation.

**Opérateurs et signes :** `+` : ajouter une observation ; `si` et `sinon` : choisir une seule branche ; `=` : mettre à jour le compteur, sans résoudre une équation entre les deux lignes.

Pour les délais, les observations arrivent aux **réceptions physiques** : trois
observations ne signifient donc pas nécessairement trois jours calendaires.
Le moteur ne connaît pas le retard réellement réalisé avant cette réception.
La mémoire comprend des compteurs, des moyennes glissantes et une période
d'interdiction de redéclenchement ; ce n'est pas une loi continue de fatigue.

### 27.2 Déclencher maintenant, agir ensuite

```text
DébutEffet = JourDéclenchement + 1
FinEffet = DébutEffet + DuréeEffet − 1
DernierJourInterdit = FinEffet + DélaiAvantRedéclenchement
```

**Rappel des variables de ce calcul.**

**Périmètre :** Un nouvel incident d'état, après vérification de l'activation, de la famille autorisée, du seuil, de la période d'observation initiale et du délai de redéclenchement.

- `JourDéclenchement` : Jour où la règle constate suffisamment d'observations déclenchantes. **Unité :** indice de jour du modèle.
- `DébutEffet` : Premier jour où l'incident peut modifier le calcul physique. **Unité :** indice de jour du modèle.
- `FinEffet` : Dernier jour inclus dans cet effet. **Unité :** indice de jour du modèle.
- `DuréeEffet` : Durée positive retenue pour l'événement. **Unité :** jours calendaires.
- `DélaiAvantRedéclenchement` : Attente supplémentaire interdisant de recréer cette règle immédiatement. **Unité :** jours calendaires.
- `DernierJourInterdit` : Dernier jour de déclenchement encore refusé pour cette règle. **Unité :** indice de jour du modèle.
- `1` : Un jour d'avance pour commencer l'effet, ou correction du comptage des deux bornes incluses. **Unité :** jour calendaire.

**Opérateurs et signes :** `+` : avancer une date ; `−` : retirer le jour déjà compté par la borne de début ; `=` : définir la date de chaque étape.

Un incident déclenché à J4, de durée sept jours, agit de J5 à J11 inclus.
Le premier nouveau déclenchement admissible est le jour suivant
`DernierJourInterdit`, sous réserve que les autres conditions restent réunies.
La période d'observation initiale vaut 30 jours par défaut ; notre exemple
pédagogique la ramène explicitement à zéro pour exercer le mécanisme rapidement.

### 27.3 Les seuils réellement programmés

| Mesure de la règle | Condition déclenchante | Effet futur retenu |
|---|---|---|
| Couverture de stock | Moins de 5 jours pendant 5 observations | Disponibilité multipliée par 0,95 pendant 7 jours |
| Couverture de stock | Moins de 3 jours pendant 2 observations | Disponibilité multipliée par 0,85 pendant 14 jours |
| Couverture de stock | Au plus 0,25 jour lors d'une observation | Disponibilité multipliée par 0,70 pendant 21 jours |
| Utilisation de capacité | Plus de 75 % pendant 5 observations | Capacité multipliée par 0,97 pendant 7 jours |
| Utilisation de capacité | Au moins 99,5 % lors d'une observation | Capacité multipliée par 0,92 pendant 7 jours |
| Utilisation de capacité | Plus de 85 % pendant 3 observations | Capacité multipliée par 0,90 pendant 14 jours |
| Utilisation de capacité | Plus de 90 % pendant 3 observations | Capacité multipliée par 0,85 pendant 14 jours |
| Délai observé rapporté au délai de référence | Plus de 1,10 pendant 3 observations | Facteur délai de 1,10 pendant 7 jours |
| Même rapport de délais | Plus de 1,25 pendant 2 observations | Trois jours supplémentaires pendant 14 jours |
| Même rapport de délais | Plus de 1,35 pendant 2 observations | Cinq jours supplémentaires pendant 14 jours |
| Rejet amont moyen sur sept jours et couverture | Plus de 10 %, deux observations, couverture inférieure à 7 jours | Disponibilité amont multipliée par 0,97 pendant 7 jours |
| Rejet amont moyen sur quatorze jours et couverture | Plus de 50 %, couverture inférieure à 3 jours | Capacité amont multipliée par 0,90 pendant 14 jours |
| Part de perte dans la quantité appelée | Plus de 3 % pendant 2 observations | Fiabilité multipliée par 0,95 pendant 14 jours |
| Même part de perte | Plus de 8 % lors d'une observation | Rendement qualité multiplié par 0,90 pendant 14 jours |
| Coût unitaire de recours amont rapporté au prix fournisseur de référence | Besoin d'achat amont positif, rapport supérieur à 2,50 pendant 3 observations | Coût de recours amont multiplié par 1,10 pendant 14 jours |

Les parts et rapports sont sans unité ; la couverture s'exprime en jours.
L'utilisation rapporte le débit mesuré au budget nominal de capacité sur le
même pas. Les fractions de rejet et de perte comparent des quantités dans
la même unité. Les moyennes utilisent les observations disponibles selon la
métrique ; une absence de réception ne révèle pas un délai futur.

Pour le recours amont, le coût surveillé additionne achat unitaire et transport
unitaire, puis rapporte ce total au prix fournisseur de référence. Les montants
doivent concerner la même unité du même article. Cette règle de la famille
`cost` ajoute un surcoût économique, sans réduction physique directe ; son
interdiction de redéclenchement dure quatorze jours après la fin de l'effet.

Des règles de manque matière peuvent aussi agir sur une liaison candidate :
manque d'au moins 5 % pendant deux observations, disponibilité multipliée par
0,92 pendant dix jours ; manque d'au moins 10 % avec réception trop tardive,
deux jours de délai ajoutés pendant quatorze jours ; manque d'au moins 35 %
pendant deux observations, capacité multipliée par 0,88 pendant quatorze jours.
Le dénominateur est le maximum du programme d'exécution, de la quantité désirée
et d'une unité de calcul. La réception est ici trop tardive lorsqu'elle dépasse
le jour courant augmenté du maximum entre sept jours et le délai de la liaison.
Ce sont des règles locales de scénario, à activer et interpréter sur leur périmètre.

Sources : `make_state_dependent_supplier_event`,
`register_state_dependent_supplier_event` et les règles de fin de pas du
[moteur](../simulation/engine/run_first_simulation.py) ;
`ReceiptLeadObservations` dans les [conventions temporelles](../simulation/engine/model_semantics.py).

## 28. Composer les risques sans les compter deux fois

Les effets imposés et les effets dépendant de l'état sont composés séparément,
puis réunis. Un multiplicateur réduit une capacité ou une disponibilité ; un
délai supplémentaire ajoute des jours. Les identifiants des événements actifs
restent conservés dans les transactions concernées.

### 28.1 Les effets d'état sont bornés, sans effacer une crise imposée

Pour des facteurs de réduction de capacité compris entre zéro et un :

```text
FacteurÉtatCapacité = max(0.70, produit(FacteursCapacitéÉtatActifs))
FacteurFinalCapacité = FacteurScénarioCapacité × FacteurÉtatCapacité
```

**Rappel des variables de ce calcul.**

**Périmètre :** Même liaison, article et jour d'application ; seuls les événements actifs et applicables entrent dans les produits. La formule décrit ici des réductions, sans facteur supérieur à un.

- `FacteursCapacitéÉtatActifs` : Liste des multiplicateurs de capacité des incidents d'état applicables. **Unité :** facteurs sans unité, de zéro à un.
- `FacteurÉtatCapacité` : Produit d'état après sa borne inférieure propre. **Unité :** facteur sans unité.
- `0.70` : Borne inférieure programmée pour cette capacité dépendante de l'état. **Unité :** facteur sans unité.
- `FacteurScénarioCapacité` : Produit des facteurs de capacité imposés par le scénario. **Unité :** facteur sans unité.
- `FacteurFinalCapacité` : Facteur composé appliqué à la capacité concernée. **Unité :** facteur sans unité.

**Opérateurs et signes :** `produit` : multiplier les facteurs d'une même famille ; `max` : garder le plus grand argument ; `×` : composer scénario et état après la borne d'état ; `=` : définir le facteur de chaque étape. Le produit d'une liste vide vaut un.

Exemple fictif vérifié : les quatre facteurs d'état 0,97, 0,92, 0,90 et 0,85
donnent un produit de 0,682686, relevé à 0,70. Une crise imposée de facteur
0,50 donne ensuite un facteur final de 0,35. Le plancher d'état ne transforme
donc pas la crise imposée en une réduction limitée à 30 %.

| Effet d'état | Borne native avant composition avec le scénario |
|---|---|
| Capacité et disponibilité, internes ou amont | Facteur au moins égal à 0,70 |
| Fiabilité et rendement qualité | Facteur au moins égal à 0,75 |
| Facteur de délai, interne ou amont | Au plus 1,50 |
| Jours de délai supplémentaires, internes ou amont | Au plus dix jours |
| Facteurs de coût concernés | Au plus 1,50 |

Les jours supplémentaires d'événements applicables s'ajoutent ; les facteurs
de délai se multiplient. Les bornes générales du moteur restent également
appliquées. Une journée d'incident n'est pas ajoutée une seconde fois à la
réception si son effet a déjà été inclus dans le calendrier de l'expédition.

### 28.2 Plusieurs destructions portent sur le reliquat

```text
PartDétruiteTotale = 1 − produit(1 − PartDétruiteParIncident)
```

**Rappel des variables de ce calcul.**

**Périmètre :** Composition des proportions de destruction de stock applicables au même périmètre ; chaque proportion est bornée entre zéro et un par le moteur.

- `PartDétruiteParIncident` : Fraction de destruction déclarée par chacun des incidents applicables. **Unité :** fraction sans unité, de zéro à un.
- `PartDétruiteTotale` : Fraction détruite après composition des reliquats. **Unité :** fraction sans unité, de zéro à un.
- `1` : La totalité du stock ou du reliquat avant l'effet concerné. **Unité :** fraction sans unité.

**Opérateurs et signes :** `−` : obtenir le reliquat puis la perte totale ; `produit` : conserver successivement les parts non détruites ; `=` : donner la fraction totale composée.

Ce calcul combine les effets. La quantité effectivement détruite doit ensuite
être rapprochée des événements physiques ; le registre d'exposition ne crée pas
de perte de matière à lui seul.

### 28.3 Ce que le MRP sait de la perte

```text
FiabilitéDuPlan = FiabilitéEffective si CompensationAnticipée
FiabilitéDuPlan = FiabilitéNominale sinon
```

**Rappel des variables de ce calcul.**

**Périmètre :** Traitement de la perte temporaire fournisseur dans le calcul des quantités à acheter ; les deux lignes sont des choix alternatifs.

- `FiabilitéDuPlan` : Fiabilité retenue pour dimensionner le besoin brut du plan. **Unité :** fraction sans unité.
- `FiabilitéEffective` : Fiabilité incluant la perte temporaire considérée. **Unité :** fraction sans unité.
- `FiabilitéNominale` : Fiabilité hors de cette perte temporaire. **Unité :** fraction sans unité.
- `CompensationAnticipée` : Option autorisant ce grossissement du besoin selon la perte temporaire. **Unité :** booléen, vrai ou faux.

**Opérateurs et signes :** `si` et `sinon` : choisir la fiabilité autorisée ; `=` : affecter la valeur au calcul du plan.

L'option `--no-supplier-risk-loss-gross-up` désactive cette compensation
immédiate. Elle ne prouve pas, à elle seule, que toutes les informations d'un
scénario sont inconnues à chaque décision : il faut conserver les dates de
connaissance et vérifier les traces. La source exacte est
`supplier_planning_reliability` ; les compositions sont dans
`supplier_risk_multipliers_for_lane` du [moteur](../simulation/engine/run_first_simulation.py).

## 29. Relier toute la chaîne et distinguer exposition et perte

```text
Besoin MRP → campagne → travail et matières consommées → lot achevé
  → stock utilisable → expédition → réception → disponibilité → client
État observé → règle d'état → incident actif à partir du lendemain
  → capacité, disponibilité, rendement ou délai modifié → nouveaux états
Incident appliqué → identifiant d'expédition → généalogie → lots clients exposés
```

**Lecture de ce schéma.** La première ligne décrit le flux physique gouverné par les décisions ; la seconde boucle montre comment l'état peut modifier les conditions suivantes ; la dernière décrit la traçabilité. Une flèche de traçabilité ne mesure pas, à elle seule, une perte de service causée par l'incident.

| Étape à raccorder | Question simple | Trace native à consulter |
|---|---|---|
| MRP et engagement | Que fallait-il couvrir et qu'a-t-on engagé ? | `mrp_dated_plan_daily.csv`, `mrp_orders_daily.csv` |
| Campagne et encours | Quel travail a réellement eu lieu et quand le lot est-il achevé ? | `production_plan_events.csv`, `production_lot_events.csv` |
| État et risque | Quelle mesure a déclenché quel effet et à quelle date ? | `supplier_state_dependent_risk_events.csv`, `supplier_risk_events_applied_daily.csv` |
| Mouvement exposé | Quelle transaction a réellement porté cet incident ? | `production_supplier_shipments_daily.csv`, clé `shipment_id` |
| Matière et transformation | Quels lots parents ont alimenté quels lots enfants ? | `production_lot_genealogy.csv` et registre d'impact |
| Client | Qu'a-t-il reçu, consommé et encore attendu ? | `production_demand_service_daily.csv`, `risk_impact_client_service.csv` |

Deux notions restent distinctes :

- **Exposition :** le lot ou la transaction a rencontré un effet de risque dans le modèle.
- **Impact incrémental :** le résultat diffère du témoin comparable sans ce mécanisme.

Le registre suit la première notion. La seconde demande une comparaison
appariée, avec mêmes demande, état initial, règles conservées et conventions
de tirage. Un même lot exposé à deux incidents n'est pas deux quantités
physiques différentes. Un lot exposé servi au client n'est pas une vente perdue.

Il reste une limite de liaison : chaque nouvel incident d'état reçoit sa propre
racine d'identité. Son enregistrement ne reçoit pas automatiquement l'identifiant
de l'incident initial qui aurait éventuellement créé la tension. Nous savons
suivre les états et les effets physiques ; nous ne disposons pas d'une preuve
automatique d'ascendance pour tous les incidents successifs. Une proximité
temporelle ne doit pas être transformée en parenté causale.

Les scénarios importés `scenario_preview` de rappel, quarantaine ou retard
servent à explorer la généalogie. Ils ne recalculent pas les stocks, délais,
coûts ou livraisons. Ils restent distincts des événements réellement exécutés
dans le moteur. Voir le [contrat matières et incidents](MATIERES_LOTS_ET_INCIDENTS.md).

Les deux interfaces existantes, [suivi de lots](EXPLORATEUR_DES_LOTS.md) et
[parcours simplifié](PARCOURS_DES_LOTS.md), conservent leurs rôles. Les identités
communes permettent de relier leurs lectures ; une consolidation camion affichée
ne déplace pas automatiquement les événements physiques de la simulation.

## 30. Un exemple court où tous les liens restent vérifiables

**Exemple fictif exécuté, distinct des données industrielles de 2025.**
Le cas comporte un fournisseur et un client, un article en UN, cent unités
initiales chez le fournisseur, une demande de dix unités par jour et un jour
de transport. Le moteur conserve ses décisions et son réapprovisionnement
fournisseur. Il n'y a pas de transformation en produit fini dans ce petit graphe.
Les comptes ci-dessous ciblent uniquement l'article `item:A` sur la liaison
`SDC-TEST` vers `C-TEST`. D'autres lots initiaux issus des réglages communs
peuvent apparaître dans le registre global ; ils sont exclus de ces comptes.

Deux calculs de quatorze jours ont les mêmes données et la même graine 9102.
Le témoin désactive les risques d'état ; la variante les active avec une
période d'observation initiale nulle. Les délais aléatoires et la compensation
anticipée des pertes temporaires sont désactivés dans les deux cas.

**Portée des contrôles : les deux calculs se terminent, mais leur qualification
automatique globale est refusée.** Pour chacun, trois tableaux attendus restent
sans lignes dans ce graphe sans usine ni centre de distribution : stocks
d'intrants, stocks de distribution et sorties de fabrication. L'audit de
parcours des lots n'a pas été produit non plus. Les tests et rapprochements
ciblés vérifient les mécanismes décrits ; ils ne remplacent pas ces quatre
contrôles non passants et ne qualifient pas l'ensemble du calcul.

| Mesure sur les quatorze jours | Témoin | Risques d'état activés |
|---|---:|---:|
| Événements d'état créés | 0 | 4 |
| Expéditions physiques | 14 | 14 |
| Quantité expédiée, y compris le transit final | 210 UN | 210 UN |
| Transactions expédiées exposées, comptées une seule fois | 0 | 11, soit 110 UN |
| Quantité servie provenant de lots exposés, sans double compte par incident | 0 UN | 40 UN |
| Réapprovisionnement fournisseur | 160 UN | 149 UN |
| Stock fournisseur final | 50 UN | 39 UN |
| Demande totale | 140 UN | 140 UN |
| Quantité servie totale | 140 UN | 140 UN |
| Demande encore en retard à la fin | 0 UN | 0 UN |

L'effet est bien physique : le réapprovisionnement et le stock fournisseur
diminuent de onze unités. Les expéditions restent identiques et le stock client
protège le service sur cette fenêtre. Cela ne signifie pas que toutes les
demandes ont été servies à leur date : dix unités attendent à J0, puis sont
rattrapées à J1 dans les deux cas. Une expédition reste en transit à la fin ;
certains événements restent actifs au-delà de ces quatorze jours.

### 30.1 Une chaîne précise, lisible sans supposer une perte

| Étape du même exemple | Événement ou identité réellement retrouvé |
|---|---|
| J2 | Une tension de couverture de stock déclenche un effet futur de disponibilité ; un effet amont est également créé |
| J3 | `SHIP-00000004` expédie dix UN avec les deux identifiants de risque ; le jour de décision reste J3 |
| J4 | La généalogie relie le parent `LOT-00000005` au lot reçu `LOT-00000008`, quantité dix UN |
| Identité de lot | Le lot métier `BATCH-00000005` est conservé ; ses occurrences de stock changent avec les sites |
| J10 | Le client consomme les dix UN de `LOT-00000008` ; événement `LEVT-00000046` |
| Comparaison au témoin | Le service quotidien est identique : ces dix unités exposées ne sont pas dix unités perdues |

Les [deux exécutions et leurs commandes](../artifacts/testing/mrp_lots_risques_20261109/execution_manifest.json),
les [résultats témoins](../artifacts/testing/mrp_lots_risques_20261109/control_overview.json)
et la [variante avec risques](../artifacts/testing/mrp_lots_risques_20261109/state_overview.json)
permettent de suivre ces identités. Les CSV détaillés sont dans leurs dossiers
`control/data` et `state/data` ; les registres de liaison dans `risk_registry`.

Le fonctionnement de la fabrication et du mélange est vérifié séparément par
les cas mémoire des chapitres 25 et 26 et par leurs tests ciblés. Le petit
graphe fournisseur–client ne démontre pas, à lui seul, une cascade complète
Gaillac → usine → Muret → client, ni une cause industrielle de 2025.
Le [manifeste de cette extension](../artifacts/testing/mrp_lots_risques_20261109/final_manifest.json)
précise les contrôles exécutés et les limites. Aucune référence nominale
n'est remplacée et aucune probabilité industrielle n'est déduite de cet exemple.
