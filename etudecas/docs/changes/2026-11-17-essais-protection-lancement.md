# Protection des composants et admission des lancements

Étude commencée le 17 novembre et terminée le 18 novembre 2026, sur
152 jours à partir du 1er janvier 2025.
Référence `coherent-MRP-20261014` conservée ; code de départ
`08dad8b19d809b09e44616d12350f7649e774868`. Les deux nouvelles options sont
désactivées par défaut. Les comparaisons précédentes restent disponibles.

## Ce qui est testé

Deux comparaisons séparées, avec demande, sécurité, nomenclature, stocks
initiaux et horizons figés inchangés : quatre semaines à 1810, huit à 1430.

| Comparaison | Témoin | Seule intervention |
|---|---|---|
| Protection | Calendrier initial A de l'étude précédente | Réserver les composants utilisables encore nécessaires aux lots physiquement engagés, avant les consommations des autres usages. |
| Lancement | Calendrier expérimental lundi–vendredi B | Autoriser un nouveau lot seulement si les composants et la capacité connus permettent de le terminer selon le calendrier projeté. |

Le deuxième témoin diffère donc du premier : on compare chaque variante à
son propre témoin. Les variantes ne sont pas combinées. La cadence de
7 700 unités/jour à 1430 reste une hypothèse, sans fermeture ajoutée pour les
jours fériés. Aucun réglage par date ou référence pour rejoindre une courbe.

## Protection : une interruption évitée, avec un coût pour les autres usages

Pour 268967, le premier lot de 107 800 unités se termine physiquement le
**12 mai au lieu du 22 mai**. La protection de 464 633 unités du composant
042342, le 11 mai, empêche un prélèvement concurrent qui interrompait ce lot.
La réservation n'est pas une consommation et n'utilise pas de stock sous contrôle.

Sur les 152 jours, le travail exécuté passe de 184 800 à **192 500 unités**,
mais la quantité terminée reste **107 800** : les 7 700 unités supplémentaires
sont encore en cours. Le stock physique final de Muret et les livraisons
clients sont identiques. Finir un lot plus tôt ne garantit donc pas ici un
gain de service au client.

La dette concurrente de 042342 augmente temporairement de 464 633 unités
pendant sept jours, soit **3 252 431 unités-jours d'attente supplémentaires**.
Elle est conservée, puis soldée ; l'attente finale reste nulle. Ce chiffre
mesure une quantité multipliée par son attente, pas un nombre de clients ni
un retard contractuel.

Attention : les besoins des autres usages sont reconstruits par différence
avec les mouvements observés. Leur total dépend donc de la consommation de
notre production : il passe de 137 692 094 à 137 227 461 unités pour ce
composant. La comparaison n'est pas à demande concurrente fixe. La dette
déjà créée est bien reportée ; cela ne prouve pas une baisse industrielle
des besoins. Ce mécanisme reste un **diagnostic historique**.

## Lancement selon les disponibilités datées

**Règle rejetée en l'état : elle introduit un blocage de priorité.**
Pour 268091, aucun nouveau lot ne démarre : 1 152 000 unités terminées en
moins. Les ordres initiaux continuent, donnant 1 945 715 unités au total,
contre 3 097 715 pour son témoin. Les stocks initiaux et ces ordres protègent
encore les livraisons clients sur la fenêtre ; cette absence de perte client
ne valide pas le blocage.

Le 24 février, l'ordre en tête demande 28 800 unités. Le contrôle attribue
d'abord 201 600 des 203 550 unités de capacité aux six autres ordres figés
du même jour. Il ne reste que 1 950 unités ; l'ordre en tête est refusé.
Il reste ensuite en tête et subit 98 refus jusqu'à la fin du calcul. La
capacité n'est pas arbitrée selon une priorité commune : c'est un défaut
de l'admission essayée, pas une panne industrielle.

Pour 268967, les quatre lots terminés restent identiques, soit 431 200
unités. **Tous passent par le chemin natif de substitution non projetable**,
sans autorisation positive du nouveau contrôle. Les 61 600 unités du lot
suivant ne sont plus engagées. Aucune continuité n'est donc validée par cette
variante. Les 106 refus pour conflit de capacité et les cas non projetables
sont tracés dans la
[revue des décisions](../../artifacts/testing/protection_lancement_20261117/validator/continuity_decisions_review.json).

Un [petit cas reproductible](../../artifacts/testing/protection_lancement_20261117/priority_liveness_probe.json)
isole ce défaut : avec deux lots de huit unités et une capacité de dix par
jour, chacun est refusé lorsque l'autre est prioritaire dans sa projection.
Un lot aujourd'hui puis l'autre demain est pourtant réalisable. Le second
subit un jour de retard physique explicite ; sa date figée n'est pas effacée.

L'examen préalable des huit composants et des engagements change déjà le
diagnostic : le lancement B décalé du 28 avril au 1er mai, acceptable dans le
petit cas à un composant, rencontre une autre réservation de capacité. Il
ne faut pas annoncer ce gain comme acquis. Le petit cas C reste admissible
avec les hypothèses examinées ; il n'est pas une cinquième simulation native.

Les réceptions utilisables aux jours 128 et 127 étaient présentes dans les
états connus du simulateur aux jours 89 et 88. Cela ne fournit pas la date
de création d'un ordre industriel. Elles peuvent informer ces lancements
tardifs, mais pas justifier rétrospectivement le gel des ordres aux jours 62
et 51. L'option conserve les dates et quantités figées : un refus retarde
l'exécution physique et reste visible dans les traces.

## Écarts au réel sur les mêmes observations

