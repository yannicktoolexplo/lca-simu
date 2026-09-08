# Synthèse fournisseurs V6 sur trois états

Ce post-traitement se lance uniquement après la validation de la campagne, des
rejeux lots et de la qualification physique. Il ne démarre aucune simulation et
ne modifie aucun résultat existant. Il refuse aussi d'écraser son dossier de
sortie.

La campagne V6 est finalisée par l'adaptateur V6 qui réemploie le schéma
d'agrégats V4 figé. Le module contrôle donc ce contrat officiel V4 ainsi que la
chaîne source déjà validée, sans convertir ni réécrire les résultats.

## Construction

```powershell
Set-Location 'C:\dev\lca-simu-pr40'

$campaignRoot = 'C:\chemin\vers\campagne-v6'
$resultsDir = 'C:\chemin\vers\resultats-finalises-v6'
$qualificationDir = 'C:\chemin\vers\qualification-physique-v5'
$lotReplayRoot = 'C:\chemin\vers\rejeux-lots-v6'
$actionResultsRoot = 'C:\chemin\vers\rejeux-actions-v6'
$readoutDir = 'C:\chemin\vers\nouvelle-synthese-v6'

python -m etudecas.prototypes.scan_2027_risk_control.supplier_v6_cross_state_business_readout build `
  --campaign-root $campaignRoot `
  --results-dir $resultsDir `
  --qualification-dir $qualificationDir `
  --lot-replay-root $lotReplayRoot `
  --action-results-root $actionResultsRoot `
  --output-dir $readoutDir
```

`--target-registry <fichier>` est optionnel si le registre signé se trouve déjà
dans le dossier de résultats. `--action-results-root` peut être omis : la page
indiquera alors qu'aucun gain de levier validé n'est fourni.

## Contrôle sans recalcul

```powershell
$readoutDir = 'C:\chemin\vers\nouvelle-synthese-v6'

python -m etudecas.prototypes.scan_2027_risk_control.supplier_v6_cross_state_business_readout validate `
  --output-dir $readoutDir
```

Le dossier `$readoutDir` doit être nouveau et extérieur aux dossiers sources.
Les chemins sont placés dans des chaînes PowerShell pour accepter sans ambiguïté
les espaces et les chemins Windows.

Le dossier contient :

- `OUVRIR_COMPARAISON_FOURNISSEURS_3_ETATS.html`, autonome et limité à trois vues ;
- `comparaison_fournisseurs_3_etats.csv`, une ligne par fournisseur et mécanisme ;
- `comparaison_fournisseurs_3_etats.json`, avec les trois états et toutes les preuves affichées ;
- `comparaison_fournisseurs_3_etats.manifest.json`, avec les empreintes des sources et sorties.

La page ne force jamais trois noms. Elle distingue les signaux stables, les
signaux dépendants de l'état, les comparaisons inter-états non admissibles et
l'absence de signal. Les 10 000 bootstrap sont
présentés comme des rééchantillonnages des 30 simulations, jamais comme 10 000
simulations physiques ou une probabilité d'incident.

Une preuve lot détaillée n'est affichée que dans la cellule exacte
état–mécanisme–voie qui a été rejouée. Les simulations d'actions ne tracent pas
les lots et ne permettent donc pas de nommer un « lot sauvé ».
