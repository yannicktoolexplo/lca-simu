# Explorer un lot, ses transports et son état à une date

Depuis [l’accueil](../index.html), ouvrez la carte puis **Parcours simplifié des lots**. Cette fenêtre reste indépendante de **Suivi de lots**. Les résultats du moteur et les stocks de sécurité sont conservés.

Vous pouvez également [enregistrer une enquête, exporter une fiche et déplier les grands parcours par voisinage](ENQUETES_LOTS.md). L’enquête retrouve le contexte sur les mêmes données ; la fiche HTML est lisible hors ligne.

## Retrouver le bon objet

La recherche accepte les identifiants LOT, LOCC, STOCKLOT, PBATCH/BATCH, les événements, les ordres planifiés, les expéditions SHIP, l’article et le site. Un SHIP reçu renvoie ses réceptions ; s’il n’existe pas encore de réception enregistrée, il renvoie les occurrences réservées ou expédiées. Les lots fabricant et les contenants sont également recherchables lorsqu’ils sont renseignés dans le registre matières.

La recherche d’un lot métier inclut les occurrences mélangées qui le contiennent. Ainsi, `PBATCH-411EC755D7110AE0` retrouve quatre occurrences : usine, dépôt et deux réceptions client. Un résultat mélangé représente toute la réception ; il n’est pas une nouvelle fabrication de ce PF.

Les filtres portent sur le site, l’article, le type d’étape, le statut d’identité et la période de **création de l’occurrence**. Cette période n’est pas une période de consommation ni le curseur de lecture. Les résultats sont triés par date puis identifiant, avec des pages de 30 occurrences. Les identités communes ne fusionnent pas les stocks.

## Lire le graphe et la fiche

Le graphe est à gauche, la fiche à droite. Les onglets donnent accès au bilan, aux identités et états, aux transports et impacts, puis aux mouvements.

- Bleu : **point de départ du parcours**.
- Vert : **étape dont la fiche est ouverte**. Cliquer une étape ne change pas le point de départ.
- Grisé : occurrence créée après la date de lecture, connue dans les résultats complets de la simulation.
- Orange, après analyse d’impact : périmètre potentiel sur tout l’historique, sans effet physique ajouté.

**Origines**, **Destinations** et **Les deux sens** changent le sens d’exploration. **Recentrer sur cette occurrence**, dans les mouvements, change le point de départ ; une réception client ouvre ses origines. **Précédent** revient au recentrage antérieur avec sa date, **Revenir au lot principal** retrouve le lot choisi à l’ouverture.

Le compteur en tête indique les étapes affichées et le total. Les grands parcours restent limités initialement à 60 étapes, avec extension explicite. Les boutons de zoom et **Ajuster** permettent le cadrage. Les occurrences restent distinctes, même au même site pour le même article.

Survolez une flèche pour ses quantités et dates. Une flèche associée à une seule expédition ouvre son contenu complet au clic ou avec Entrée après sélection au clavier. Les mouvements offrent les mêmes accès sous forme de boutons.

## Lire une date et localiser les quantités

Le curseur et le champ de jour décrivent une **fin de journée simulée**. Les boutons précédent/suivant utilisent les jours d’événements des occurrences du parcours affiché. **Tout l’historique** revient à l’état après tous les événements disponibles. Cette date est indépendante de celle de la carte principale.

Le bilan de la fiche concerne **toute l’occurrence au site inspecté**. Une réservation déduite du stock reste séparée du départ ; elle n’est jamais déduite une seconde fois. Avant la création, la fiche indique « occurrence pas encore créée ».

Sous le graphe, **Où est la quantité du point de départ ?** suit la quantité initiale de cette occurrence : stock usine, fournisseur, dépôt, client, autre site, réservation au site, transport, consommation, service client et perte. Il suit uniquement les transports du même article et de la même unité. Une matière consommée devient une consommation dans ce bilan ; sa quantité n’est pas convertie en unités de PF. Le graphe conserve les liens vers les fabrications.

Le bilan réseau ne dépend pas du nombre de cartes actuellement affichées. Les passages successifs au dépôt puis chez le client ne comptent pas deux fois comme stock restant. Un départ sans réception enregistrée reste en transit dans l’horizon, même si une date d’arrivée avait été prévue. Le cumul des réceptions client est présenté séparément ; des retours puis nouvelles livraisons peuvent compter plusieurs passages.

Pour suivre un lot métier à partir de son origine, recherchez son PBATCH/BATCH puis choisissez sa fabrication ou entrée initiale. L’onglet **Identités / états** propose aussi les origines métier retrouvées. Si vous recentrez sur une réception mélangée, le bilan réseau suit **tout ce mélange**, et non un seul de ses composants.

