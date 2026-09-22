# Plans V2 et fixtures V3 autonomes — 17 septembre 2026

Les cinq échecs V3 du bilan initial apparaissaient sous le message générique
`V2 refinement plan/signature mismatch`. Le diagnostic sépare deux problèmes.

La signature interne du plan historique V2 est valide. Son constructeur était
cependant présent en CRLF dans le checkout ; ses octets LF sont exactement ceux
de Git et de l'empreinte attendue par le plan. La copie de travail a été normalisée
et protégée par `.gitattributes`, avec une
[preuve conservée](../quality/2026-09-17-v2-driver.json). Aucun hash attendu n'a été
remplacé. Le contrôle passe alors à la dépendance historique V1, dont la validation
échoue à son tour. Son diagnostic en lecture seule retrouve également une
signature de plan valide et une différence CRLF/LF du constructeur V1 ; cette
dépendance n'a pas été modifiée dans cette étape. Cela ne qualifie donc pas toute
la chaîne historique, ni ses autres dépendances transitives.

## Correction des tests

Les tests V3 ne copient plus implicitement les livraisons externes du poste.
Ils construisent les plans et les résultats V1/V2 dans le dossier temporaire,
avec les générateurs existants, des exécuteurs synthétiques et les vrais
validateurs. Le helper V1 accepte une réponse op80 optionnelle ; sa valeur par
défaut et les scénarios V2 existants restent inchangés.

La réponse choisie pour le scénario V3 donne 81 % global en V1, admis dans sa
bande de 78,5–81,5 %, mais refusé par la bande V2 de 79,25–80,75 %. Les nouveaux
candidats op80 V2 sont également insuffisants. Le refus V2 est recalculé depuis
les preuves, jamais imposé par substitution du validateur ou réécriture d'un
statut. V3 doit alors réutiliser 65 preuves et produire seulement 15 cas nouveaux,
sans lire les graines réservées à la validation finale.

Les tests existants conservent leurs contrôles de reprise, d'interruption,
d'altération des preuves, des propositions et des graphes. Un nouveau test
modifie le hash du constructeur dans un plan et recalcule sa signature : le
validateur doit toujours le refuser, car signer un contenu ne prouve pas sa
conformité au contrat scientifique.

Un test historique distinct utilise `--historical-artifacts`. Sans cette option,
il est ignoré explicitement. Avec l'option, tous les plans et sources transitifs
doivent être cohérents ; les chemins historiques ne sont pas réécrits.

## Portée

Ces tests vérifient l'orchestration et les critères de sélection avec des résultats
synthétiques. Ils ne lancent pas le moteur et ne constituent pas une nouvelle
validation scientifique des résultats historiques. Le code métier et les
empreintes attendues en production restent inchangés.

## Vérification

Les sept tests V3 existants passent, dont les cinq auparavant bloqués, en
258,25 secondes. Cette exécution avait collecté le module avant l'ajout des deux
nouveaux tests ; ceux-ci sont couverts par l'exécution ciblée ci-dessous. Au total,
les deux exécutions couvrent **19 tests réussis et 1 intégration historique ignorée**.

Les onze tests V2 et le nouveau refus d'un constructeur différent passent :
**12 réussites et 1 intégration historique ignorée**, en 64,92 secondes.
Les tests documentaires passent également : **12 réussites et 4 sous-tests**.
La suite générale de référence n'est pas relancée pour cette intervention ciblée ;
son dernier résultat de 653 réussites appartient au bilan précédent. Les modules
V2/V3 restent hors de ce socle court ; ils se lancent explicitement pour vérifier
cette chaîne plus coûteuse.
Le rapport de l'exécution ciblée est conservé localement sous
`etudecas/artifacts/testing/2026-09-17-v2-signatures/targeted.xml` et `targeted.json`.

```powershell
python -m pytest etudecas/prototypes/scan_2027_risk_control/tests/test_supplier_balanced_product_delay_multiseed_refinement_v2.py etudecas/prototypes/scan_2027_risk_control/tests/test_supplier_balanced_product_delay_multiseed_refinement_v3.py -q
```
