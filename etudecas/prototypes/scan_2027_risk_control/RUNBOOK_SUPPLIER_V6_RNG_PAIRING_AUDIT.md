# Audit du couplage aléatoire V6

## Objet

Ce livrable vérifie si les six inversions de service de `PF268967` entre OP93
et OP80 peuvent être expliquées par un décalage des tirages aléatoires.

Il ne relance pas le moteur. Il relit et revalide uniquement le plan, les 90
preuves, les summaries référencés par hash et les traces compactes signées du
holdout V6. Les campagnes V4, V5 et V6 restent inchangées.

## Construire une fois le livrable officiel

Depuis `C:\dev\lca-simu-pr40` :

```powershell
python -m etudecas.prototypes.scan_2027_risk_control.supplier_v6_rng_pairing_audit audit
```

La commande refuse tout écrasement. La cible par défaut est :

```text
C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_v6_rng_pairing_audit_20260905_v1
```

Elle produit :

- `supplier_v6_rng_pairing_audit.json` : preuve scientifique signée ;
- `supplier_v6_rng_pairing_seed_summary.csv` : six inversions et six témoins ;
- `RAPPORT_AUDIT_COUPLAGE_ALEATOIRE_V6_FR.md` : lecture métier en français ;
- `artifact_manifest.json` : tailles, SHA-256 et signature du paquet.

## Revalider un paquet existant

```powershell
python -m etudecas.prototypes.scan_2027_risk_control.supplier_v6_rng_pairing_audit validate
```

La validation échoue si un fichier manque, si un hash diffère ou si une
signature n'est plus conforme.

## Lecture correcte

La conclusion attendue est `aucun_defaut_rng_prouve`. Elle signifie que tous
les tirages de délai observables sont exactement reproductibles à partir de
l'identité fournisseur-flux-jour signée. Elle ne transforme pas le NO-GO V6 en
succès et n'explique pas à elle seule les six inversions de taux de service.

Les calendriers de commande divergent entre OP93 et OP80 sous l'effet de la
dynamique stocks/MRP/cadencement. Une graine commune couple les mêmes
événements physiques lorsqu'ils ont lieu le même jour ; elle ne force pas les
deux systèmes à déclencher les mêmes commandes.

## Limite lots

Les preuves V6 permettent de compter les expéditions, mais pas de reconstruire
les lots de production : `lot_trace_enabled=false` et `lot_count=0`. Toute
analyse causale lot par lot doit donc faire l'objet d'une campagne diagnostique
distincte, définie avant le gel d'une future validation.
