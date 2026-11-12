# Sensibilité : amplitudes et durée — 12 novembre 2026

L'extension est lancée par étapes. Les données industrielles et le bundle
`coherent-MRP-20261014` sont conservés. Les pilotes ont ensuite révélé un
défaut moteur de filiation après perte de transport, corrigé localement avant
de préparer une étude entièrement fraîche. Le statut effectif est dans les
résultats locaux ; un plan préparé n'est pas une étude terminée.

## Ce que la première campagne ne démontrait pas

`scv26_c362` s'est arrêtée après le nominal et 24 variantes de 362 jours,
uniquement aux facteurs ×0,5 et ×2. La hausse de la période de revue MRP
violait le contrat de livraison client quotidienne. L'étude échouée reste
inchangée : aucun réessai de son cas partiel et aucune suppression de garde.

Ses 25 cas terminés ont été recalculés indépendamment à partir des CSV :
quantités servies, révisions du programme et immobilisation connue concordent.
Le premier lecteur a refusé cinq écarts de coût calculés par soustraction
binaire : sa tolérance absolue de 10⁻¹² n'était pas adaptée à cette opération.
Ce refus est conservé. Un contrôle séparé fondé sur les erreurs d'arrondi
IEEE 754 explique ces écarts, sans changer les seuils d'effet ni leur classement.
L'index de réutilisation lie les reçus, entrées, CSV et sources des seuls cas
terminés ; il ne transforme pas la campagne interrompue en campagne validée.

## Ne pas confondre absence d'effet et amplitude insuffisante

Les 19 facteurs sont classés et leurs six projections d'entrée sont conservées :

- capacité et délai de l'approvisionnement externe : le parcours agrégé actif
  consomme d'autres capacités et délais ; augmenter ces multiplicateurs ne
  corrige pas l'absence de consommateur ;
- cible de couverture PF nulle : un multiplicateur conserve zéro ; revue
  inférieure à un jour et fiabilité supérieure à 100 % : bornes effectives ;
- sécurités : les 27 couples protégés par les sources restent protégés ;
- stocks fournisseurs : les 33 pools du nominal ne sont pas débités dans ce
  parcours agrégé ; leur variation peut modifier le coût, pas produire une
  pénurie par épuisement de ces pools ;
- gain et lissage : le lancement daté remplace la commande physique. Le lissage
  modifie encore une trace MPS ; les amplitudes extrêmes vérifient le couplage
  restant, sans déclarer le paramètre entièrement inutilisé ;
- coefficients monétaires : trois effets physiques ne sont pas attendus d'un
  simple changement de comptabilité. Le coût de transport reste contrôlé en
  raison du classement des liaisons et des éventuels arrondis.

## Essais déclarés avant exécution

Le premier pilote court a exécuté son témoin, puis refusé la capacité
fournisseur ×0,1 : le lot géré de 7 000 kg dépassait la capacité de
1 864,077670 kg/j. Ses résultats et son refus restent conservés ; 427
contrôles indépendants passent pour les 26 cas terminés, sans déclarer
ce pilote complet.

Le précontrôle commun exige, pour chaque lot géré, une capacité quotidienne
au moins égale au lot. Le maximum des rapports lot/capacité nominale vaut
environ 0,375520833334. La borne de calcul est vérifiée après l'arrondi du
CSV à six décimales : le couple contraignant atteint 7 000 kg/j pour
7 000 kg. Cette limite vient des politiques de lots candidates du modèle,
pas d'une capacité minimale industrielle confirmée. Aucun lot n'est réduit
et aucune exception article n'est ajoutée.

Un nouveau pilote, dans `feasible_revision/`, comprend un témoin de 21 jours,
une capacité fournisseur ×0,5 et une fiabilité des liaisons ×0,5.
La fiabilité porte sur toutes les
liaisons et représente une perte déterministe de quantité livrée : ce n'est
pas une fréquence de panne industrielle identifiée.

