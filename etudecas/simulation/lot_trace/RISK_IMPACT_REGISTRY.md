# Registre d'impact risque → lots → clients

Version du contrat : `risk-lot-impact-registry/1.0`.

Ce registre relie un incident simulé à son exposition physique sans confondre
trois affirmations différentes :

1. le moteur a appliqué un incident à une transaction d'expédition ;
2. la matière de cette transaction se retrouve dans des lots aval ;
3. l'incident a dégradé le service ou augmenté le coût par rapport à ce qui se
   serait produit sans incident.

Les points 1 et 2 sont traçables. Le point 3 exige une simulation contrefactuelle
appariée et n'est jamais déduit de la seule proximité temporelle.

## Données natives ajoutées au moteur

Les colonnes existantes sont conservées. Les nouvelles simulations ajoutent :

- dans `production_supplier_shipments_daily.csv` : `shipment_id`,
  `risk_decision_day`, `risk_event_ids`, `edge_id`, `purchase_cost` ;
- dans `production_lot_events.csv` et `production_lot_genealogy.csv` :
  `shipment_id`, `risk_decision_day`, `risk_event_ids`.

`shipment_id` suit la matière entre le prélèvement du lot fournisseur et le lot
réceptionné. `risk_decision_day` reste le jour où l'effet a été calculé, même si
la libération physique ou la réception a lieu plus tard.

## Niveaux de preuve

- `native_transaction` : les identifiants d'incident sont portés par la
  transaction. On peut dire que la transaction a été exposée dans le moteur.
- `scope_day_association` : ancien run rapproché sur fournisseur, destination,
  article et jour. Il s'agit d'une association reconstruite, pas d'un lien natif.
- `physical_genealogy` : propagation à travers des liens explicites de transport
  ou de transformation.
- `lineage_exposure_only_not_counterfactual_service_degradation` : de la matière
  exposée est arrivée dans un lot servi au client ; cela ne prouve pas une perte
  de service causée par l'incident.

## Tables produites

- `risk_impact_incidents.csv` : une ligne par incident, avec portée, nombre de
  mouvements/lots/clients exposés, quantités par unité et niveau de preuve.
- `risk_impact_exposure_bundles.csv` : une ligne par expédition exposée. C'est
  l'unité physique unique à sommer.
- `risk_impact_bundle_events.csv` : table de correspondance plusieurs-à-plusieurs
  entre incidents et expéditions.
- `risk_impact_entities.csv` : lots, campagnes et nœuds touchés avec quantité et
  part basse/haute.
- `risk_impact_edges.csv` : liens de transport, production et service constituant
  les chemins physiques.
- `risk_impact_client_service.csv` : quantités servies provenant de lots exposés,
  avec demande et backlog observés uniquement comme contexte.
- `risk_impact_costs.csv` : coûts réels des transactions exposées et statut de
  l'identification du surcoût.
- `risk_impact_quality.json` : couverture, réconciliations, avertissements et
  règles d'interprétation.

## Provenance vérifiable

`risk_impact_quality.json` contient aussi `provenance` :

- `source_files` donne, pour chaque CSV réellement lu, son chemin, son empreinte
  SHA-256, sa taille et le nombre de lignes utilisées ; l'empreinte porte sur le
  même instantané d'octets que celui analysé par le registre ;
- `identity` donne, lorsqu'une campagne parente est détectée, la cascade, la
  variante, le type de cas, la solution éventuelle et la graine aléatoire ;
- `critical_hashes` fige le manifeste, le tableau des runs, les commandes, la
  configuration, les événements de risque et l'état au passage du jour 0 ;
- `parent_run` et `parent_campaign` conservent les chemins et empreintes des
  pièces ayant servi à cette vérification.

La présence d'un seul fichier caractéristique d'une campagne active ce contrôle
strict. Une campagne incomplète, un fichier modifié, un run qui ne correspond
pas exactement à une ligne/commande, ou une identité J0 contradictoire fait
échouer la construction. Un ancien run situé hors campagne reste accepté : ses
sources disponibles sont empreintées et les éléments externes absents sont
explicitement déclarés indisponibles.

Après écriture, `registry_outputs.csv_artifacts` donne l'empreinte SHA-256 et le
nombre de lignes de chacun des sept CSV produits. Le JSON qualité ne s'auto-hache
pas : son champ `quality_json.self_hash_status` explique cette exclusion, qui
évite une définition récursive impossible.

## Splits, mélanges et unités

Un transport conserve la quantité dans une même unité. Sa propagation est une
balance matière.

Une production peut mélanger plusieurs lots et plusieurs unités de composants.
Le registre ne somme jamais des kilogrammes, mètres et unités. Pour chaque
composant, il calcule la fraction exposée. La fraction du lot fini est encadrée :

- borne basse : plus grande fraction exposée parmi les composants ;
- borne haute : somme des fractions exposées, plafonnée à 100 %.

Avec un seul composant exposé, les deux bornes sont identiques. Avec plusieurs
composants exposés dont le mélange microscopique n'est pas connu, l'intervalle
rend l'incertitude visible au lieu d'inventer une précision.

## Prévention du double comptage

Plusieurs incidents peuvent agir simultanément sur la même expédition. Le champ
`overlap_group_id` est alors commun à plusieurs lignes de
`risk_impact_bundle_events.csv`.

Règles obligatoires :

- sommer les quantités réseau par `exposure_bundle_id`, jamais par ligne
  d'incident ;
- ne pas sommer les synthèses de plusieurs incidents partageant un même groupe ;
- ne sommer que des quantités de même unité ;
- considérer les montants par incident comme non additifs tant qu'ils n'ont pas
  été désenchevêtrés par une campagne contrefactuelle.

## Coûts

Le coût de transport et le coût d'achat de l'expédition sont des coûts réels
exposés. Ils ne représentent pas automatiquement le surcoût de l'incident.

Le registre peut isoler l'effet mécanique d'un multiplicateur de prix à quantité
observée constante. Le coût total incrémental — stock supplémentaire, arrêt de
production, transport accéléré, pénalité client — reste
`not_identified_without_matched_counterfactual` jusqu'à comparaison avec un run
normal utilisant la même graine aléatoire.

## Origines avant le jour 0 et fin d'horizon

`pre_horizon_origin=1` indique qu'un lot source existait avant la période
présentée. Le chemin reste traçable, mais il ne faut pas prétendre avoir observé
sa fabrication historique.

Les expéditions dont la réception est postérieure au dernier jour simulé sont
comptées comme exposées en transit, sans invention d'un lot réceptionné ou d'un
client aval. La qualité donne séparément la couverture totale et la couverture
des réceptions attendues dans l'horizon.

## Génération sans écrasement

```powershell
python -m etudecas.simulation.analysis.build_risk_lot_impact_registry `
  --data-dir <run-ou-data> `
  --output-dir <nouveau-dossier-versionne>
```

Le générateur refuse un dossier de sortie non vide.
