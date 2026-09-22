# Audit depuis HEAD — moteur, API, préparation et prototypes

Date : 20 septembre 2026. Référence : `f95b1db6bb233cbf9750fc6ab2fda3943d6e82ab` du 15 septembre. Revue en lecture seule des sources. Aucun correctif de production, aucune nouvelle simulation réelle, aucune modification des résultats historiques.

**Deux défauts nouveaux reproductibles et une lacune héritée de cache sont établis.** Aucun ne démontre que les résultats nominaux livrés sont faux. Les conditions d’activation et les limites de chaque preuve sont précisées ci-dessous. Cette revue n’est pas une certification exhaustive du simulateur.

## Constats

### MHEAD-01 — P2 : une origine fabricant peut être surallouée après division d’un stock mixte

**Nouveau module.** `etudecas/simulation/lot_trace/materials.py:130` valide chaque allocation par réception ; `:150` propage l’origine à travers les transports ; `:181` contrôle l’appartenance des identifiants aux origines possibles ; `:211` contrôle uniquement le total physique sortant du lot.

Contre-exemple : un stock parent de 100 UN possède deux origines documentées A=50 et B=50. Deux transports de 30 UN créent deux réceptions filles, chacune documentée entièrement A. Le constructeur accepte **60 UN d’origine A pour 50 UN disponibles**, avec trois contrôles de quantité satisfaits. Les quantités physiques globales sont correctes ; l’attribution des origines ne l’est pas.

Le chemin est accessible depuis `lot_trace/payload.py:84` : import optionnel de `material_traceability.json`, puis appel du constructeur `:88`. Cela concerne donc l’enrichissement par données fabricant, et pas seulement un helper isolé. Les métadonnées ont ici une structure valide mais des allocations mutuellement contradictoires. Cette contradiction devrait être refusée ou signalée, au lieu de devenir une attribution documentée acceptée.

**Impact :** recherche inverse et périmètre d’un rappel de lot potentiellement incorrects après division d’un stock d’origines mixtes. **Limite :** aucune occurrence de cet enrichissement fautif n’a été établie dans les résultats nominaux actuels ; pas de preuve de corruption des stocks physiques. P2 pour ce chemin conditionnel, pas P1 généralisé.

**Correction proposée :** contrôler le budget par origine des parents connus sur l’ensemble des sorties, en préservant la part inconnue. Si les allocations ne peuvent pas être prouvées, conserver les origines possibles et refuser la qualification exacte. Ajouter la régression 50+50 → 30A+30A, des cas valides et des parents partiellement inconnus.

Preuve : [counterexamples.py](../../artifacts/testing/audit_since_head_20260920/model/counterexamples.py), clé `origin_overallocation` dans [counterexamples.json](../../artifacts/testing/audit_since_head_20260920/model/counterexamples.json).

### MHEAD-02 — P2 : une réservation seule peut être présentée comme un départ réalisé

**Nouvelle logique de statut.** `etudecas/simulation/lot_trace/payload.py:357` considère indifféremment `lane_ship` et `shipment_reserve` pour le prédicat `dispatched`. À `:361`, le lot sans stock disponible devient « Produit - sorti du stock usine ».

Contre-exemple : production de 100 UN à J0, réservation complète à J1 pour un départ J10 et une réception J12, aucun événement `lane_ship`. Le payload retourne pourtant `pf_availability_status="dispatched"`. Le fait que le stock disponible passe à zéro à la réservation ne prouve pas une sortie physique.

**Impact :** suivi trompeur d’un PF réservé avant départ, particulièrement en fin d’horizon ; confusion entre disponibilité, réservation et localisation physique. **Limite vérifiée :** le balayage des événements du nominal `audited_corrections_20260920` n’a trouvé **aucun** PF produit puis uniquement réservé, sans départ et sans stock final. Le défaut est latent, reproduit sur une fixture minimale ; il ne faut pas le présenter comme un lot nominal actuellement mal affiché.