Après la lecture indépendante du pilote, le plan révisé prévoit au plus 32
nouveaux calculs de 362 jours et quatre calculs prospectifs conditionnels de
726 jours. Les facteurs fournisseur ×0,1 et ×0,01 sont remplacés par la borne
globale faisable, sans relancer le cas refusé.
Les capacités, demande, stocks de fabrication et fiabilité sont explorés
jusqu'à ×0,01 ou ×20 lorsque cela reste utile. Une direction est arrêtée si
ses trois premiers effets sont déjà observés ; aucun résultat non exécuté
n'est inventé. Seuils conservés : 0,1 point pour chaque taux et 1 % du coût
témoin, avec plancher d'une unité monétaire.

La prolongation n'est exécutée que si une réduction annuelle extrême de
capacité, de stock de fabrication ou de capacité fournisseur laisse le taux
de service inchangé.
Elle possède son propre témoin. Au-delà de 2025, reconduction saisonnière,
croissance et fermetures futures sont des hypothèses explicites du runtime.
Un contrôle des préfixes vérifie si la planification a déjà changé avant la
fin 2025 ; dans ce cas, l'écart ne peut pas être attribué à la seule durée.

Un seul calcul est exécuté à la fois. Budgets : 45 minutes pour le pilote,
32 heures pour l'extension, 20 Gio cumulés avec les anciens résultats,
10 Gio libres minimum et 4 Gio de mémoire de travail échantillonnée pour
l'arbre de processus possédé. Tout refus d'écriture ou de sécurité arrête
l'exécution concernée sans réessai. Les exports compacts restent conservés.

## Preuves et limites

Les scripts d'expérimentation, plans, registre et preuves sont sous
`etudecas/artifacts/testing/sensibilite_extension_20261112/` :

- `protocol.json`, `tickets.json`, `preparation/input_mapping.json` ;
- `preparation/pilot_plan.json` et `preparation/annual_plan.json` ;
- `validator_2ec46f6b9a37/reuse_index.json`, refus initial et contrôle numérique ;
- premier refus : `supervision/pilot/state.json` ; révision faisable :
  `feasible_revision/supervision/pilot/state.json`, puis
  `feasible_revision/supervision/annual/state.json` ;
- lectures indépendantes dans `validator_2ec46f6b9a37/study_*/`.

Le plan révisé est sous `feasible_revision/preparation/`. Le précontrôle des
lots et capacités est `feasible_revision/managed_capacity_preflight.json`.
Les scripts précédemment gelés sont copiés à l'identique pour cette révision,
avec leurs empreintes ; le premier protocole et ses preuves restent intacts.

## Correction révélée par le pilote de fiabilité

Le second pilote a terminé le nominal et la capacité fournisseur ×0,5, avec
les mêmes trois indicateurs à 21 jours. La fiabilité ×0,5 a ensuite échoué :
la réception interne portait la quantité survivante, mais ses parents portaient
encore toute la quantité expédiée. La garde de conservation était correcte.

La correction conserve les prélèvements, réservations et départs complets.
Seuls les parents de la réception et leurs contributions d'origine suivent
la quantité reçue. Exemple : 100 expédiées, 50 perdues, 50 reçues ; les
parents de 33 et 67 unités donnent 16 et 34 unités reçues. Les quantités
physiques restent entières, les attributions à des ordres pouvant rester
fractionnelles. Réception physique, stock retenu et libération restent distincts.
Le nominal sans perte conserve les structures d'origine. Aucun garde-fou
n'est assoupli. La convention filtrant un envoi total livré nul avant son
prélèvement reste inchangée.

Vérifications réellement exécutées sur le code corrigé : environnement,
23 cas pytest exacts en mémoire et 201 contrôles indépendants sur sept
oracles manuels, complétés par huit contrôles d'attributions fractionnelles.
L'intégration réelle a ensuite terminé ses trois simulations de 21 jours,
avec lecture indépendante réussie des trois mesures :

