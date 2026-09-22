# Entrées de simulation et API HTTP locale

Les entrées décrivent une hypothèse de simulation : multiplicateurs de stock,
capacité, demande, délai ou fiabilité, graine aléatoire et durée en jours.
Leur validité technique ne prouve ni leur plausibilité métier ni la validité
scientifique du résultat. Un multiplicateur de 1 conserve le paramètre de base ;
0 est accepté par le parseur, mais le moteur peut appliquer ses propres planchers.

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
