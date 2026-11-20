# Entrées de simulation et API HTTP locale

Les entrées décrivent une hypothèse de simulation : multiplicateurs de stock,
capacité, demande, délai ou fiabilité, graine aléatoire et durée en jours.
Leur validité technique ne prouve ni leur plausibilité métier ni la validité
scientifique du résultat. Un multiplicateur de 1 conserve le paramètre de base ;
0 est accepté par le parseur, mais le moteur peut appliquer ses propres planchers.

### Option expérimentale : réduction des ordres figés non lancés

`--production-frozen-reduction-policy unstarted_whole_lot_reduction_v1`
teste une exception au gel strict, avec le carnet figé et le calendrier de
lancement sans capacité modélisée. Le défaut reste le gel des dates et quantités.
L'autorisation industrielle de cette exception n'est pas confirmée.

À la clôture du lundi, un lot entier simulé encore non lancé peut être annulé
si le recalcul conserve les besoins des PF et leur protection, sans dégrader
leur couverture datée ni celle des demandes externes. Le gel s'applique aux
fabrications ; les achats de composants suivent leurs propres délais et règles.
Les ordres initiaux et les fabrications déjà engagées restent intangibles.
L'identité, la quantité et la date d'origine restent dans le journal. La
réception prévue, les besoins de composants et la réservation de travail sont
retirés ensemble ; aucune matière ni réception physique n'est créée ou annulée.
Un remplacement ultérieur reste une proposition hors de la période figée de
28 ou 56 jours, avec une disponibilité projetée, pas une promesse ferme.

Le rapprochement industriel peut remplacer des identifiants de besoins et
réaffecter un composant à d'autres usages. Les versions, fenêtres, unités et
quantités sources doivent alors rester traçables. Les compléments prévisionnels
normalisés sur des semaines futures peuvent être révisés ; ils ne constituent
pas des commandes clients fermes. Les autres besoins déclarés et les lots
conservés gardent leur protection datée. Le contrôle utilise un seul stock et
les réceptions et propositions déjà présentes : aucun achat supplémentaire
n'est créé pour le faire réussir. Toute quantité prévisionnelle supplémentaire
doit être couverte à sa date. La sécurité dynamique suit les besoins révisés,
avec les mêmes paramètres source ; les quantités fixes restent protégées.
L'anticipation liée aux délais de sécurité est vérifiée séparément, sans
l'ajouter une deuxième fois à la consommation physique.

Lorsque la politique existante arrondit les achats nets au kilogramme le plus
proche, un reliquat strictement inférieur à 0,5 kg peut subsister dans la
sécurité dynamique prévisionnelle. Le contrôle conserve explicitement ce
reliquat, avec le même quantum dans les entrées et les deux plans. Il ne crée
aucune matière : les besoins datés, les quantités fixes de sécurité et le stock
physique restent soumis à leurs contrôles stricts. Cette convention ne
s'applique pas aux unités physiques entières.

À la fin de l'horizon prévisionnel, la réserve de repli reste une quantité
calculée : maximum entre le plancher fixe et les besoins de la fenêtre initiale
connue, selon les jours source. Elle est recalculée après retrait d'un lot
uniquement si cette formule et ses champs d'audit sont vérifiés. La fenêtre
future incomplète reste déclarée inconnue ; elle n'est pas remplie de zéros.

L'export `data/frozen_production_reduction.json` explique chaque décision et
ses contrôles datés. Les gains de stock ou de production doivent être comparés
aux reports, au service et à l'autre PF ; cette option ne définit ni une durée
de fabrication ni une capacité machine industrielle.

### Option expérimentale : lancements PF sans débit machine modélisé

Le moteur CLI accepte le couple explicite
`--production-capacity-planning-policy unconstrained_lot_calendar_v1` et
`--production-material-launch-policy known_material_kit_unconstrained_v1`.
Il exige le carnet figé `industrial_frozen_order_book_v1`, les autres contrats
du programme daté et un horizon d'au plus 365 jours. Ce choix ne modifie pas
le graphe de référence : le scénario doit déclarer une capacité PF non modélisée
(`capacity.max_rate = 0`). Dans cette convention du moteur, zéro signifie
**absence de plafond**, pas usine arrêtée. Les fermetures sont déclarées par
le calendrier. Un quota hebdomadaire positif reste applicable ; le scénario
sans plafond de lancement le désactive explicitement avec
`lot_execution.max_lots_per_week = 0`.

