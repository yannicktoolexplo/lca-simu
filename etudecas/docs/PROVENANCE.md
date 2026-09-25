# Références reproductibles et provenance

## Empreintes des sources figées

Les contrôles scientifiques conservent le SHA-256 des octets exacts. Une
empreinte documentaire AST n'est pas un substitut à cette preuve d'identité.
Un écart doit être diagnostiqué avant de reconstruire un résultat ou de revoir
son état de référence.

```powershell
python -m etudecas.provenance --path chemin/source.py --expected-sha256 EMPREINTE_ATTENDUE
```

Ce diagnostic en lecture seule distingue une égalité exacte, une différence
expliquée uniquement par CRLF au lieu de LF sur une source UTF-8, et les autres
différences. Seule l'égalité exacte retourne 0 ; tout écart retourne 1 et une
erreur d'entrée retourne 2. La commande ne modifie ni source ni manifeste et
n'accepte pas une empreinte de remplacement. Le statut `content_mismatch`
signifie « non expliqué par cette normalisation », sans conclure à une différence
de comportement du code.

Les six premières sources protégées par `text eol=lf` dans `.gitattributes` étaient :
`build_industrial_supply_preliminary_complete_v3.py` et
`supplier_operating_point_full_campaign_v2.py` et
`supplier_balanced_product_delay_multiseed_refinement_v3.py`, ainsi que
`launch_supplier_operating_point_full_campaign_v8.py`, et les wrappers
`run_supplier_v8_v2_to_stage3_v3_chain_task.ps1` et
`run_supplier_v8_v2_to_stage3_v4_chain_task.ps1`. Lors de ce contrôle historique,
leur contenu LF correspondait exactement à Git et aux empreintes examinées.
Ce constat ne décrit pas les versions modifiées depuis. Les règles empêchent
la conversion automatique CRLF au checkout ; elles ne corrigent pas à elles
seules une copie de travail déjà existante. Cette politique reste limitée à
ces sources vérifiées, sans réécriture générale des artefacts historiques.

La consolidation du 23 septembre utilise un registre de révision distinct,
`prototypes/scan_2027_risk_control/supplier_campaign_source_revision.json`.
Ses 34 sources courantes et le registre sont protégés en LF dans Git ; les BOM
PowerShell sont conservés. Les empreintes courantes portent sur les octets LF
exacts, sans normalisation permissive pendant la vérification. Les anciennes
empreintes et capsules restent inchangées. Un ancien plan ne devient pas valide
par cette migration : une reprise exige la même révision et les mêmes intrants.

Le 17 septembre, 58 autres sources ont été examinées et protégées de la même
façon, soit 64 au total. L'[inventaire des preuves](quality/2026-09-17-frozen-sources.json)
conserve pour chacune de ces 58 sources l'empreinte avant correction,
l'empreinte LF attendue et les emplacements qui déclarent cette empreinte.
La correction exige à la fois l'égalité avec l'empreinte existante et avec
les octets de `HEAD`. Elle ne met à jour aucun hash scientifique attendu.
Les sources modifiées en contenu et les fichiers sans référence concordante
restent hors de cette opération. Une source peut correspondre à une version
figée sans satisfaire un autre consommateur attendant une version différente :
les tests des consommateurs restent nécessaires.

Le diagnostic des plans V2 a ensuite identifié le même problème dans
`supplier_balanced_product_delay_multiseed_refinement_v2.py`. Sa signature de
plan était valide ; seuls les octets CRLF du constructeur différaient. La
[preuve dédiée](quality/2026-09-17-v2-driver.json) confirme l'identité de sa
version LF avec Git et le hash déclaré dans le plan historique. Cette correction
porte à 65 le nombre de sources protégées en LF, sans réaccepter de manifeste.

L'inventaire historique V8 a ensuite été retrouvé et vérifié contre la signature
attendue par Stage3. Il permet de corriger 21 autres représentations CRLF après
comparaison avec Git, soit 86 sources protégées en LF. Sur ses 68 entrées,
61 correspondent maintenant exactement ; sept restent non expliquées par la
normalisation LF. Le chemin signé du dépôt diffère également. Le contrat V8
reste donc refusé dans ce checkout ; aucun hash d'inventaire n'est remplacé.

Le diagnostic d'inventaire reste en lecture seule :

```powershell
python -m etudecas.testing.inventory --root . --reference etudecas/docs/quality/v8-stage2-reference.json --expected-signature 02ed2e5b92828732aec51b4322596e99c3fbaa9ec771e89c3be8cf9011f8191a
```

Il retourne 1 en cas d'écart et 2 si la référence est invalide. Il compare les
entrées enregistrées et le chemin du dépôt, sans certifier la découverte des
dépendances transitives ni la validité scientifique de la campagne.

## Réutilisation des résultats Monte Carlo dans la carte

Un horizon compatible ne suffit pas pour réutiliser un résumé partagé. Celui-ci
doit déclarer `manifest.manifest_path` ou `run_manifest`, résolu vers
`<run cible>/run_manifest.json` ou `<run cible>/run/run_manifest.json`.
Les chemins relatifs sont résolus depuis la racine du dépôt.

L'horizon déclaré par `days_override`, ou à défaut `days`, doit être un entier
positif, éventuellement écrit comme chaîne entière. Un horizon cible connu
doit être identique. Les résumés JSON mal formés ou de types inattendus sont
refusés. Un résumé fourni explicitement ou trouvé dans le dossier local est
prioritaire ; s'il est incompatible, une erreur est levée. Seul un résumé
situé sous le dossier du run cible peut omettre le chemin du manifeste.

En l'absence de résumé explicite ou local, les candidats partagés compatibles
sont classés par nombre de runs réussis puis date de modification. Le fallback
partagé peut être désactivé. Si aucun candidat ne convient, la fonction retourne
le chemin local attendu, qui peut ne pas exister ; elle ne crée pas de données.

Cette vérification rattache un résultat au run par son chemin déclaré. Elle
ne compare pas les empreintes du graphe, du moteur, des paramètres ou du
contenu du manifeste et n'exige pas que le manifeste déclaré existe. Un chemin
réutilisé après modification du run ne constitue donc pas une preuve de
reproductibilité scientifique. Cette limite est distincte des contrôles exacts
des sources figées décrits plus haut.

Les tests du pipeline utilisent des répertoires temporaires et isolent tous
les emplacements de recherche partagés. Ils ne dépendent pas de résultats
historiques présents sur le poste. Les tests de livraisons historiques utilisant
des sources auditées externes restent des intégrations dépendantes de ces données.