| Produit et critère, en unités | Protection : témoin → essai | Admission : témoin → essai |
|---|---:|---:|
| 268967 : erreur hebdomadaire moyenne | 26 585 → 26 585 | 29 320 → 31 979 |
| 268967 : erreur moyenne du stock de Muret | 74 336 → 69 436 | 82 525 → 82 525 |
| 268091 : erreur hebdomadaire moyenne | 82 128 → 82 128 | 82 128 → 64 376 |
| 268091 : erreur moyenne du stock de Muret | 292 145 → 292 145 | 292 145 → 93 986 |

Une erreur plus faible est préférable, mais **le rapprochement de 268091
obtenu en bloquant sa file ne valide pas la règle**. Son écart cumulé au
réel passe de +688 615 à −463 385 unités sur les semaines documentées.
Pour 268967, la protection réduit l'erreur de stock d'environ 6,6 %, sans
améliorer l'erreur hebdomadaire ; l'admission dégrade cette dernière d'environ
9,1 %. Les semaines non renseignées empêchent d'évaluer toute la trajectoire.

Le sous-total connu d'immobilisation du réseau passe de 677 358,57 à
677 348,47 avec la protection, et de 679 081,40 à 682 107,44 avec
l'admission. **Les stocks de produits finis à Muret ne sont pas valorisés
dans ce sous-total** : il ne mesure ni tout le stockage ni le coût industriel
global. La protection ajoute notamment 1 078 000 unités-jours de stock
physique à Muret pour 268967, malgré ce petit recul du sous-total connu.

Les [courbes et chiffres](../../resultats/protection_lancement_20261117.html)
présentent les deux comparaisons ; les
[valeurs hebdomadaires](../../artifacts/testing/protection_lancement_20261117/comparison/weekly_comparison.csv)
restent consultables.

## Ce que les données industrielles ne permettent toujours pas d'identifier

Les cinq classeurs examinés n'apportent ni heures machine allouées, ni dates
physiques de début/fin, ni identifiant reliant un ordre de fabrication à un
retrait d'étuis. `Extract_En_cours.xlsx` ne contient pas d'ordre pour 268967.

Du 31 mars au 27 avril, les retraits documentés représentent 171 000 unités,
contre 154 000 possibles sous l'hypothèse de cinq jours à 7 700 unités/jour.
Un simple déplacement des retraits à l'intérieur de ce bloc ne suffit pas.
Cela ne permet pas de choisir entre capacité/calendrier différents et
décalage de comptabilisation. Les bilans de stock vérifiés ferment, mais
n'identifient pas les entrées et sorties brutes.

La production observée reste **estimée par les retraits d'étuis**. Les
comparaisons utilisent les mêmes semaines documentées : 13 pour 268967,
21 pour 268091, et 22 photographies de stock par produit. Les semaines
inconnues ne deviennent pas des zéros. Les ratios de formats confirmés ne
sont pas modifiés.

## Implémentation, preuves et limites

- `--active-batch-material-protection-policy engaged_remaining_v1` : uniquement
  les lots natifs déjà engagés et incomplets ; priorité contre les autres
  usages de composants, pas contre tous les consommateurs du réseau. Les
  ordres initiaux de conditionnement suivent leur mécanisme distinct.
- `--production-material-launch-policy known_dated_continuity_v1` : un lot
  physique, composants et capacité connus ; réservations concurrentes
  conservatrices. Si le cas n'est pas projetable, le chemin natif est conservé
  avec un motif explicite, sans promesse de continuité.
- Les décisions utilisent des informations présentes dans l'état courant,
  pas les incidents futurs ni les observations futures. Les deux généalogies
  restent conservées. Les unités physiques sont entières.

Les [règles détaillées](../REGLES_MRP.md), le
[protocole](../../artifacts/testing/protection_lancement_20261117/protocol.json)
et son [amendement avant calcul](../../artifacts/testing/protection_lancement_20261117/dated_launch_amendment.json)
précisent hypothèses, critères et budgets. Les contrôles techniques ne
certifient ni la causalité industrielle ni le meilleur ordonnancement possible.

Les 69 tests de calcul sélectionnés sont passés, sans cas ignoré. Les quatre
simulations natives sont terminées et qualifiées ; les deux témoins reproduisent
chacun leurs 57 CSV antérieurs à l'identique. La contre-revue des quatre
scénarios compte 402 312 contrôles et celle des métriques 5 147, sans erreur.
Le [manifeste final](../../artifacts/testing/protection_lancement_20261117/final_manifest.json)
relie les preuves, les empreintes, les budgets et les limites.

Les lectures préliminaires invalidées restent conservées : un lecteur
confondait fin physique et champ de disponibilité vide ; une autre vérification
refusait des écarts numériques de masse inférieurs à 4 × 10⁻¹¹. Le lecteur
final distingue les événements et borne seulement le bruit des quantités
continues ; **aucune tolérance n'est appliquée aux unités physiques entières**.
Ces preuves préliminaires ne comptent pas comme réussies.

Le contrôle documentaire global reste refusé sur cinq domaines générés déjà
périmés. Le contrôle final exécuté couvre environnement, tests ciblés et quatre
qualifications ; il ne prétend pas valider ce registre global. Aucun test
d'altération volontaire de fichiers, aucune suite globale ni contrôle navigateur
n'a été exécuté. Le HTML est vérifié statiquement et son image est relue.

**Décision : aucune variante promue.** La protection est un mécanisme utile
pour éviter une interruption locale, à confronter aux priorités industrielles
des usages concurrents. L'admission actuelle est conservée uniquement pour
reproduire l'essai refusé. La prochaine correction doit donner une priorité
commune aux ordres, préserver leur dette et expliciter les retards physiques,
puis réussir le petit cas de non-blocage avant un nouvel essai natif. La capacité
réelle et les dates des ordres restent des données à obtenir ; pas de réglage
arbitraire pour rejoindre les pics.
