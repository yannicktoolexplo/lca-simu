# Deuxième engagement usine pour 268967

Le témoin contient un ordre de 107 800 unités lancé le 17 mars et traité sur
dix jours ouvrés. L’essai conserve cet ordre et avance le deuxième ordre
déjà présent dans le carnet. La décision intervient le 9 février pour un
lancement le 7 avril. Le moteur garde l’identité et la quantité de l’ordre,
ainsi que son horizon figé de 56 jours. L’adaptateur protège chacun des deux
engagements après son gel natif. Cette fermeté reste une hypothèse.
[Protocole](../../artifacts/testing/deuxieme_engagement_268967_20261120/protocol.json)

Le choix repose sur les deux besoins concordants du MRP du 9 février,
110 495 étuis et 23 424,94 mètres pour le repère du 6 avril
(`Flow_Data_MRP_results.xlsx`, `Feuille1!I5628,I5875`). Le 7 avril est le
premier jour ouvert de la semaine qui suit ce repère. Le deuxième ordre
garde l’exécution journalière du moteur sans plafond machine. Les stocks
initiaux, les délais, la demande et le profil de besoins complémentaires
restent ceux du témoin sur 120 jours. Le MRP recalcule les achats.

Avant le calcul, le prévol retrouve 12 200 unités disponibles de 344135
dans le témoin le 7 avril, pour 107 800 requises. Avec le même délai que
l’achat simulé de janvier, une commande passée au gel du 11 février
atteindrait la disponibilité le 24 mars. Cette date préserverait les dix
jours ouvrés de sécurité. La date limite théorique pour être simplement
prêt le 7 avril est le 25 février. Si tout le lot part le 7 avril, les deux
jours calendaires de transport et les quinze jours ouvrés de contrôle donnent
une disponibilité le 30 avril, dernier jour commun aux deux calculs.
[Prévol indépendant](../../artifacts/testing/deuxieme_engagement_268967_20261120/validator/preflight_second_engagement.json)

## Le deuxième ordre déclenche l’achat nécessaire

| Étape dans le moteur | Date | Quantité |
| --- | --- | ---: |
| Gel natif de l’ordre de fabrication | 11 février | 107 800 produits finis |
| Passation de la commande 344135, `MRPREQ-B1C790D88C9ADBA7` | 11 février | 120 000 unités |
| Réception physique du 344135 | 18 mars | 120 000 unités |
| Composant utilisable après contrôle | 24 mars | 120 000 unités |
| Fabrication et départ du deuxième lot | 7 avril | 107 800 produits finis |
| Entrée physique à Muret | 9 avril | 107 800 produits finis |
| Libération à Muret | 30 avril | 107 800 produits finis |

Le témoin prévoit 480 000 unités de 344135 le 1er avril. L’essai en
commande 120 000 au gel du nouvel ordre et 360 000 le 1er avril.
La généalogie retrouve dans le deuxième lot les **12 200 unités** restantes
de l’ancien achat et les **95 600** nécessaires issues de l’achat avancé.
Il reste **24 400 unités** de celui-ci après le prélèvement. Le premier lot
garde son lancement, son travail, sa fin physique et sa libération à Muret.

La révision du programme simulé de 268967 reste proche de **49,2 %**,
avec 1 326 révisions sur 2 696 comparaisons actives dans le témoin et
1 304 sur 2 651 dans l’essai. Les calendriers de lancement diffèrent sur
56 publications. Pour 268091, les calendriers coïncident et le taux
reste de 2 881 sur 4 529 comparaisons, soit 63,6 %.
[Comparaison des programmes](../../artifacts/testing/deuxieme_engagement_268967_20261120/replanning_comparison.json)

## Le volume se rapproche, le lancement est trop tôt

| Mesure de 268967 | Témoin | Deux engagements |
| --- | ---: | ---: |
| Production physique cumulée sur la fenêtre | 107 800 | 215 600 |
| Écart au cumul estimé de 280 250 unités sur les semaines documentées | −172 450 | −64 650 |
| Écart absolu moyen des retraits sur 10 semaines | 18 175 | 28 955 |
| Écart absolu moyen du stock physique à Muret sur 17 relevés | 32 172 | 36 777 |
| Quantités simulées livrées aux clients | 508 921 | 508 921 |

Le 7 avril, le moteur concentre 107 800 prélèvements d’étuis sur un jour.
La source donne zéro prélèvement cette semaine, puis 71 920 et 94 000 les
semaines du 14 et du 21 avril (`Feuille1!J857:J859` dans les mouvements).
L’arrivée à Muret améliore le rapprochement du relevé du 28 avril, mais
dégrade ceux des 14 et 21 avril. Le 14 avril, Muret compte 709 197 unités
dans le relevé. Les deux simulations donnent 740 084 et 847 884 unités.
[Graphique](../../resultats/deuxieme_engagement_268967_20261120.png)

Les départs clients simulés des deux références gardent les mêmes dates
et quantités. Les 508 921 unités de 268967 sont servies avec les stocks
déjà utilisables. Le deuxième lot ajoute 107 800 unités au stock final
de Muret et se libère le dernier jour de l’essai. L’utilisation de ce stock
en mai reste à mesurer. Les autres usages des composants suivis et les
résultats de 268091 coïncident.

L’essai soutient la séparation entre **engager l’achat** dès la décision
usine et **autoriser le travail** à la date opérationnelle. Le besoin
hebdomadaire de début avril a suffi à déclencher l’achat simulé. Les
prélèvements observés réfutent le calendrier d’un lot entièrement exécuté
le 7 avril comme explication de la vague de travail des deux semaines
suivantes. La priorité est d’identifier ce que date le repère MRP, puis
de tester séparément la date et l’étalement du travail à partir d’un signal
connu avant le gel. La variante reste expérimentale.

Neuf tests ciblés passent, ainsi que la qualification du run et le
rapprochement de leurs empreintes. Deux contrelectures contrôlent les
résultats et la traçabilité de 344135 depuis l’achat jusqu’au prélèvement.
[Manifeste des preuves](../../artifacts/testing/deuxieme_engagement_268967_20261120/final_manifest.json)