Le calcul conserve la prévision consommée par la demande réelle connue, les
besoins nets, les quantités de lot et les ordres engagés. Il place les nouveaux
lancements sur les jours ouverts en respectant les horizons figés de 28 jours
à 1810 et 56 jours à 1430. Plusieurs ordres déjà dus peuvent être exécutés le
même jour, chacun avec son identité et son contrôle matière. Le kit complet
de chaque ordre est vérifié sur le stock utilisable courant, avec les arrondis
par lot physique ; une réception future ne finance pas ce lancement.

Les ordres initiaux de conditionnement des mêmes PF acceptent également cette
déclaration explicite de débit nul. Ils conservent leur ordre de priorité, leurs
quantités, leurs besoins d'emballage et leurs dates sources de disponibilité.
Leurs matières déjà incorporées restent du travail en cours initial : elles
ne sont pas consommées une seconde fois. Une fermeture impose toujours zéro
travail, y compris sur ces ordres initiaux.

Le mode conserve la résolution journalière existante : un lot intégralement
approvisionné peut être terminé dans la journée. Cela ne constitue ni une durée
physique mesurée ni une simulation de lots en cours parallèles. Les marges de
planification et les délais de contrôle/disponibilité restent distincts. Les
sorties amont disposant d'un débit positif conservent leur calcul capacitaire.
L'option n'est pas activée par défaut et n'est pas exposée par le raccourci CLI
de la référence nominale ; elle s'utilise avec un graphe et des arguments moteur
préparés explicitement.

#### Durée d'exécution d'un lot engagé

`--engaged-lot-work-days "IDENTIFIANT_ORDRE,JOURS"` permet d'étudier un
seul ordre figé dans ce mode. Il faut un calendrier ouvré déclaré, un lot
physique en unités entières et les prélèvements cumulés du lot
(`--production-component-issue-policy batch_cumulative_v1`). La durée doit
être entière et laisser au moins une unité de travail dans chaque tranche.
Une fermeture ou un manque de matière peut reporter du travail au-delà de
la durée saisie. Le kit complet reste exigé au lancement.

L'ordre conserve ses dates au carnet jusqu'au premier travail. Le moteur
prélève alors les composants au fur et à mesure, suit l'encours et projette
une seule réception MRP à partir du travail restant. La sortie physique du
lot entier intervient à la fin du travail, puis le transport et le contrôle
qualité suivent leurs règles propres. La durée est une hypothèse de scénario.
Ce mode utilise l'unique encours du couple usine–produit et refuse le
chevauchement si un autre ordre dû de ce couple doit attendre derrière lui.

#### Report de l’autorisation de travail

`--frozen-lot-not-before "IDENTIFIANT_ORDRE,JOUR"` teste une date minimale
d’autorisation pour un seul ordre figé simulé dans le mode sans débit
machine modélisé. `JOUR` est l’indice entier du jour dans le calcul.
Le report devient connu le jour de lancement inscrit au carnet.
Il conserve les dates du carnet, la quantité, les besoins matière et les
règles de protection. La réception ferme projetée se décale à partir de
l’annonce, avec la marge calendaire du carnet. Le calendrier et la
disponibilité des composants s’appliquent à la nouvelle autorisation.
Le journal des ordres figés indique les journées et le motif de report.

## 1. Contrat du parseur Python/JSON

`request_from_dict` exige exactement une source : `input_graph` ou `input_path`.
Les champs inconnus sont refusés. Les booléens doivent être de vrais booléens :
`false` en JSON ou `False` en Python ; la chaîne `"false"` est refusée.
Les jours et graines doivent être des entiers non négatifs ; `true`, `1.5` et
`"2"` ne sont pas convertis en entiers. Pour l'API Python, zéro jour conserve
la convention historique de durée définie dans le graphe.

Les multiplicateurs doivent être des nombres finis et non négatifs. Les chaînes
numériques, booléens, `NaN`, infinis et valeurs négatives sont refusés. Les flags
de scénario doivent être des booléens. Les dictionnaires et listes d'arguments
sont contrôlés ; une structure incorrecte ne devient plus silencieusement vide.

Le contrat Python de confiance conserve `run_script`, `output_dir`, `run_id` et
`engine_args`. Il ne constitue pas une frontière d'accès aux fichiers. Les objets
`SimulationRequest` construits directement restent une interface interne de
confiance ; ils ne passent pas automatiquement par le parseur de dictionnaire.

