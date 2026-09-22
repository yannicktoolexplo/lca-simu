# Conserver une enquête et déplier un grand parcours

Dans **Parcours simplifié des lots**, développez **Conserver ou partager cette enquête**. Les commandes fonctionnent hors ligne dans les HTML du nominal et du scénario de risque.

## Enregistrer puis rouvrir

**Enregistrer l’enquête** télécharge un petit fichier JSON. Il mémorise le point de départ, le lot principal, la fiche inspectée, le sens, le jour, l’onglet, les filtres de recherche, le zoom et le voisinage déplié. Si un transport ou une cible d’impact sont sélectionnés, leurs identifiants sont également conservés.

Pour reprendre plus tard, ouvrez la carte contenant ces données, puis **Ouvrir une enquête** et choisissez le fichier. Les quantités sont relues dans la carte ; le périmètre d’impact éventuel est recalculé. L’historique du bouton « Précédent » repart à vide. Les positions des barres de défilement et les détails secondaires dépliés ne sont pas mémorisés.

Le fichier ne contient pas les résultats de simulation. Pour le transmettre à une personne, conservez aussi la carte HTML correspondante. Il n’y a pas d’envoi automatique ni de service externe.

### Empêcher les confusions entre calculs

L’enquête est liée par empreinte SHA-256 aux événements, à la généalogie, aux occurrences, au registre matières, au contexte camion et aux nœuds de la carte. L’ordre des événements fait partie de cette identité, car il peut déterminer l’ordre des mouvements dans une journée.

Le nominal et un scénario peuvent réutiliser les mêmes numéros LOT ou SHIP. Cela ne suffit pas pour rouvrir une enquête : si l’empreinte diffère, l’import est refusé et la navigation actuelle reste intacte. La carte d’origine reste nécessaire. L’empreinte identifie les données comparées ; elle ne certifie ni leur vérité industrielle, ni la version du moteur ou du rendu.

Le fichier importé est validé avant toute modification de la navigation : format, données, lots, sens, jour, voisinage, fiche visible, filtres, zoom, expédition et cible d’impact. Un fichier JSON illisible ou dépassant 1 Mo est refusé. Il ne peut jamais importer ou modifier des stocks, mouvements, statuts qualité ou incidents physiques.

## Exporter une fiche lisible et imprimable

**Exporter la fiche HTML** produit un instantané autonome, sans script, lisible hors ligne et imprimable depuis le navigateur. Il contient :

- scénario, date de lecture, point de départ et occurrence inspectée ;
- bilan local de l’occurrence entière à la date retenue ;
- bilan réseau de la quantité du point de départ, avec bornes après mélange si nécessaire ;
- tous les liens physiques du parcours choisi, leurs dates, quantités, unités et identifiants d’expédition ;
- sélection éventuelle du transport et de la cible d’impact, limites et empreinte des données.

Les bilans correspondent à la date choisie. **La table des liens couvre tout l’historique du sens sélectionné**, y compris les événements ultérieurs à cette date. Elle n’est pas tronquée par le nombre de cartes affichées ni le voisinage. Les quantités des liens sont celles des mouvements entiers ; une livraison mélangée ne devient pas intégralement attribuable au PF suivi.

La fiche HTML n’est pas un export du graphe interactif, ni un dossier exhaustif de tous les événements qualité ou de tous les chargements. Pour reprendre les transports et impacts en détail, utilisez le fichier JSON avec la carte. Une matière consommée n’est pas convertie artificiellement en quantité de PF. Les informations fabricant ou qualité absentes restent inconnues.

## Déplier un grand parcours

Le sélecteur **Voisinage**, au-dessus du graphe, propose tout le parcours ou les occurrences à une, deux ou trois liaisons du point de départ. Le sens **Origines / Destinations / Les deux sens** continue de définir le périmètre autorisé.

Cliquez sur une occurrence visible, puis **Étendre depuis la fiche** pour révéler ses voisins directs dans ce périmètre. Le point de départ et la fiche restent conservés. Aucun stock n’est fusionné ; aucun lien absent de la généalogie n’est créé. Pour repartir d’une branche précise, utilisez le recentrage habituel.

Le compteur indique toujours le nombre affiché et le total du parcours. Au-delà de 60 cartes, la pagination continue de s’appliquer ; les occurrences les plus proches du point de départ sont affichées d’abord. Le bouton **Ajuster** cadre les cartes visibles. Un changement de sens ou de point de départ remet les extensions manuelles à zéro. Le retour au recentrage précédent retrouve son voisinage.

**Cette réduction est uniquement graphique.** Elle ne réduit ni le bilan réseau, ni le périmètre potentiel d’impact, ni les liens de la fiche exportée. Une branche masquée n’est pas une branche absente des données.

## Vérifications

Les tests utilisent de petits cas pour vérifier la restauration, l’absence de mutation des données, les fichiers invalides, un même numéro de lot associé à des données différentes, l’échappement HTML et les mélanges. Un transfert après mélange reste inclus dans le bilan réseau alors que sa carte est masquée par le voisinage.

Les essais Chromium ouvrent les vrais HTML hors ligne : téléchargement du JSON et du rapport, rechargement complet, restauration, déploiement du dépôt vers ses deux clients, parcours matière de plus de 300 occurrences et refus d’une enquête nominale dans la vue risque. Le rapport est aussi imprimé en PDF lors de la vérification.

Voir les [preuves de livraison](../artifacts/testing/lot_cases_20260920/verification-summary.json), le [guide général](EXPLORATEUR_DES_LOTS.md) et la [fiche HTML d’exemple à J291](../artifacts/testing/lot_cases_20260920/case-browser/fiche-pf-j291.html).
