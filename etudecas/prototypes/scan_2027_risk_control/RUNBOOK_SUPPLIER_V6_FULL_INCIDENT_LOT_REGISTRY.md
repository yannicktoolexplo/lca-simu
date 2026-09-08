# Registre V6 des incidents et des lots

Ce post-traitement ne relance aucune simulation. Il lit la campagne fournisseur
finalisée et, s'ils existent, les 0 à 3 rejeux détaillés déjà finalisés. Il
écrit une livraison séparée et refuse tout dossier de sortie déjà existant.

## Construire après la campagne

Depuis la racine du dépôt :

```powershell
Set-Location 'C:\dev\lca-simu-pr40'
$CampaignRoot = 'C:\chemin\campagne-v6-finalisee'
$ResultsDir = 'C:\chemin\resultats-v6-finalises'
$ReplayRoot = 'C:\chemin\rejeux-lots-finalises'
$OutputDir = 'C:\chemin\livraisons\registre-v6-neuf'

python -m etudecas.prototypes.scan_2027_risk_control.supplier_v6_full_incident_lot_registry build `
  --campaign-root $CampaignRoot `
  --results-dir $ResultsDir `
  --replay-root $ReplayRoot `
  --output-dir $OutputDir
```

Omettre `--replay-root` si aucun rejeu détaillé n'est disponible. Les 3 240
expositions et les 108 cellules sont quand même publiées, mais aucune ligne
n'est alors déclarée couverte par une généalogie.

`$OutputDir` doit désigner un dossier neuf, extérieur à la campagne, aux
résultats finalisés et aux rejeux. Le traitement refuse aussi bien un dossier
existant qu'un chemin inclus dans l'une de ces sources. Les chemins contenant
des espaces fonctionnent lorsqu'ils sont affectés aux variables entre quotes,
comme ci-dessus.

## Revalider une livraison existante

```powershell
$OutputDir = 'C:\chemin\livraisons\registre-v6-neuf'
python -m etudecas.prototypes.scan_2027_risk_control.supplier_v6_full_incident_lot_registry validate `
  --output-dir $OutputDir
```

## Livrables

- `registre_expositions_incidents_3240.csv` : une ligne par
  répétition–état–voie–mécanisme, avec expéditions, quantités, service,
  production, retard client cumulé et couverture généalogique exacte ;
- `cellules_incidents_108.csv` : les agrégats officiels par
  état–voie–mécanisme, enrichis de la couverture lots (0/30 ou 1/30) ;
- `genealogies_rejeux_detaillees.csv` : toutes les lignes natives disponibles,
  sans aperçu limité, avec expédition, lot entrant, campagne, batch, encours,
  lot fini, libération et contact client agrégé ;
- `contexte_j0_rejeux.csv` : stock composant, production, encours, demande,
  service à l'heure et retard client restant au premier jour de l'incident ;
- `registre_incidents_lots_v6.json` : le même contenu structuré, y compris les
  lignes sources brutes des généalogies ;
- `OUVRIR_REGISTRE_INCIDENTS_LOTS_V6.html` : consultation autonome en trois
  vues, sans dépendance réseau ;
- `registre_incidents_lots_v6.manifest.json` : empreintes des entrées et de tous
  les fichiers publiés.

Dans la première étape de généalogie, le champ `event_day` est le jour de
décision d'expédition (`risk_decision_day`). Le fichier natif publié ne contient
pas le jour de réception : le registre ne l'invente pas. Le champ
`event_day_kind` rappelle cette convention ligne par ligne.

## Critères de refus

Le traitement s'arrête notamment si la campagne ne prouve pas les 3 240
tests d'incident, les 90 références appariées — soit 3 330 cas signés — et les
108 cellules, si une empreinte officielle diffère, si un
agrégat ne se réconcilie pas avec ses 30 répétitions, si un rejeu ne revalide
pas son inventaire signé, ou si une ligne de généalogie est perdue.

## Limites à conserver dans toute présentation

Les tests d'incident sont des hypothèses conditionnelles, pas des événements
historiques ni des probabilités fournisseurs. Les lots descendants n'existent
que pour la répétition exacte des rejeux détaillés : ils ne couvrent jamais les 29
autres répétitions de la cellule. Le « client » est le nœud agrégé `C-XXXXX`.
Deux voies seulement utilisent un besoin MRP dynamique explicite ; aucune trace
signée de réponse MRP n'est disponible. Les analyses d'actions existantes sont
en boucle ouverte, avec `lot_trace_enabled=false` : aucun gain d'action ne peut
être rattaché ici à un lot. Les coûts et pertes de chiffre d'affaires ne sont
pas validés par ce registre. Les deux mécanismes sont testés séparément : ce
n'est pas une cascade de plusieurs incidents fournisseurs corrélés ou
endogènes. Les rejeux détaillés montrent la propagation physique d'un incident
unique dans les seuls dossiers retenus.