**Correction proposée :** statut distinct `reserved_pending_departure`, puis `dispatched` seulement sur événement de départ réalisé. Conserver la distinction stock disponible / quantité réservée / stock physique. Tester aussi les réservations partielles et les départs hors horizon.

Preuve : clé `reserved_is_dispatched` dans [counterexamples.json](../../artifacts/testing/audit_since_head_20260920/model/counterexamples.json), CSV [reserved_fixture/events.csv](../../artifacts/testing/audit_since_head_20260920/model/reserved_fixture/events.csv).

### MHEAD-03 — P2 : les paramètres JSON implicites n’invalident pas la reprise Monte-Carlo

**Lacune héritée, non nouvelle régression démontrée.** Le nouveau `etudecas/simulation/source_fingerprint.py:15` parcourt seulement les fichiers `*.py`. Le précédent fingerprint Monte-Carlo était également limité au Python. Son remplacement élargit utilement le périmètre de code, sans résoudre les dépendances de configuration non Python.

Le contrat effectif de `montecarlo/run_montecarlo_analysis.py:146` associe bien le hash du graphe, les paramètres CLI et les fichiers explicitement cités dans les arguments. Cependant `case_config.py:8` et `:116` chargent implicitement `config/cases/data_poc.json`. Ses tarifs de production alimentent notamment `engine/run_first_simulation.py:7148` ; ils ne sont pas nécessairement recopiés dans le graphe ni passés par un argument fichier. Le JSON est absent de `implementation_files`.

La sonde de bout en bout utilise les vrais `build_checkpoint_config`, `checkpoint_fingerprint`, `write_run_checkpoint` et `load_run_checkpoint`, avec un minuscule faux moteur qui lit un JSON adjacent. Après passage du tarif JSON de 1 à 1000, le graphe et les arguments restent identiques : **fingerprint inchangé, checkpoint cost=1 réutilisé, alors que le faux moteur lit désormais1000**. Elle prouve la lacune de contrat de cache ; elle ne prétend pas avoir relancé une campagne réelle ou démontré un cache obsolète dans les livraisons existantes.

**Impact :** reprise potentiellement fondée sur une autre configuration implicite, malgré un graphe et un code Python inchangés. **Correction proposée :** inventorier et hasher les configurations réellement résolues, notamment la configuration de cas active ; transmettre cette empreinte au contrat de reprise. Tester séparément changement du graphe, des arguments fichier, du code et d’une configuration implicite. Éviter d’assimiler empreinte de code et preuve complète de reproductibilité.

Preuves : [execution_and_cache.py](../../artifacts/testing/audit_since_head_20260920/model/execution_and_cache.py), clé `checkpoint` dans [execution-and-cache.json](../../artifacts/testing/audit_since_head_20260920/model/execution-and-cache.json), et clé `json_runtime_dependency_omitted` dans la première sonde.

## Ce qui a été vérifié et ce qui reste borné

