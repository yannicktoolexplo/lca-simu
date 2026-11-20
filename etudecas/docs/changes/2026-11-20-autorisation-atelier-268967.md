# Autorisation de travail d’un lot déjà engagé

L’essai conserve les deux ordres, dont le deuxième de 107 800 unités
engagé le 11 février, et les dates du carnet de l’essai précédent. Le
7 avril, jour de lancement prévu, l’atelier apprend que le travail est
autorisé à partir du 14 avril. Le deuxième lot garde sa durée d’un jour.
Le premier lot garde ses dix jours ouvrés. Les besoins matière du carnet
et la commande anticipée de 344135 restent soumis aux mêmes règles.
[Protocole](../../artifacts/testing/autorisation_atelier_268967_20261120/protocol.json)

Les versions MRP du 12 janvier au 2 février portent le même besoin
d’emballages à 1430 au repère du 13 avril. La version du 9 février porte
les mêmes quantités au repère du 6 avril. Le 14 avril correspond au
premier jour ouvert de l’ancienne semaine. C’est un report hypothétique
d’une semaine, établi à partir de repères connus avant le gel. La colonne
source décrit une sortie prévue de composant. La date réelle de travail
en atelier reste inconnue.
[Cellules et calcul préalable](../../artifacts/testing/autorisation_atelier_268967_20261120/preflight.json)

Les deux calculs sont comparés jusqu’au 30 avril. Le candidat est prolongé
au 7 mai pour observer la sortie du contrôle avec le calendrier du cas.
Les 160 lignes du profil fixe communes aux deux calculs sont identiques.
Les neuf lignes ajoutées correspondent aux publications hebdomadaires
du profil conservé, à leur date. Le calendrier de contrôle compte les
jours du lundi au vendredi, y compris le 1er mai dans ce cas.

## Du carnet à la libération à Muret

Le composant 344135 du deuxième lot conserve la passation du **11 février**,
la réception du **18 mars** et la disponibilité du **24 mars**. Du 7 au
13 avril, le journal indique que l’ordre reste en attente d’autorisation.
Le carnet garde ses dates du 7 et du 10 avril. Après l’annonce, le MRP
utilise une seule réception ferme projetée de 107 800 unités au **17 avril**,
qui inclut la marge de trois jours du carnet. Le prélèvement et la sortie
physique du lot se produisent le **14 avril**, lors du travail autorisé.

Le lot arrive le **16 avril** et reste en contrôle jusqu’au **7 mai**.
Au 30 avril, Muret compte 808 213 unités physiques dans les deux cas.
Dans le candidat, 107 800 sont toujours en contrôle et 700 413 sont
utilisables. Le 7 mai, les 808 213 unités sont utilisables dans le candidat.
Le premier lot conserve sa chronologie.

| Indicateur de 268967 sur les dates communes | Lancement 7 avril | Lancement 14 avril |
| --- | ---: | ---: |
| Cumul physique simulé | 215 600 | 215 600 |
| Écart au cumul estimé de 280 250 unités | −64 650 | −64 650 |
| Écart moyen des prélèvements sur 10 semaines | 28 955 | **14 571** |
| Écart moyen du stock physique à Muret sur 17 relevés | 36 777 | **30 436** |
| Unités livrées aux clients en simulation | 508 921 | 508 921 |

Le travail rejoint une semaine où les retraits d’étuis sont observés.
Un lot exécuté en une journée concentre toujours 107 800 unités, face à
71 920 retirées la semaine du 14 avril et 94 000 la semaine suivante.
Le gain sur l’écart de stock physique vient du relevé du 14 avril. Il
passe de 847 884 à 740 084 unités simulées, pour 709 197 observées.
Le report laisse le service de 268967 et de 268091 identique jusqu’au
30 avril. Le stock déjà disponible absorbe l’attente.
[Graphique](../../resultats/autorisation_atelier_268967_20261120.png)

Le programme de 268967 change pour 14 publications de lancement, avec
un taux de révision inchangé de 1 304 sur 2 651 comparaisons actives.
Le programme de 268091 coïncide sur toute la fenêtre commune.
[Comparaison des décisions](../../artifacts/testing/autorisation_atelier_268967_20261120/replanning_comparison.json)

L’essai confirme l’intérêt de distinguer l’engagement d’achat, le travail
et la libération. Le 14 avril reste une hypothèse. La durée du deuxième
lot et la part éventuelle d’autres lots dans la seconde semaine restent
à départager. La référence nominale garde ses paramètres.

Le premier calcul a été interrompu après détection d’un défaut dans
l’ordre d’initialisation d’un export. Le calcul qualifié reprend les
mêmes paramètres après correction de cet export. Cinq tests ciblés, la
qualification native et la contrelecture indépendante vérifient la
livraison. Les traces avant le 7 avril coïncident, à l’exception des chemins
et empreintes du profil prolongé cités dans 128 notes de provenance. Les
quantités des usages déclarés sont identiques sur la fenêtre commune.
[Manifestes et correction](../../artifacts/testing/autorisation_atelier_268967_20261120/final_manifest.json)