## 2. Contrat HTTP plus restreint

`request_from_http` refuse un moteur, dossier de sortie, identifiant de run ou
argument moteur libre fourni par le client. Il impose le moteur canonique,
un nouvel identifiant aléatoire et un sous-dossier de la racine de sortie du
serveur. `engine_args: []` reste accepté pour les anciens générateurs de payload.
`skip_map` et `skip_plots` peuvent être absents ou `true`, jamais `false`.

Les fichiers d'entrée sont résolus sous `--input-root` (le dépôt par défaut).
Un chemin absolu n'est accepté que s'il reste dans cette racine après résolution,
y compris à travers un lien symbolique. Les graphes/politiques doivent avoir
l'extension `.json`, les contrôles/perturbations `.csv`. Ils doivent exister.
Le graphe chargé est transmis en mémoire à l'API Python ; les fichiers de contrôle
restent lus par le moteur. Il n'y a pas de protection contre un acteur local
capable de modifier ces fichiers entre leur validation et leur utilisation.

Le graphe est contrôlé et le scénario demandé doit exister. Le client doit fournir
un horizon explicite de **1 à 3 660 jours** par défaut ; `--max-days` règle la limite.
L'HTTP refuse zéro pour empêcher une durée implicite non bornée. Un planning de
contrôle et une politique de feedback ne peuvent pas être combinés.

## 3. Accès et limites d'exécution

Le serveur écoute uniquement `127.0.0.1` ou `localhost` en IPv4. Chaque démarrage
génère un jeton, affiché dans le terminal local. Les appels `POST /simulate`
doivent le transmettre dans `X-Etudecas-Token`. Le jeton n'apparaît pas dans
`GET /health`, les URL ou les résultats. L'en-tête `Host` doit désigner le serveur
local et son port effectif.

Aucune origine navigateur n'est autorisée par défaut. Une origine exacte peut
être ajoutée avec `--allow-origin http://localhost:8000`. L'ouverture d'un HTML
par `file://` utilise souvent l'origine `null` : elle exige l'option explicite
`--allow-origin null` **et** le jeton. Il n'y a plus de CORS `*`. Les clients Python
sans en-tête `Origin` doivent eux aussi fournir le jeton.

Le corps doit être un objet JSON, annoncé par un seul `Content-Length`, sans
`Transfer-Encoding`. Limites par défaut : **4 Mio**, **10 secondes par opération
de lecture socket**, **une simulation à la fois**, **300 secondes pour le
sous-processus moteur**. La limite de lecture n'est pas une échéance globale
contre un client qui envoie lentement des octets ; le serveur reste un outil local.
Le nombre de connexions HTTP, la mémoire et la taille des sorties ne sont pas
bornés par cette politique. Ce serveur n'est pas conçu pour une exposition réseau.

Le moteur lancé directement est tué et attendu par `subprocess.run` si son délai
expire. Ce délai ne couvre pas le prétraitement Python, et ce mécanisme ne promet
pas la terminaison d'éventuels descendants créés par le moteur. Un dossier partiel
peut subsister : il ne vaut pas résultat réussi. Le créneau d'exécution est libéré
après succès ou erreur. Le lanceur batch historique n'est pas modifié.

| Statut HTTP | Sens |
| --- | --- |
| 400 | JSON, champs ou données invalides |
| 401 | Jeton absent ou incorrect |
| 403 | Origine ou hôte refusé |
| 408 | Délai de lecture du corps dépassé |
| 413 | Corps vide ou trop volumineux |
| 415 | Type de contenu autre que JSON |
| 429 | Une simulation occupe déjà le créneau |
| 500 | Échec d'exécution interne |
| 504 | Délai du sous-processus moteur dépassé |

## 4. Utilisation et migration

Depuis la racine du dépôt :

```powershell
python -m etudecas.simulation.engine.server --port 8765 --execution-timeout 300
```