- **API et HTTP :** contrats de requête, rejet des champs et facteurs inconnus, types stricts, horizon, origine et hôte locaux, authentification, chemins de fichiers, taille et lecture du corps, concurrence et timeout. Lecture complète des petits modules HTTP et tests ciblés ; aucun contournement établi. Une exploration de processus enfant n’a pas montré de survivant après timeout : ce n’est pas un constat de défaut.
- **Moteur et préparation :** revue des changements de demande réalisée / signal MRP, jours de sécurité, quantités UN, valorisation inconnue, pertes physiques versus demandes rejetées, observation à réception, identités et états des expéditions. Vérification ciblée des aides sémantiques ; aucune répétition d’une simulation lourde. Les grands moteurs principal et pilote ont été examinés par diff et chemins appelants, pas intégralement ligne par ligne. Le pilote garde des conventions historiques ; cette revue ne le certifie pas équivalent au moteur nominal corrigé.
- **Traçabilité et transport :** lecture du nouveau modèle matières, intégration metadata, modifications du payload, index et liens causaux ; estimations logistiques explicitement qualifiées. Les deux contre-exemples ci-dessus ne sont pas couverts par les tests existants qui passent.
- **Prototypes :** revue du refus de promouvoir les candidats scientifiques comme décisions confirmées, des points d’entrée du runner de calibration V2, signatures, verrou, publication atomique, reprise et statuts de confirmation. Les tests d’injection de panne utilisent un faux exécuteur et un plan synthétique annoncé. Ils ne prouvent ni un régime industriel ni la validité de campagnes historiques. La revue du runner de 1443 lignes est ciblée, pas exhaustive.
- **Fixtures historiques :** les tests exigeant des campagnes externes sont maintenant identifiés et soumis à activation explicite. Les fixtures analytiques conservent une provenance et des empreintes ; cela améliore la reproductibilité locale. Un test synthétique vert ne remplace pas les validations historiques désactivées. Les wrappers PowerShell et campagnes externes n’ont pas été exécutés ici.
- **Helpers et format des résultats :** lecture d’`atomic_io`, `provenance`, `reference_status` et du validateur de package. Écriture atomique par fichier, contrôle de hash et intégrité structurelle ne constituent pas une transaction multifichier ou une validation métier complète. Ces limites sont annoncées ; aucun défaut supplémentaire concret établi dans ces modules.
- **Pipeline et Monte-Carlo :** association déclarative des analyses à un run, horizon et refus des analyses historiques partagées incompatibles. L’association par chemin de manifeste n’est pas une signature cryptographique des résultats ; le code le précise. Le problème de dépendance JSON du cache est distinct.

## Couverture, tests et conservation

L’inventaire du périmètre contient **163 fichiers : 47 différences de contenu, 30 nouveaux non suivis et 86 fichiers strictement identiques à HEAD** malgré leur statut Git modifié. Ces 86 cas ne sont pas des différences CRLF : leurs octets sont identiques. Le détail nominatif, le hash et le degré réel de revue figurent dans [coverage.csv](../../artifacts/testing/audit_since_head_20260920/model/coverage.csv) et [coverage.json](../../artifacts/testing/audit_since_head_20260920/model/coverage.json). Certaines modifications de tests n’ont reçu qu’une revue partielle de diff et de contrat ; elles sont indiquées comme telles. Aucun fichier n’est déclaré audité intégralement par le seul fait d’être inventorié.

Deux exécutions ciblées indépendantes de la suite globale du parent :

1. API, HTTP, requêtes, atomicité, provenance, référence documentaire, schéma et calibration atomique V2 : **111 tests + 6 sous-tests passés**, 34,25 s.
2. Matières, affichage logistique, sémantique modèle, format de run, pipeline, sélection d’actions et politique des fixtures historiques : **135 tests + 57 sous-tests passés**, 31,74 s.

Soit **246 tests et 63 sous-tests passés**, sans lancer le moteur réel. Les rapports JUnit [targeted-existing.xml](../../artifacts/testing/audit_since_head_20260920/model/targeted-existing.xml) et [targeted-integration.xml](../../artifacts/testing/audit_since_head_20260920/model/targeted-integration.xml) identifient les cas exécutés. Les scripts des sondes et leur résultat sont conservés séparément des sources de production. Le contrôle final [summary.json](../../artifacts/testing/audit_since_head_20260920/model/summary.json) vérifie les 163 empreintes de source par rapport au début de cette sous-revue.

Priorité de correction proposée : statuts de réservation, conservation par origine avant import de lots fabricants réels, puis dépendances du cache avant une reprise après changement de paramètres implicites. Les hypothèses métier déjà qualifiées — durée physique tau à confirmer, besoin MRP statique, valorisation incomplète — restent des limites connues ; elles ne sont pas rebaptisées ici en nouveaux défauts.
