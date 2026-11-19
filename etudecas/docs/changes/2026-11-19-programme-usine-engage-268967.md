# Engagement d'usine connu avant le gel pour 268967

Le même signal de janvier a deux effets selon son statut. Dans l'essai
révocable, l'achat avance, puis le lot est annulé le 27 janvier. Dans
l'essai où le programme représente un engagement, l'achat, la fabrication,
le transport et le contrôle se succèdent. Le rapprochement au réel
progresse pour le cumul et le stock de D1920. L'écart hebdomadaire de
production augmente légèrement. [Essai révocable](2026-11-19-programme-anticipe-268967.md)

## Chaîne vérifiée

| Étape du scénario avec engagement | Date simulée | Quantité |
| --- | --- | ---: |
| Signal des composants de 1430 connu, date du même lot avancée | 12 janvier | Lot de 107 800 PF |
| Ordre figé et commande du composant principal 344135 | 21 janvier | 120 000 composants |
| Réception du composant à l'usine | 25 février | 120 000 composants |
| Mise à disposition du composant après contrôle | 3 mars | 120 000 composants |
| Prélèvement du composant principal, première fabrication et expédition | 17 mars | 107 800 composants et 107 800 PF |
| Arrivée physique du même lot à D1920 sous contrôle | 19 mars | 107 800 PF |
| Stock du lot utilisable à D1920 | 9 avril | 107 800 PF |

Le même identifiant d'ordre et le même lot physique relient ces étapes.
Ni le volume de l'ordre ni les quantités physiques ne sont modifiés par
l'adaptateur. La réservation et la consommation sont deux événements
distincts. Le 30 avril, les 107 800 unités de ce lot sont toujours à D1920,
utilisables. Les clients sont servis avec le stock déjà présent.
Les sorties livrées et l'attente quotidienne restent identiques.

## Écarts au réel jusqu'au 30 avril

Les deux témoins et l'essai avec engagement sont comparés sur les mêmes
120 jours. Les témoins donnent les mêmes chiffres PF sur cette fenêtre.
L'exécution du lot en une journée reproduit un volume et un mouvement
de stock, avec un profil hebdomadaire encore différent de celui estimé
à partir des prélèvements d'étuis.

| Indicateur 268967 | Témoins | Engagement | Observation |
| --- | ---: | ---: | ---: |
| Cumul sur 10 semaines documentées | 0 | 107 800 | 280 250 unités estimées |
| Écart du cumul au réel | −280 250 | −172 450 | Réduction de 107 800 unités |
| Écart absolu moyen par semaine | 28 025 | 28 955 | Augmentation de 930 unités |
| Écart absolu moyen sur 17 photos à D1920 | 53 627 | 36 964 | Réduction de 31,1 % |
| Stock physique final simulé à D1920 | 592 613 | 700 413 | Approvisionnement supplémentaire de 107 800 unités |
| Demande publiée et servie en simulation | 508 921 | 508 921 | Service quotidien identique |

La semaine du 17 mars, l'indicateur réel vaut 49 250 unités. Le
lot entier de 107 800 augmente donc l'erreur de cette semaine de
9 300 unités. Les 27 couples site et article représentant les autres
usages gardent les mêmes demandes, consommations et attentes. Les
quantités commandées et reçues sur la période restent identiques par
article, avec un calendrier d'achat différent pour le 344135.

Pour 268091, les ordres initiaux, la production, les stocks et les
livraisons sont identiques sur la fenêtre. La demande publiée et servie
vaut 1 167 461 unités. Les composants de 1810 donnent certains signaux
concordants. Les engagements initiaux existants rendent leur attribution
à un nouveau lancement indéterminée.
[Comparatif des deux PF](../../resultats/programme_anticipe_engage_268967_20261119.html)

## Interprétation et portée

Dans cette simulation, le besoin net du dépôt et l'engagement usine ont
des rôles différents. Le premier peut justifier de différer une
fabrication. Le second maintient un calendrier et déclenche ses achats
longtemps avant le lancement. La distinction empêche d'effacer
systématiquement un programme déjà engagé lorsqu'un stock aval couvre
encore la demande. La fermeté de l'ordre industriel reste à établir.
Le 17 mars a été choisi comme premier jour ouvert de la semaine source.
Les dates physiques simulées éclairent le mécanisme.

Le moteur nominal conserve son comportement. L'option de l'expérience
porte exclusivement sur l'identité du lot avancé, une fois le gel natif
vérifié. Les autres ordres suivent la règle habituelle de réduction.
Le témoin et l'essai révocable couvrent 152 jours. La variante avec
engagement s'arrête au 30 avril, ce qui laisse son rattrapage de mai
hors de la comparaison. Aucun débit machine ni durée de fabrication
n'a été recalibré.

Les six tests ciblés, la qualification native et la porte technique
passent. La contrelecture indépendante vérifie 46 156 points, dont les
sources, le préfixe commun, l'achat, les huit composants, les lots,
les stocks et le service quotidien. La documentation générée reste
en attente de revue de ses liens et empreintes. La vue HTML a fait
l'objet de contrôles statiques et d'une inspection du graphique PNG.
[Manifeste](../../artifacts/testing/programme_anticipe_engage_268967_20261119/final_manifest.json)
