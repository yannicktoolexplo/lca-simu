# Sélection des fournisseurs pour préparer des actions

Le protocole historique `supplier_post_top3_action_protocol` appelait une
fonction supprimée, `_stable_v2_suppliers`. Son ancien test d'acceptation
s'appuyait sur 30 réalisations, des indicateurs de stabilité et des extensions
déclarées complètes. Le sélecteur actuel a un contrat différent : ses frontières
scientifiques fournissent des candidats descriptifs, sans autoriser une action.

## Contrat actuel

Le protocole utilise désormais l'entrée publique
`select_confirmed_action_suppliers` du sélecteur. En mode `post-top3`, l'option
`--priority-boundary-audit` permet de fournir explicitement l'audit scientifique
associé aux résultats réseau de `--network-results`.

- Sans audit fourni, la sélection est refusée avec le motif
  `priority_boundary_audit_required`. Les anciens indicateurs V2 ne suffisent pas.
- Avec un audit fourni, les contrôles existants du sélecteur sont exécutés.
  Un audit manquant, incohérent ou rejeté provoque une erreur ; aucun classement
  historique ne sert de solution de repli.
- Un trio descriptif d'enveloppe service, un groupe de priorités non départagé
  ou le groupe service V3 restent des candidats. Le groupe V3 complet conserve
  ses quatre fournisseurs, sans être tronqué arbitrairement à trois.
- Aucune de ces frontières ne libère actuellement une sélection pour agir :
  les fournisseurs sélectionnés restent vides et `action_promotion_allowed`
  vaut `false`. Les candidats, leur périmètre et le motif scientifique de
  blocage sont conservés dans `selection_evidence` du manifeste du protocole.

Le statut historique `selection_refused_v2_not_stabilized` reste utilisé pour
la compatibilité des consommateurs. Le champ `candidate_selection_status`
conserve le statut scientifique plus précis lorsqu'un audit a été validé.
La préparation du catalogue reste possible ; le fichier des actions des
fournisseurs sélectionnés reste vide. Le protocole n'exécute aucune simulation.

## Portée et limites

Cette correction raccorde le protocole aux règles scientifiques déjà présentes.
Elle n'ajoute pas de voie autorisant des actions. Une telle évolution demandera
un contrat explicite, des preuves adaptées et des tests d'acceptation distincts.
La présence dans un groupe descriptif ne constitue ni une recommandation
industrielle ni une mesure de criticité observée du fournisseur.

Les tests couvrent les anciens indicateurs, les trois types de candidats et
des audits invalides ou absents. Les fixtures du sélecteur remplacent certains
validateurs amont par des lecteurs contrôlés : elles vérifient le raccordement
et les gardes locales, pas toute la chaîne cryptographique des livraisons.
Certains tests de données réelles restent dépendants des artefacts externes.

Les sources du protocole et du sélecteur ont changé. Leurs nouvelles empreintes
ne sont pas réacceptées dans les anciens manifestes signés ; une livraison
historique qui les fige reste liée à sa version d'origine.