Exemple de client Python, après démarrage du serveur (il lance réellement une
simulation ; adapter l'horizon et le graphe au besoin) :

```python
import getpass
import json
from urllib.request import Request, urlopen

token = getpass.getpass("Jeton affiché par le serveur : ")
payload = {
    "input_path": "etudecas/simulation_prep/result/supply_graph_poc_simulation_ready.json",
    "scenario_id": "scn:BASE",
    "days": 7,
    "output_profile": "minimal",
    "common_random_numbers": False,
}
request = Request("http://127.0.0.1:8765/simulate",
                  data=json.dumps(payload).encode("utf-8"),
                  headers={"Content-Type": "application/json", "X-Etudecas-Token": token})
with urlopen(request, timeout=320) as response:
    result = json.load(response)
print(result["result"]["output_dir"])
```

Les anciens clients HTTP doivent supprimer les options internes et ajouter le
jeton ; leur simple succès avec l'ancien serveur ne prouve pas leur compatibilité.
`launch_interactive_map` ouvre toujours le HTML et démarre le serveur, mais ne
réécrit pas une carte existante et n'y injecte pas le jeton. L'affichage autonome
des résultats pré-calculés reste indépendant des appels HTTP. Les clients live
doivent être adaptés explicitement ; l'exemple Python fournit une voie utilisable.

## 5. Contrat du graphe et preuves

Le validateur retourne des erreurs structurées au lieu d'un `AttributeError`
pour les lignes mal formées d'articles, nœuds, arcs, scénarios, stocks, processus
et demandes journalières. Il ne modifie pas le graphe. Les champs numériques
déjà contrôlés (stocks initiaux, ratios d'entrée, jours et quantités de demande)
doivent désormais être finis ; les booléens n'y comptent pas comme des nombres.
Les chaînes numériques finies restent compatibles avec le contrat historique
du graphe. Tous les champs numériques du moteur ne sont pas contrôlés par ce
validateur ; ce n'est pas un audit de conservation physique ni de cohérence BOM.

Les tests couvrent les entrées rejetées, le parcours HTTP avec un faux moteur
local, un vrai sous-processus dépassant son délai, la non-écriture avant
validation et la conservation du contrat Python interne. Le registre
`simulation_input.json` relie ces règles aux implémentations et aux tests ; les
changements déclenchent une relecture via `check-all` et `watch-all`.

## Corrections du réexamen du 18 septembre 2026

Les requêtes Python natives repassent par le même contrôle de types que JSON.
Le moteur CLI et l'API vérifient le graphe avant exécution. Stocks négatifs,
articles de stock/BOM absents et arcs sans extrémités sont refusés. Un scénario
inconnu ne devient plus le premier scénario. Les facteurs de sensibilité
inconnus ou non finis sont refusés avant matérialisation ; les facteurs de ce
chemin multiplicatif doivent être strictement positifs.

Voir [les vérifications d'exécution](EXECUTION_VERIFICATION.md) pour les limites
et la distinction entre contrat d'entrée, conservation et validation métier.

## Profil commun de besoins concurrents pour un essai historique

L'adaptateur `etudecas.simulation.current_reference` accepte le mode expérimental
`--scan3-mode fixed_residual_replay` avec `--replay-profile-csv CHEMIN`. Le profil
est obligatoire dans ce mode et interdit dans les autres. Le mode nominal reste
`legacy_residual`. Ce parcours est limité à la première année documentée ; il
ne constitue pas une règle de prévision prospective.

Le CSV conserve les **quantités demandées** des résidus d'un témoin identifié,
jamais les anciennes consommations ni les anciennes dettes. Chaque budget clos
doit figurer exactement une fois, y compris avec une demande explicitement
nulle. Identité article/site, unité, fenêtre, clôture, identifiant du besoin et
quantité source doivent correspondre au graphe. Les quantités en unités
physiques restent entières ; une ligne manquante n'est pas un zéro.

Les quantités deviennent accessibles à la phase de clôture **après la
production propre du jour**. Avant cette phase, l'aperçu indique seulement
qu'une clôture reste à traiter ; il n'expose pas sa quantité. Les prévisions
et calendriers d'observations du graphe ne sont pas remplacés. Les demandes
non servies restent dans le registre natif des besoins en attente.

Le manifeste lie le profil à ses octets par SHA-256. Son statut est
`conditional_scenario_not_industrial_observation` : un résidu extrait d'un
témoin simulé n'est pas une observation industrielle indépendante. Les exports
conservent séparément le retrait source, la consommation propre de l'essai,
le besoin fixé et leur écart signé, sans forcer ce dernier à zéro. Voir les
[contrôles associés](TEST_VALIDATION.md#profil-commun-de-besoins-concurrents).