| Cas corrigé, 21 jours | Demande servie en quantité | Révisions du programme | Immobilisation connue |
| --- | ---: | ---: | ---: |
| Nominal | 85,5070 % | 28,2051 % | 66 811,7721 |
| Capacité fournisseur ×0,5 | 85,5070 % | 28,2051 % | 66 811,7721 |
| Fiabilité des liaisons ×0,5 | 80,0596 % | 55,4557 % | 66 878,2955 |

La fiabilité fait donc réagir nettement le service et les révisions. Le coût
varie d'environ 0,10 %, sous le seuil d'effet déclaré de 1 %. La capacité
fournisseur sans effet à 21 jours reste à départager sur l'année et à sa borne
faisable. Les écarts annuels ne sont pas anticipés.

Le nominal corrigé est comparé aux deux anciens témoins de 21 jours : graphes,
12 CSV et mesures identiques, avec 45 contrôles réussis. Le lecteur du pilote
frais réussit 76 contrôles d'agrégation, en plus des preuves propres aux trois
cas. Les preuves sont sous `post_transport_fix/` et dans le dossier du validateur.

Le contrôle natif ciblé de la perte réussit 21 vérifications supplémentaires.
Pour 693055 simulé de Gaillac à Avène : 590 kg prélevés et expédiés au jour 7,
295 kg reçus physiquement au jour 14 et 295 kg de parents au lot reçu. Les
295 kg manquants sont une perte simulée. La quantité reçue reste retenue,
avec disponibilité prévue au jour 23, hors du pilote : cette libération
n'est pas observée. Le stock initial parent n'a pas d'origine de fabrication
identifiée ; aucune origine n'est inventée. Dans cet export,
`pulled_qty` représente le départ brut et `shipped_qty` la quantité survivante ;
la preuve du départ repose aussi sur les événements de lots.

La qualification générique a été effectivement relancée sur le nouveau témoin
et **refusée** : le profil compact n'exporte pas
`production_input_consumption_daily.csv`. Ce refus est conservé sous
`post_transport_fix/qualification/`. Les contrôles locaux ne qualifient pas
les bilans matière complets et ne lèvent aucune réserve antérieure F3/transferts.

Le changement du moteur invalide la réutilisation conservatrice des anciens
résultats comme résultats du code corrigé. Ils restent historiques. Le nouveau
plan contient donc trois calculs de pilote entièrement frais, puis au plus
41 calculs de 362 jours et quatre prolongements conditionnels de 726 jours,
avec leurs propres témoins. Le plafond de stockage est révisé à 32 Gio cumulés
pour conserver les anciens essais tout en recalculant ces variantes ; un
plafond de 20 Gio risquerait de tronquer cette nouvelle étude. Les autres
budgets restent un seul calcul, 4 Gio de mémoire échantillonnée, 10 Gio libres,
45 minutes pour le pilote et 32 heures pour l'annuel.

Contrat de code corrigé :
`236ab838600cdfaa1e1c1f8c01a3b6a175f0991555dec434bcc6c5cc00293946`.
Plans et suivi actuels : `post_transport_fix/preparation/`,
`post_transport_fix/supervision/pilot/state.json`, puis
`post_transport_fix/supervision/annual/state.json`. Les plans antérieurs à
36 calculs ne sont pas exécutés comme s'ils utilisaient le code corrigé.

Les trois mesures restent la part de demande servie en quantité, rattrapages
inclus ; les révisions du programme prévisionnel de fabrication simulé ; et
le sous-total connu du capital immobilisé. Elles ne mesurent respectivement
ni la ponctualité, ni les révisions d'OF industriels, ni le coût complet de
l'entrepôt. Les 12 couples sans valorisation fiable restent exclus.

Les bilans matière complets ne sont pas qualifiés par les exports compacts.
Les réserves antérieures F3 et transferts ne sont ni réévaluées ni levées.
Aucune nouvelle référence ou calibration industrielle n'est promue.
