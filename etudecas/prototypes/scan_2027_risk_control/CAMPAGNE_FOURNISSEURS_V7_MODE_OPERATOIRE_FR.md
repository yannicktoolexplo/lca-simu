# Validation fournisseurs V7 — mode opératoire

## Objet

V7 confirme un unique réglage déjà figé, sans rechercher un meilleur réglage :

- état proche de 100 % : délais ajoutés `(268091=0 ; 268967=0)` ;
- état proche de 93 % : `(8,4 ; 80,6)` jours ;
- état proche de 80 % : `(17,5 ; 96,6)` jours.

La décision repose exclusivement sur 150 nouvelles graines communes aux trois
états, soit 450 simulations physiques. Les résultats V5/V6 ont servi au
développement du protocole et au dimensionnement, jamais comme preuves V7.

## Garde-fous scientifiques

- Aucun choix de candidat ni réglage n'est permis en V7.
- Les points à 30, 60, 90 et 120 graines sont descriptifs. Seul le résultat à
  150 graines peut accepter ou rejeter le triplet.
- Le bootstrap comporte exactement 50 000 rééchantillonnages de blocs complets
  de graines. Il ne constitue pas 50 000 nouvelles simulations physiques.
- La même graine définit un bloc statistique commun aux trois états. L'audit RNG
  signé ne met en évidence aucune anomalie. Les calendriers physiques pouvant
  diverger, un appariement aléatoire exact événement par événement n'est ni
  requis ni revendiqué.
- Un rejet interdit toute correction sur cette cohorte : il faut un nouveau
  protocole et de nouvelles graines.

Les critères principaux sont figés dans `protocol_manifest.json` : intervalles
bootstrap à 90 % entièrement dans les bandes 91,5–94,5 % et 78,5–81,5 %, borne
basse unilatérale à 95 % d'au moins 98,5 % pour l'état haut, six marges d'ordre
simultanées strictement positives, et écart entre produits inférieur ou égal à
5 points dans chaque état. Les inversions graine par graine restent un diagnostic
secondaire ; une égalité au plafond n'est pas un échec.

## Séquence prévue après audit du code

Les commandes ci-dessous sont un plan d'exécution. Ne pas les lancer avant le
feu vert et la vérification indépendante du SHA du module.

```powershell
$module = "etudecas/prototypes/scan_2027_risk_control/supplier_fresh_development_holdout_protocol_v7.py"
$moduleSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $module).Hash.ToLower()

python -m etudecas.prototypes.scan_2027_risk_control.supplier_fresh_development_holdout_protocol_v7 prepare-plan --reviewed-module-sha256 $moduleSha
python -m etudecas.prototypes.scan_2027_risk_control.supplier_fresh_development_holdout_protocol_v7 validate-plan
python -m etudecas.prototypes.scan_2027_risk_control.supplier_fresh_development_holdout_protocol_v7 prepare-run
python -m etudecas.prototypes.scan_2027_risk_control.supplier_fresh_development_holdout_protocol_v7 run-validation --workers 2
python -m etudecas.prototypes.scan_2027_risk_control.supplier_fresh_development_holdout_protocol_v7 status
python -m etudecas.prototypes.scan_2027_risk_control.supplier_fresh_development_holdout_protocol_v7 finalize
python -m etudecas.prototypes.scan_2027_risk_control.supplier_fresh_development_holdout_protocol_v7 validate-result
```

While an official `run-validation` is active, use the additive monitor below
instead of the frozen protocol's `status` command. It is strictly read-only:
it validates the plan, run, latest signed progress, and each committed proof.
Attempts without a proof (active or orphaned) are reported separately; they
are neither counted as evidence nor modified.

```powershell
python -m etudecas.prototypes.scan_2027_risk_control.supplier_fresh_development_holdout_monitor_v7
```

`run-validation` reprend les seules preuves signées déjà valides. En reprise
officielle et avant de relire les preuves, il purge de façon idempotente les seuls
répertoires de cas reconnus et strictement bornés sous `engine_attempts`. Il ne
touche jamais aux courbes ni aux bundles conservés. Une preuve de cas n'est
publiée qu'après réussite et vérification de cette purge canonique. Une coupure
avant publication laisse donc un cas à rejouer, jamais une fausse preuve complète.

Dès que `validation_result.json` existe, `run-validation` refuse toute nouvelle
exécution ou reprise avant de réécrire progression ou points intermédiaires. Les
répertoires de plan et de run refusent également les sources protégées, les
fichiers inattendus et les écrasements de preuves.

## Sorties et reprise aval

Chaque preuve conserve avant purge canonique :

- les quatre tables journalières production/service/stock/contraintes ;
- `first_simulation_daily.csv` lorsqu'il existe ;
- le résumé de simulation ;
- la trace journalière complète des expéditions fournisseurs ;
- une courbe JSON compacte demande/service/backlog.

Les fichiers sont compressés en gzip déterministe, hashés et reliés à la preuve.
`validate_result(...)` reconstruit la décision sans écriture. La fonction publique
`validated_evidence(...)` fournit ensuite l'index validé des 450 preuves et les
chemins relatifs des bundles pour les post-traitements autorisés.

## Limites de lecture métier

V7 valide la capacité du simulateur à représenter trois niveaux de service sous
les hypothèses de délais fixées. Elle ne mesure pas une performance fournisseur
observée et ne donne pas une probabilité historique d'incident. Cette étape ne
teste ni incident qualité, ni cascade de risques, ni action corrective, ni coût,
ni politique en boucle fermée. La trace d'expéditions est une sortie brute du
profil compact ; elle ne devient une preuve de campagne incidents/lots qu'après
un post-traitement séparé et explicitement validé.
