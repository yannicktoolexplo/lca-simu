# Audit du suivi des lots et proposition d'interaction

Audit du 19 septembre 2026, sur la carte `supply_graph_corrected_map_20260918_transport_impacts.html`. Aucune modification de la carte ou du moteur pendant cet audit. Une maquette ergonomique indépendante accompagne les constats.

## Verdict

Le socle permet une exploration utile de la généalogie simulée. Les bilans locaux, contributions de PF, réceptions mélangées, transports et périmètres potentiels sont distingués. Le produit n'est cependant pas encore suffisamment direct pour répondre sans ambiguïté à « où est n'importe quel lot, à telle date, et qui a reçu quoi ? ».

La prochaine étape doit améliorer la recherche, la cohérence de la sélection et la lecture graphique. Ajouter des panneaux supplémentaires sans revoir leur organisation accentuerait la difficulté actuelle.

## Preuves et périmètre

Le [rapport exécutable](../artifacts/testing/lot_usability_20260919/audit.json) provient d'une nouvelle ouverture hors ligne de la carte, de tests d'interaction à 1366 × 768 et de l'exécution de la fonction actuelle de bilan sur toutes les occurrences du payload.

- 14 803 occurrences, 58 816 événements et 33 220 liens.
- Les 14 803 occurrences passent le bilan local de l'affichage ; aucune exception détectée. Ce contrôle utilise le code de bilan existant, ce n'est pas une seconde implémentation indépendante.
- La [qualification précédente](../artifacts/testing/transport_impacts_20260919/verification-summary.json) conserve les rapprochements indépendants aux CSV, 48 tests, 62 contrôles navigateur et 62 familles d'invariants CSV. Ces preuves portent sur leurs cas et invariants ; elles ne certifient pas tous les usages ni la calibration industrielle.
- 1 657 occurrences mélangées et 61 stocks initiaux.
- Aucun lot fabricant ni contenant entrant documenté dans le payload nominal actuel.
- 1 641 groupes transport : 634 avec estimation de nombre de camions, 1 007 sans nombre connu, aucun chargement proposé sur profil physique complet dans ce contexte.
- Tous les événements du CSV audité appartiennent à `scn:BASE`. Cet audit ne valide pas l'exploration des lots de tous les scénarios.
- Aucun nouveau message d'erreur JavaScript dans les parcours essayés. Chargement mesuré à 7,38 s sur cette machine, non représentatif d'un benchmark général.

## Ce qui est acquis

1. Séparation entre lot métier, occurrence de stock, réception, expédition et estimation camion. L'absence de numéro fabricant reste visible.
2. Navigation amont et aval sur les liens physiques. Les autres branches d'un stock ancêtre et les autres origines d'un descendant mélangé ne sont pas ajoutées indistinctement.
3. Contribution du PF distincte du total de la livraison. Le cas signalé conserve 3 473 + 10 927 = 14 400 UN.
4. Bilans locaux avec traitement des réservations, départs, consommations, pertes et service client. Les erreurs et données absentes ne sont pas transformées en zéros fiables.
5. Contenu complet des expéditions, accès aux regroupements camion existants et à leurs limites.
6. Impact potentiel conservateur, avec exclusion des lots sans lien simplement cochargés. Les effets physiques d'un nouvel incident ne sont pas inventés.
7. Fenêtre simplifiée indépendante du suivi détaillé, preuves de non-mutation, documentation reliée au code et aux tests.

## Défauts ou limites constatés

