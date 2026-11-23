# Gien, Avène et Muret · essais de correction

[Preuves et limites](../../artifacts/testing/solutions_mrp_20261123/final_manifest.json) ·
[Courbes des retards à Muret](../../resultats/chainage_besoins_lots_20261123.html)

## Gien · tenir compte du stock déjà utilisable

Le témoin reçoit 23 millions d’unités de 042342 au rejeu du 24 mars et redémarre le délai complet de contrôle pour le volume entier. La version du MRP du 23 mars indique 19,75 millions en stock courant. Même en supposant que les 6,75 millions de stock d’ouverture étaient tous utilisables, au moins **13 millions** du courant proviendraient de la réception. Le rejeu de 96 jours teste cette lecture à partir du jour de connaissance. Il garde 10 millions sous contrôle et ne modifie aucune quantité reçue. La même règle calcule zéro à libérer plus tôt pour la réception de février.

Le lot de **107 800 PF** est terminé et expédié le **28 mars**, puis reçu à Muret le 30. Le témoin s’arrête à 74 362 unités travaillées et n’achève aucun lot avant la fin de l’essai.

| Comparaison au réel | Témoin | Libération partielle | Dates communes |
| --- | ---: | ---: | ---: |
| Retraits d’étuis à Gien, estimation du travail de fabrication | 43,09 % | **13,85 %** | 7 semaines |
| Stock physique du 042342 à Gien | 14,65 % | **11,21 %** | 14 relevés |
| Stock physique du 268967 à Muret | 4,02 % | **3,18 %** | 14 relevés |

Pour chaque ligne, l’erreur est la somme des écarts absolus divisée par la somme observée. Les deux scénarios livrent les mêmes volumes simulés, 435 397 pour le 268967 et 902 858 pour le 268091, aux mêmes dates. Les retraits d’étuis renseignent le travail réalisé. L’écart des dates de fin d’OF estimées reste plus élevé.

La qualification standard refuse le découpage parce que son contrat attend un fragment par ordre et cellule source avec le délai de contrôle d’origine. Deux oracles séparés vérifient le bilan de chaque commande d’origine, les dates et la conservation du lot. Le résultat est retenu comme **rapprochement historique local**. Le statut qualité et le moment de libération exacts restent inconnus dans la source. [Détail du rejeu](../../artifacts/testing/solutions_mrp_20261123/gien/SYNTHESE.md) · [Manifeste de qualification](../../artifacts/testing/solutions_mrp_20261123/gien/qualification/qualify-e0980108effb4f0598f0f9c04d0c118a/manifest.json)

## Muret · prioriser une libération confirmée

Si Qualité confirme qu’un lot déjà présent peut retrouver sa date prévue, comparer la baisse du **nombre d’unités manquantes cumulé jour après jour**. Sur 44 clôtures et trois amplitudes de retard, cette règle sélectionne un lot utile pour **10 cas touchés sur 10 à +7 jours et 11 sur 11 à +14 jours** pour le 268091. Gien ne nécessite aucune action sur ces cas. Les lots encore en transit sont exclus. À deux jours ouvrés après la date prévue, le gain est plus faible et reste présent dans les mêmes cas. Le calendrier d’essai compte du lundi au vendredi.

| Manque prévisionnel maximal au 28 avril, en PF | Sans action | Date confirmée retrouvée | Date confirmée deux jours ouvrés plus tard |
| --- | ---: | ---: | ---: |
| Retard global de 7 jours | 214 492 | **70 492** | 70 492 |
| Retard global de 14 jours | 348 162 | **218 562** | 290 774 |

Le plus gros lot donne le même gain la plupart du temps. Au 28 avril à +14 jours, le calcul choisit un lot de 129 600 plutôt que 144 000. Le lot plus petit couvre mieux les jours de manque. Même en mobilisant tous les lots déjà présents, le scénario ne retrouve pas le témoin à cette clôture. Dans l’essai de stress plus long, le rétablissement d’un lot ramène à zéro les manques sur les trois clôtures touchées lorsqu’on réévalue le plan avec la demande historique. La demande réellement publiée n’a servi qu’à l’évaluation après coup, sous deux conventions de dates. Ce bilan ne mesure pas des livraisons industrielles. [Oracles](../../artifacts/testing/solutions_mrp_20261123/validator/muret_oracle.json) · [Évaluation historique](../../artifacts/testing/solutions_mrp_20261123/muret/historical_score.json)

## Avène · différencier la prévision et le plan de production

En mai, décaler quatre lots du 26 au 27 réduit le pic journalier de 345 600 à 201 600. Les deux jours appartiennent à la même semaine et conduisent à la même date prévue de disponibilité à Muret. L’écart aux échéances de transfert augmente de 134 602 unités. Aucun des reports testés ne fait progresser le profil hebdomadaire avec les garde-fous de l’usine et du dépôt.

Une prévision corrigée avec les quatre dernières semaines closes réduit son erreur sur le second semestre, de **107,33 à 77,34 %** pour le 268091 et de **158,68 à 67,19 %** pour le 268967. C’est un repère utile pour quantifier le biais. Dans le plan d’Avène du 28 avril, la correction complète fait toutefois apparaître jusqu’à 336 202 unités de besoin brut supplémentaire non couvert et 899 704 unités de déficit supplémentaire face à la sécurité d’origine. Maintenir la cible de sécurité d’origine dans le calcul ne suffit pas à conserver toute la couverture. [Oracle des plans et des prévisions](../../artifacts/testing/solutions_mrp_20261123/avene/independent_manifest.json)

L’essai suivant applique 25, 50, 75 ou 100 % de la correction, avec le même contrôle de la demande et de la sécurité à chaque date. Six des 44 clôtures font baisser le stock projeté, uniquement sur les nouveaux lots en contrôle. Le pic et le volume proposé sur les quatre semaines après le gel ne baissent dans aucun cas retenu. Le 28 avril, une correction à 25 % ramènerait le pic à 72 000 unités, avec 381 304 unités de déficit supplémentaire face à la protection. [Grille et oracle](../../artifacts/testing/solutions_mrp_20261123/avene/partial/final_manifest.json)

## Correctif livré

L’appel direct au calendrier de production sans plafond accepte désormais un plan qui ne crée aucun lot. Le test de régression reproduit le plantage avant correction, puis contrôle que le bilan garde les **80 unités fermes en retard** et ne crée aucun ordre supplémentaire. Quatre tests ciblés et un oracle indépendant couvrent aussi le gel et les plans avec de nouveaux ordres. Le parcours nominal de 14 jours a été exécuté et qualifié sur le code corrigé. Le rejeu Gien de 96 jours a été réalisé avant ce correctif. La vérification globale de la documentation est en échec depuis l’état de départ sur des références générées. Les liens de ce bilan ont été vérifiés séparément.
