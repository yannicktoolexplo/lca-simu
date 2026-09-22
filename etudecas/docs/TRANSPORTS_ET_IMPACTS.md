# Transports et impacts dans le parcours simplifié

Depuis le 20 septembre, ces panneaux sont regroupés dans l’onglet **Transports / impacts** de la fiche latérale. Le graphe reste visible pendant leur consultation. Ils couvrent tout l’historique, indépendamment du curseur de date qui pilote les bilans local et réseau. Une flèche associée à une seule expédition ouvre aussi son contenu. Voir le [guide de l’explorateur](EXPLORATEUR_DES_LOTS.md).

Ces outils appartiennent à **Parcours simplifié des lots**. Le suivi détaillé existant et les résultats du moteur restent inchangés.

## Examiner un transport

Sélectionnez une étape du parcours, puis développez **Transports de l'occurrence** et cliquez sur une expédition SHIP. Le détail présente tous ses lots au départ et les occurrences reçues, avec les sites, dates, articles et quantités. Un clic sur un lot permet de suivre son parcours et sa fiche.

Le total expédié provient seulement des événements de départ, par article et unité. Les réservations ne sont pas additionnées aux départs ; les réceptions ne sont pas une seconde expédition. La quantité de toute l'expédition reste distincte de la contribution du PF sélectionné. Une réception absente du registre reste absente, même lorsqu'une date d'arrivée prévue existe.

Le détail reprend les **regroupements camion déjà calculés** : trajet, fenêtre hebdomadaire, palettes estimées ou proposées, nombre de camions estimé ou chargements proposés, données physiques manquantes et sources des hypothèses. Les autres expéditions du groupe sont accessibles. Le groupe est présenté en entier et peut dépasser le périmètre du lot examiné.

Un SHIP est une expédition simulée, pas un camion réel. Les nombres estimés ne prouvent pas un chargement physique précis ; le module n'invente pas l'affectation d'un lot à un véhicule. Un profil absent donne une capacité inconnue. Les dates et regroupements de la simulation ne sont pas recalculés.

## Rechercher les impacts potentiels

Dans **Rechercher les impacts potentiels**, utilisez **Analyser cette occurrence**. Le parcours se centre sur son aval et les occurrences concernées prennent un contour orange. Les listes présentent :

- les occurrences de départ et les fabrications potentiellement concernées ;
- les réceptions client et les expéditions liées au périmètre ;
- les soldes locaux ou réservations encore en attente, au dernier événement de chaque occurrence ;
- les occurrences dont le solde ne peut pas être établi.

Si des lots fabricant sont renseignés, le sélecteur **Lot fournisseur** permet d'analyser toutes les réceptions qui leur sont explicitement affectées, ainsi que les origines possibles conservées après mélange. Sans identité fabricant documentée, l'analyse reste possible par occurrence ; une même référence article ne suffit pas à fusionner des réceptions. Les origines simulées restent étiquetées comme telles.

Le périmètre suit les descendants par les liens physiques positifs de production et de transport. Les occurrences et expéditions sont dédupliquées. Il ne remonte pas vers les autres origines d'une réception mélangée. Les autres lots d'une expédition ou d'un groupe camion ne sont pas considérés concernés par simple cochargement.

Une réception mélangée et ses usages aval sont inclus de façon conservatrice. Les quantités affichées sont les totaux des occurrences, pas des quantités défectueuses ou des quantités de PF attribuées à une matière. Les stocks de plusieurs unités ou de plusieurs étapes ne sont pas additionnés. Les listes couvrent toute l'analyse ; le diagramme suit le point de navigation courant. Les listes dépassant 50 lignes annoncent leur limite et permettent d'en afficher davantage.

Cette exploration porte sur tout l'historique disponible. Elle n'applique aucune quarantaine et ne recalcule ni retard, ni rebut, ni perte de service. **Effacer l'analyse** retire le périmètre et les contours orange. Ouvrir à nouveau la fenêtre démarre une nouvelle exploration.

## Vérification et code

Le module `visualization/maps/lot_journey_operations.js` lit les événements, la généalogie et le contexte logistique existants. Les tests sur petits cas couvrent les chargements mélangés, la réservation suivie du départ, les articles et unités distincts, les branches sans lien, les identités fournisseur, les données manquantes et la préservation des données et de la fenêtre existante.

Les contrôles Chromium comparent le contenu des expéditions et le périmètre aval aux CSV, puis vérifient la remise à zéro et les empreintes du registre avant/après navigation. Les regroupements affichés sont rapprochés du contexte logistique existant ; leurs hypothèses industrielles ne sont pas certifiées par ce contrôle. Voir les [preuves de livraison](../artifacts/testing/transport_impacts_20260919/verification-summary.json).
