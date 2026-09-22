# Raccordement du protocole fournisseur — 16 septembre 2026

L'appel à `_stable_v2_suppliers`, absent du module fournisseur, provoquait trois
échecs reproductibles. Le protocole utilise maintenant l'entrée publique
`select_confirmed_action_suppliers`, qui consulte les contrôles scientifiques
actuels lorsque l'audit de frontière est fourni.

Le contrat actuel conserve des candidats descriptifs et interdit leur promotion
en sélection autorisant des actions. Restaurer l'ancienne acceptation sur les
seuls indicateurs V2 aurait contredit ce contrat. Le test d'acceptation ancien
a donc été remplacé par un test de refus explicite ; les candidats et les
motifs de blocage restent accessibles dans `selection_evidence` du manifeste.

L'option `--priority-boundary-audit` est disponible sur le protocole historique.
Son absence donne un refus motivé ; un audit fourni invalide provoque une
erreur. Le groupe service V3 conserve ses quatre fournisseurs. Aucune
simulation ni aucune réacceptation de manifeste historique n'a été effectuée.

Validation : **37 tests réussis et 4 sous-tests réussis**, couvrant le protocole,
le sélecteur et la documentation. Avant correction, les deux modules de tests
applicatifs donnaient **3 échecs et 18 réussites**. L'aide CLI et
`git diff --check` passent. Les tests ne requalifient pas toute la chaîne de
provenance historique ; certains validateurs amont sont remplacés dans les
fixtures.

Le [contrat métier](../SUPPLIER_ACTION_SELECTION.md) et sa règle générée sont
maintenus avec des empreintes de code et un contrôle documentaire automatisé.
La prochaine priorité reste l'isolation des fixtures de prototypes dépendant
de chemins externes et la séparation entre tests reproductibles et tests
d'intégration sur livraisons historiques.
