# Exécution et reprise d'une calibration fournisseur

La calibration caractérise des hypothèses de simulation. Elle ne mesure pas
une performance fournisseur observée et n'autorise pas à promouvoir une action.
La robustesse des fichiers ne constitue pas une validation scientifique.

## Deux versions explicites

Le module historique `supplier_service_regime_calibration_runner.py` reste
inchangé : ses octets sont référencés par des contrats figés. Son écriture peut
échouer sous Windows avec `WinError 5`, comme reproduit le 17 septembre 2026.

Pour une **nouvelle exécution**, le module
`supplier_service_regime_calibration_runner_v2.py` utilise `etudecas.atomic_io`.
Il s'agit d'une copie versionnée, sans modification des règles de sélection,
des graines ni des empreintes attendues du protocole et du plan. Cette duplication
est volontaire : toute évolution commune nécessite une comparaison explicite,
sans réécrire automatiquement la V1. Aucun appelant historique n'est redirigé.

La signature V2 contient sa version, son code et le SHA-256 du module d'écriture.
Le manifeste expose également la politique d'écriture et cette empreinte.
Un dossier V1 ne peut pas être repris par V2 ; choisir un nouveau dossier.
Modifier le module d'écriture change la signature et empêche une reprise implicite.
Ces empreintes ne couvrent pas automatiquement toutes les dépendances transitives.

```powershell
# Lecture et validation seulement : aucune simulation ni création de résultats.
python -m etudecas.prototypes.scan_2027_risk_control.supplier_service_regime_calibration_runner_v2 --mode validate --plan-dir C:\chemin\plan-signe

# Nouvelle exécution : dossier distinct de toute campagne V1.
python -m etudecas.prototypes.scan_2027_risk_control.supplier_service_regime_calibration_runner_v2 --mode screening --plan-dir C:\chemin\plan-signe --output-dir C:\chemin\nouvelle-calibration-v2
```

Le plan doit toujours être celui attendu par le contrat. Les fixtures synthétiques
ne sont acceptées que dans les tests, par une substitution temporaire de leur
empreinte attendue. Elles ne constituent pas un plan de production autorisé.

## Déroulement métier

1. Le screening exécute les 36 candidats avec la graine prévue.
2. La sélection discrète est figée, sans interpolation.
3. La confirmation établit un checkpoint signé sur les 15 premières répétitions
   (`--mode confirmation --checkpoint-after-repetitions 15`).
4. La reprise (`--mode confirmation`, sans cette option) ajoute seulement les
   répétitions 16 à 30. Les preuves du préfixe sont conservées et vérifiées.

Un résultat de test utilisant un exécuteur synthétique reste non publiable.
Les indicateurs `confirmatory_release_allowed` et `action_promotion_allowed`
restent faux. Un smoke test ne peut pas alimenter une campagne complète.

## Publication et erreurs

Chaque JSON ou CSV est écrit dans un temporaire unique situé dans le même
dossier, vidé et synchronisé, puis remplacé atomiquement. Le fichier précédent
n'est jamais supprimé avant le remplacement. Le contenu CSV garde ses colonnes,
ses caractères UTF-8 et ses champs multilignes.

Seuls les codes Windows 5, 32 et 33 au remplacement sont retentés : six essais
maximum et cinq attentes de 0,05 ; 0,10 ; 0,20 ; 0,40 ; 0,80 seconde (1,55 seconde
d'attente demandée au total, hors temps des appels système). Une erreur de
sérialisation, de synchronisation, ou un autre code n'est pas retenté.
Un refus d'accès peut être permanent : épuiser les essais remonte alors l'erreur.

Le temporaire de cette écriture est nettoyé en cas d'échec récupérable par Python.
Si son nettoyage échoue également, une note est ajoutée à l'exception initiale.
Un arrêt brutal peut laisser un temporaire. Ni une transaction sur plusieurs
fichiers ni une garantie de durabilité après panne matérielle ne sont revendiquées.
Deux écrivains indépendants peuvent publier chacun un fichier complet, mais le
dernier remplacement gagne ; le verrou de campagne reste indispensable.

Une preuve peut être publiée avant l'échec de mise à jour du registre. La reprise
refuse cet inventaire incomplet ; elle ne réintègre, ne supprime et ne résigne
aucune preuve automatiquement. Conserver le dossier et le journal pour diagnostic,
résoudre le refus d'accès, puis utiliser un nouveau dossier si l'inventaire est
incohérent. Une reprise après erreur n'est sûre que si les contrôles la valident.

## Documentation et vérification

Le registre `docs/rules/calibration_execution.json` relie ces règles au code
V2, à la politique d'écriture et aux tests de refus, reprise et non-réutilisation.
Il participe à `build-all`, `check-all` et `watch-all`. Les empreintes documentaires
signalent les changements ; leur acceptation exige une relecture explicite.

Le workflow local prévoit les tests d'écriture sur Windows et Linux. Les erreurs
Windows sont injectées pour tester les branches de façon déterministe ; cela ne
prouve pas la cause externe du verrou observé. La présence du workflow ne signifie
pas qu'il a été exécuté sur GitHub.
