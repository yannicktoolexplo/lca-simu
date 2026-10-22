# Exécution et reprise d'une calibration fournisseur

La calibration caractérise des hypothèses de simulation. Elle ne mesure pas
une performance fournisseur observée et n'autorise pas à promouvoir une action.
La robustesse des fichiers ne constitue pas une validation scientifique.

## Protocole avant exécution

Appliquer les critères de [développement scientifique](DEVELOPPEMENT_SCIENTIFIQUE.md)
et le skill `etudecas-supply-calibrate` après le diagnostic de l'écart. Déclarer
rapprochement historique, rejeu autonome ou prospective ; identifier les données
d'entrée et celles réservées à la comparaison, avec leurs dates de connaissance.
Vérifier périmètre, unités, calendriers, état initial, BOM et politiques avant
d'ajuster un paramètre. Une injection rétrospective reste identifiée comme telle.

Dans le suivi existant, figer avant calcul hypothèse et témoin, paramètres bornés,
critères de volumes et de dates, fenêtres chronologiques de calibration et de
validation, budget et condition d'arrêt. Examiner sensibilité, identifiabilité
et compensations entre paramètres ; déclarer ce que les sources ne permettent
pas d'identifier. Une meilleure courbe n'établit pas une cause industrielle.

Commencer par un oracle en mémoire et une baseline ciblée. Le déroulement
screening/confirmation ci-dessous appartient à ce runner précis ; il ne rend
pas 36 candidats ou 30 répétitions nécessaires à toute calibration. N'étendre
le calcul que si une question supplémentaire le justifie. Avant promotion,
contre-vérifier hors ajustement les effets sur stocks, flux, dates et service
dans toute la chaîne, avec gains, dégradations et limites ; préserver le nominal.

## Une seule implémentation courante

Le module `supplier_service_regime_calibration_runner.py` contient désormais
l'implémentation robuste V2, qui utilise `etudecas.atomic_io`. Le fichier suffixé
`_v2.py` a été retiré après comparaison : les règles de sélection, les graines,
les commandes de calcul et les indicateurs sont conservés. Le schéma de résultats
reste explicitement V2 ; le nom du fichier ne détermine pas la version du contrat.

Les anciennes sources sont conservées dans la capsule de comparaison du tri du
23 septembre. La V1, dont l'écriture pouvait échouer sous Windows, n'est plus
une seconde implémentation courante. Ses résultats et signatures historiques
ne sont ni réécrits ni réutilisés implicitement.

La signature V2 contient sa version, son code et le SHA-256 du module d'écriture.
Le manifeste expose également la politique d'écriture et cette empreinte.
Un dossier V1 ne peut pas être repris par V2 ; choisir un nouveau dossier.
Modifier le module d'écriture change la signature et empêche une reprise implicite.
Ces empreintes ne couvrent pas automatiquement toutes les dépendances transitives.

```powershell
# Lecture et validation seulement : aucune simulation ni création de résultats.
python -m etudecas.prototypes.scan_2027_risk_control.supplier_service_regime_calibration_runner --mode validate --plan-dir C:\chemin\plan-signe

# Nouvelle exécution : dossier distinct de toute campagne V1.
python -m etudecas.prototypes.scan_2027_risk_control.supplier_service_regime_calibration_runner --mode screening --plan-dir C:\chemin\plan-signe --output-dir C:\chemin\nouvelle-calibration-v2
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

Le workflow et les anciens tests d'écriture Windows/Linux décrivent une couverture
historique, pas une autorisation d'exécution actuelle. Appliquer la
[sélection exacte des contrôles](TEST_VALIDATION.md) et les restrictions Sophos de
`AGENTS.md` : relire chaque cas et ses fixtures, exclure altérations volontaires,
restaurations de dates, disparitions simulées et écritures factices répétées.
Ne pas relancer `check_source_revision.py` ni une variante. Une injection d'erreur
Windows historique ne prouve pas la cause externe d'un verrou.

En cas de nouveau refus d'écriture ou d'alerte, arrêter les exécutions concernées,
conserver preuves et journal, puis diagnostiquer en lecture seule. La politique
de reprise interne décrite plus haut n'autorise ni nouvelles sondes ni relances
pour contourner Sophos. Un contrôle exclu ou non exécuté reste déclaré tel quel ;
la présence d'un workflow ne signifie pas son exécution locale ou sur GitHub.