| Priorité | Constat vérifié | Conséquence | Amélioration proposée |
|---|---|---|---|
| P1 | `LOCC-00002658` renvoie zéro résultat alors que cet identifiant figure dans le suivi. | Copier un identifiant affiché ne garantit pas de retrouver le lot. | Indexer tous les identifiants utiles : LOT, LOCC, STOCKLOT, PBATCH/BATCH, SHIP, et origines documentées. |
| P1 | Rechercher `PBATCH-411EC755D7110AE0` renvoie deux occurrences ; ses deux réceptions client mélangées sont aussi dans les données, mais ne sont pas trouvées directement. | La recherche n'est pas exhaustive pour la présence d'un lot métier. | Indexer `business_lot_ids` et distinguer résultat « identité du lot » et résultat « contient une part du lot ». |
| P1 | Rechercher `338929` donne 4 262 résultats, avec 30 boutons seulement. | La recherche par article ne suffit pas à retrouver une réception précise. | Filtres site, période, type, statut, tri et pagination ; regroupement des résultats par identité métier sans fusionner les occurrences. |
| P1 | Après un clic sur LOT-00002738, la fiche est celle du client, mais le focus du graphe reste LOT-00002658. | La sélection visible, la fiche et le recentrage sont difficiles à distinguer. | Un encadrement clair pour l'étape inspectée, un point de départ distinct et une action explicite de recentrage ; historique de navigation. |
| P1 | À 1366 × 768, le diagramme débute vers le bas de la fenêtre, après les textes, la fiche et les panneaux. | La vue dite simplifiée demande déjà de défiler pour voir les destinations. | Graphe central visible d'emblée ; fiche latérale ; panneaux secondaires dans des onglets. |
| P1 | Un cas matière comporte 324 occurrences ; seules 60 sont affichées au départ. La limite est annoncée sous le graphe. | Les branches restantes peuvent être difficiles à remarquer. | Compteur visible en tête, expansion par voisinage, filtres et cadrage ; conserver l'identité de chaque occurrence et ses liens. |
| P2 | Aucun curseur temporel propre au parcours ; les bilans portent sur le dernier événement, l'impact sur tout l'historique. | « Où est le lot à J280 ? » n'a pas de réponse directe dans cette vue. | Mode fin de journée incluant réservations, stock local et transit, avec cumul reçu séparé des stocks clients. |
| P2 | Le solde est local à une occurrence. | Un solde nul à l'usine peut être lu comme disparition du lot. | Résumé du lot métier sur le réseau, à une date donnée, avec contributions et sans compter deux fois les passages successifs. |
| P2 | Pas de zoom/cadrage ni d'historique propre au parcours, pas de lien direct d'état ou d'export dédié. | Les grands parcours et le partage d'une enquête demandent trop de manipulations. | Zoom, ajuster à l'écran, retour précédent, état partageable et export contextualisé. |
| Données | Numéros fabricant et contenants absents, nombreux groupes transport sans estimation. | Un suivi industriel complet ne peut pas être reconstruit par l'affichage seul. | Renseigner les allocations de lots fournisseurs, profils logistiques et identités physiques, avec sources et distinction observé/simulé. |

Le libellé « origine fabricant non documentée » doit aussi être contextualisé : une fabrication simulée portant un PBATCH connu et une matière au numéro fabricant inconnu ne représentent pas le même manque d'information.

## Proposition d'interactivité

La [maquette indépendante](proposals/lot-explorer.html) montre une organisation possible sur le PF signalé :

- en tête, identité du lot, scénario et quantité de référence ;
- un curseur de date et des boutons « événement précédent / suivant » ;
- un graphe central qui reste visible et une fiche à droite, actualisée au clic ;
- des vues « Parcours », « Transports » et « Réceptions client », conservant le contexte ;
- des quantités de contribution distinguées des réceptions complètes.

Le curseur illustre un vrai besoin : à J280, les 14 400 UN sont en transport ; à J282 elles sont au dépôt ; à J291, 3 473 sont en transport et 10 927 au dépôt. À J294, les deux réceptions totalisent 14 400 UN du PF. Il s'agit de la fin de journée, selon les mouvements du nominal. Le cumul reçu n'est pas le stock restant chez le client.

La maquette n'est pas intégrée au produit. Elle ne couvre que l'aval de ce PF, jusqu'aux réceptions J293/J294. Ses sept dates d'événements et sa navigation ont été [contrôlées](../artifacts/testing/lot_usability_20260919/proposal-checks.json). Les matières amont, le service client postérieur et les incidents en sont exclus explicitement.

Pour la vue complète future : survol d'un lien pour quantité/date, clic sur ce lien pour l'expédition, déploiement d'une branche sans perdre la sélection, et commande d'impact conservant sa cible clairement visible. Les rapprochements visuels doivent rester des conteneurs dépliables, jamais une fusion de stocks créant des chemins inexistants.

## Ordre de travail recommandé et critères d'acceptation

1. **Fiabiliser l'accès et la sélection.** Tout identifiant affiché doit être recherchable ; la recherche PBATCH doit retrouver les deux réceptions mélangées ; un clic doit identifier sans ambiguïté la fiche ouverte.
2. **Réorganiser le parcours simplifié.** À 1366 × 768, le graphe du PF de référence et ses deux destinations doivent être visibles, avec le détail accessible sans perdre le graphe. Conserver le suivi détaillé existant.
3. **Ajouter le temps et le bilan réseau.** Vérifier des cas stock → réservation → transit → réception, des départs partiels, des mélanges et un horizon se terminant pendant le transport. Rapprocher les états aux CSV et ne pas confondre réception et service client.
4. **Étendre les données et la couverture.** Rechercher les origines et contenants renseignés, parcourir un lot sans aval, un stock initial, un lot épuisé, un cas de remplacement de référence et un scénario de risque identifié. Afficher clairement les inconnues et la provenance.
5. **Puis simuler les incidents physiques ciblés.** Définir date d'application, objet ciblé et règle de quarantaine/rebut/retard ; comparer au nominal et vérifier la propagation réelle. Une exposition généalogique seule ne suffit pas.

Les étapes 1 et 2 ont le meilleur effet immédiat sur la clarté. Le temps et le bilan réseau apportent ensuite une capacité nouvelle ; les incidents physiques viennent après cette clarification.
