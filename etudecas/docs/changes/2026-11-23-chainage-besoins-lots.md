# Avène, Gien et Muret · des besoins datés aux lots

[Courbes interactives](../../resultats/chainage_besoins_lots_20261123.html) ·
[Comparaison 2025 avec les données industrielles](../../resultats/priorites_avene_gien_20261122.html) ·
[Manifeste des contrôles](../../artifacts/testing/chainage_besoins_lots_20261123/final_manifest.json)

Le lien commun est la **quantité de produit fini que Muret peut utiliser à la date du besoin**. Une réception ferme, même décalée, reste déduite du volume à fabriquer. Le moteur signale son retard et conserve les ordres existants. Quand une partie de la quantité perd son statut ferme, le besoin net augmente et l’usine peut proposer un lot entier. Le tampon disponible à Muret détermine si un retard crée un manque. Ce calcul reste propre à chaque référence.

## Avène · 268091

À la clôture du 28 avril, les **63 653 unités de demande publiée** sont en transit de Muret vers le client dans le rejeu. Le plan prévoit de lancer **11 lots, soit 345 600 unités**, le 26 mai, au premier jour hors gel. Les demandes de transfert cumulées à l’usine au 29 mai atteignent 1 223 572 unités. Après déduction de 887 370 déjà engagées, le besoin net atteint **336 202 unités**. La lotification ajoute 9 398 unités.

Les engagements existants, projetés une seule fois, laissent un **manque prévisionnel de 69 367 unités du 27 au 29 mai** à Muret, résorbé le 30 mai. Les nouveaux lots du 26 mai sont projetés utilisables à Muret à partir du 13 juin. En retirant uniquement les objectifs de protection datés du 29 mai au 12 juin, le lancement du 26 mai tombe à 57 600 unités et le pic sur quatre semaines à **302 400 unités, soit −12,5 %**. Le total reste à 907 200 unités et le manque prévisionnel de mai reste identique. En janvier, l’essai déplace le pic de 259 200 unités sans le réduire. La protection explique une part du regroupement. Modifier sa règle n’est pas justifié par ces deux cas.

## Gien · 042342, puis 268967

Le 23 mars, le MRP industriel classe **19,75 millions d’unités de 042342 en stock courant**, sur 21,25 millions au relevé. Les mouvements hebdomadaires concordent avec ces stocks. Cela soutient une libération plus précoce que celle du rejeu. Il manque les dates et statuts qualité par lot, ainsi que l’affectation à l’ordre de fabrication. En aval, le gain net de 31 986 PF à Muret la semaine du 24 mars ne révèle ni les réceptions brutes ni les départs clients.

Le lot simulé de **107 800 unités** part de Gien le 28 mars, entre à Muret le 30 et devient utilisable le 18 avril. Lors de la revue du 30 mars, Muret dispose déjà de **697 655 unités utilisables**. Retarder d’une semaine la date ferme du lot entier laisse le plan inchangé. À quantité physique égale, si seulement 53 900 unités ont une date ferme, le transfert proposé avance du **31 au 20 mai**, le lancement du **11 au 4 juin**, et la fabrication proposée sur quatre semaines passe de **107 800 à 215 600 unités**. La revue du 13 avril confirme une hausse d’un lot, de 323 400 à 431 200 unités. Dans l’essai, le reliquat reste sous contrôle. Une libération partielle industrielle reste à documenter.

## Effets à Muret et décisions

| Retard des réceptions déjà fermes | 268091 · Avène | 268967 · Gien |
| --- | ---: | ---: |
| Clôtures comparables avec au moins une réception décalée | 21 sur 24 | 4 sur 20 |
| Clôtures avec manque prévisionnel supplémentaire à +7 jours | 10 sur 21 | 0 sur 4 |
| Clôtures avec manque prévisionnel supplémentaire à +14 jours | 11 sur 21 | 0 sur 4 |
| Dates ou quantités proposées modifiées, dépôt ou usine | 0 | 0 |

Au 28 avril, le manque prévisionnel supplémentaire atteint **214 492** unités à +7 jours et **348 162** à +14 jours. Ces chiffres sont des écarts maximums jour par jour avec le témoin. Les connaître à la clôture ne suffit pas à changer le plan. Un essai de stress décale aussi les mêmes réceptions au-delà du premier jour où un nouvel ordre hors gel pourrait devenir utilisable à Muret. Les propositions restent identiques. L’essai utilise le gel de quatre semaines à Avène et de huit semaines à Gien, et la projection conditionnelle des engagements d’usine avec transport et contrôle.

Évaluée après coup avec la demande historique sur deux calendriers, la pénurie projetée n’augmente sur aucune clôture comparable dans les essais de +7 et +14 jours. Elle augmente sur deux ou trois clôtures Avène selon le calendrier dans l’essai de stress. Ce calcul mesure un bilan cumulatif avec les besoins de service. Les expéditions et livraisons industrielles par lot manquent pour mesurer le service réel. Deux clôtures Gien, les 6 avril et 4 mai, sont écartées de la comparaison complète car le plan usine local ne reproduit pas l’archive.

**Décision.** La référence est conservée. Le calcul doit continuer à réserver une quantité ferme une seule fois, tout en distinguant le besoin non couvert à temps du besoin sans engagement. Un cas élémentaire vérifie cette distinction dans le moteur. Pour expliquer davantage les dates réelles, la priorité est de rapprocher les engagements, les réceptions et les libérations qualité datées, d’abord sur ces deux épisodes. Un essai de rattrapage ne pourra déplacer une réception existante ou proposer une alternative que si sa disponibilité est démontrée. Son effet se mesurera sur le stock total de la chaîne, le manque à échéance et les départs, en gardant la demande prévisionnelle comme entrée du plan.

Les calculs locaux n’ont relancé aucune simulation native. Ils ont été contrôlés par des oracles indépendants de bilan, de calcul des plans et de lecture des sources. La mémoire de certains sous-essais n’a pas été instrumentée. Les périmètres exacts et les empreintes figurent dans le manifeste.
