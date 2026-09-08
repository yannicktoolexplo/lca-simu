# Reprise de la campagne fournisseurs V8 par tranches

## État figé

- Campagne : `fae9219a5cc59bcf9efd07b50b19009a1c7fd36b68fa81774c976b40a68c3598`.
- Aucun processus de simulation actif.
- Toutes les tâches planifiées V8 sont désactivées.
- `op_100`, blocs 1 et 2 : terminés, soit 10 répétitions sur 30.
- `op_100`, blocs 3 et 4 : reprenables ; 20 et 16 préparations signées seront réutilisées.
- Aucun incident qualité, de capacité ou de disponibilité produit fini.
- Incidents étudiés : retard transport de 120 jours et livraison planifiée réduite de 50 % pendant 42 jours.

## Règle d'exécution

Le module `resume_supplier_operating_point_full_campaign_v8_bounded.py` :

- contrôle seulement par défaut ;
- exige `--execute` pour lancer des calculs ;
- accepte un ou deux blocs explicites au maximum ;
- utilise un worker par bloc pour Ã©viter la collision Windows observÃ©e sur
  `progress.json.tmp`, tout en exÃ©cutant les deux blocs en parallÃ¨le ;
- s'arrête après les blocs sélectionnés ;
- ne lance jamais la consolidation, les relectures de lots ou la construction HTML.

Contrôle à blanc de la prochaine tranche :

```powershell
python -m etudecas.prototypes.scan_2027_risk_control.resume_supplier_operating_point_full_campaign_v8_bounded `
  --shard-id op_100__seed_block_03 `
  --shard-id op_100__seed_block_04
```

La même commande avec `--execute` à la fin constitue l'autorisation explicite de calcul. Elle ne doit être utilisée qu'après accord de l'opérateur.

### Enchaînement sûr jusqu'au bilan de tranche

L'orchestrateur `orchestrate_supplier_v8_bounded_tranche.py` regroupe ces
contrôles sans élargir le périmètre. Sans `--execute`, il ne lance aucun calcul,
n'écrit aucun fichier et vérifie que les blocs demandés ferment bien un seul
jalon 10/30, 20/30 ou 30/30 d'un seul état. Avec `--execute`, il attend la fin
des seuls blocs explicites, revalide leurs preuves, puis construit et revalide
le bilan dans un dossier qui doit être nouveau et extérieur à la campagne.

Contrôle à blanc de la tranche A et de son futur bilan 20/30 :

```powershell
python -m etudecas.prototypes.scan_2027_risk_control.orchestrate_supplier_v8_bounded_tranche `
  --operating-point-id op_100 `
  --simulation-count 20 `
  --shard-id op_100__seed_block_03 `
  --shard-id op_100__seed_block_04 `
  --checkpoint-output-dir C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_v8_op100_checkpoint_20_20260906_v1
```

Ajouter `--execute` à cette commande est l'unique autorisation de calcul et de
publication. L'orchestrateur ne lance ni consolidation inter-états, ni suivi
de lots, ni étape aval, et ne modifie aucune tâche planifiée.

## Découpage restant

| Tranche | Blocs autorisés | Résultat atteint après validation |
|---|---|---|
| A | `op_100` 03 et 04 | état 100 : 20/30 |
| B | `op_100` 05 et 06 | état 100 : 30/30 |
| C | `op_93` 01 et 02 | état 93 : 10/30 |
| D | `op_93` 03 et 04 | état 93 : 20/30 |
| E | `op_93` 05 et 06 | état 93 : 30/30 |
| F | `op_80` 01 et 02 | état 80 : 10/30 |
| G | `op_80` 03 et 04 | état 80 : 20/30 |
| H | `op_80` 05 et 06 | état 80 : 30/30 |

Une paire de blocs a demandé environ sept heures lors de la première exécution complète. Cette durée est indicative et doit être réestimée après chaque tranche.

## Après chaque tranche

1. Vérifier les 185 résultats signés de chaque bloc, sans erreur.
2. Vérifier qu'aucun processus enfant ne subsiste.
3. Contrôler le jalon demandé, sans écriture ni nouveau calcul :

   ```powershell
   python -m etudecas.prototypes.scan_2027_risk_control.supplier_v8_state_checkpoint `
     --mode readiness `
     --operating-point-id op_100 `
     --simulation-count 20
   ```

   Remplacer `op_100` et `20` par l'état et le jalon atteints. Les seuls jalons
   admis sont 10, 20 et 30.
4. Produire, seulement lorsque le contrôle répond `ready`, un nouveau bilan
   intermédiaire dans un dossier distinct :

   ```powershell
   python -m etudecas.prototypes.scan_2027_risk_control.supplier_v8_state_checkpoint `
     --mode build `
     --operating-point-id op_100 `
     --simulation-count 20 `
     --output-dir C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_v8_op100_checkpoint_20_20260906_v1
   ```

   Ce générateur ne lance pas le moteur de simulation, ne modifie pas la
   campagne et refuse d'écraser le bilan historique 10/30.
5. Laisser les tâches automatiques désactivées.
6. Attendre une nouvelle autorisation avant la tranche suivante.

La sensibilité entre les trois états, les intervalles statistiques, la sélection des dossiers fournisseurs, les relectures détaillées de lots et l'HTML autonome final ne sont exécutés qu'après validation des 18 blocs.