### Exemple du PF signalé

| Fin du jour | Usine | Dépôt | Transport | Stock client du PF suivi |
|---|---:|---:|---:|---:|
| J279 | 14 400 | 0 | 0 | 0 |
| J280 | 0 | 0 | 14 400 | 0 |
| J282 | 0 | 14 400 | 0 | 0 |
| J291 | 0 | 10 927 | 3 473 | 0 |
| J292 | 0 | 0 | 14 400 | 0 |
| J293 | 0 | 0 | 10 927 | 3 473 |
| J294 | 0 | 0 | 0 | 14 400 |

Quantités en UN. Les réceptions client totales sont plus grandes car elles mélangent plusieurs PF. Le service client intervient ensuite ; sa quantité totale ne doit pas être attribuée intégralement au PF choisi.

### Après un mélange

Le bilan affiche des **bornes** quand l’affectation précise n’est pas connue. Exemple : une réception contient 60 unités suivies et 40 autres, puis en sert 50. Entre 10 et 50 unités suivies peuvent avoir été servies ; entre 10 et 50 peuvent rester. Ces intervalles sont liés entre eux et ne s’additionnent pas comme des quantités exactes. Une fois toute la réception servie, les 60 unités suivies ont nécessairement été servies.

Le calcul conserve des quantités entières pour les UN. Il ne crée pas d’allocation physique proportionnelle entre origines mélangées. Les contributions historiques affichées sur les cartes du nominal restent celles du modèle causal existant ; elles ne constituent pas une preuve d’allocation exacte du service postérieur au mélange.

## Identités, données absentes et scénarios

L’onglet **Identités / états** distingue lot métier simulé, occurrence, stock, origine fabricant externe et contenant. Une fabrication PBATCH identifiée n’est pas présentée comme un lot fabricant fournisseur manquant. Un stock initial conserve explicitement l’absence d’histoire avant J0. Les substitutions de référence sont présentées comme des consommations enregistrées.

Les états physiques calculés sont : stock présent, stock avec réservation, réservé en attente, occurrence épuisée, occurrence à venir ou état non vérifiable. **Présence en stock ne signifie pas libération qualité.** Les statuts qualité et péremptions restent non documentés dans ces données. Les sources et le caractère observé ou simulé des origines renseignées sont affichés. Aucun numéro fabricant, numéro de palette ou véhicule réel n’est inventé.

Les lots du nominal et ceux du scénario `scn:STATE_DEPENDENT_FULL` s’ouvrent dans des vues distinctes depuis l’accueil. Les LOT et SHIP sont locaux à chaque scénario : le même numéro ne démontre pas qu’il s’agit du même objet dans deux calculs. La vue risque utilise ses propres CSV et le graphe d’entrée désigné par son manifeste. Elle présente les incidents déjà associés aux réceptions. Elle ne superpose pas les contributions PF du nominal.

Les **transports, mouvements détaillés et impacts potentiels** portent sur tout l’historique, comme indiqué dans leurs onglets. Le curseur filtre le bilan local et le bilan réseau, pas ces listes historiques. Aucun nouvel incident physique n’est appliqué : quarantaine, rebut et retard ciblés seront une étape ultérieure, conformément au choix utilisateur du 20 septembre.

## Vérifier et reproduire

Le module `lot_journey.js` regroupe le parcours, les transports, l’explorateur, la chronologie et les dossiers d’enquête, dans cet ordre. Les tests sur petits cas vérifient les réservations, départs partiels, transit en fin d’horizon, mélanges, inconnues, substitutions et arrondis KG. Les allocations possibles d’un petit mélange sont énumérées indépendamment pour vérifier les bornes.

Les revues Chromium hors ligne rapprochent les quantités datées des CSV, vérifient recherche, pagination, filtres, clics, clavier, visibilité à 1366 × 768 et absence d’erreurs JavaScript. L’audit de toutes les occurrences utilise le même code de bilan que l’interface : il complète les rapprochements indépendants sans les remplacer.

La publication du nominal utilise `python -m etudecas.visualization.maps.material_delivery` ; celle d’un scénario distinct utilise `python -m etudecas.visualization.maps.material_delivery --mode scenario`. Le second refuse un graphe différent de celui du manifeste. Les deux lisent des résultats existants et produisent un nouveau HTML sans rejouer le moteur. Les empreintes de sources et de fichiers produits accompagnent la livraison.

Voir les [preuves de cette livraison](../archive/README.md) et le [bilan daté](../archive/README.md).
