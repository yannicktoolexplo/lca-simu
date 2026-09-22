# Corrections et vérification du simulateur — 18 septembre 2026

Ce document suit les quatorze constats de [l'audit contradictoire](AUDIT_ETUDECAS_2026-09-18_RECONTROLE.md). Il distingue les corrections du code, les résultats recalculés et les hypothèses métier restant à confirmer. Les anciens résultats et leur manifeste sont conservés.

## Corrections réalisées

| Constat | Correction | Vérification |
|---|---|---|
| F01 — généalogie différente selon le lot | Même sélection causale Python pour chaque lot sélectionnable ; suppression du parcours HTML qui reprenait tout l'historique d'un stock partagé | Tests de stocks partagés et contributions partielles ; contrôles Chromium de lots non sélectionnés par défaut |
| F02 — stocks exportés trop tôt | Stocks de fin de journée exportés après tous les mouvements | Rapprochement indépendant CSV/mouvements/registre sur les nouveaux calculs |
| F03 — fractions physiques en UN | Quantification avant toute modification des stocks et du registre ; reliquat conservé dans les prévisions | Demandes de 0,5 exécutées 0/1/0/1 ; UN entiers dans les calculs complets |
| F04 — dérive fournisseur/registre | Même quantité exécutée des deux côtés ; stocks sources fractionnaires en UN refusés ; transit et parents répartis en entiers | Dix unités sur trois jours : 3/3/4 ; transit multiplié par 0,75 : allocations 2/5, total 7 |
| F05 — score à unités incompatibles | Retrait des ratios pertes matière/demande et production intermédiaire/demande ; dimensions exclues indiquées indisponibles | Calcul manuel du score ; invariance au changement kg/g |
| F06 — faux volumes de pertes | Demandes non exécutées séparées des rejets qualité physiques ; pertes détaillées par article et unité | Reconstruction indépendante depuis ordres, réceptions et pertes ; corruption volontaire du résumé rejetée |
| F07 — statut et lisibilité | Un produit sorti du stock usine reste produit ; identité métier séparée des occurrences ; libellés ajustés et vue complète ; compteur client limité aux clients | Statuts et géométrie vérifiés dans Chromium ; capture aval examinée |
| F08 — mode estimé interrompu | Initialisation quotidienne et fonction d'enregistrement placées avant utilisation, moteur canonique et pilote | Modes estimés exécutés ; contrôle statique des noms |
| F09 — scénario inconnu remplacé silencieusement | Identifiant inconnu explicitement refusé | Tests API et appels directs |
| F10 — contrat d'entrée incomplet | Validation du graphe avant exécution ; articles et extrémités connus, quantités/BOM non négatives, nombres finis ; même validation API native/JSON | Cas invalides ciblés et sondes adverses |
| F11 — dépendances absentes du cache Monte Carlo | Empreinte incluant les modules applicatifs frères | Modification d'une dépendance invalidant l'empreinte |
| F12 — facteur de sensibilité ignoré | Facteurs inconnus, booléens, chaînes, non finis et hors contrat refusés | Tests de fautes de clé et de types |
| F13 — reprise d'action incomplète | Contrôle du calendrier, des entrées, des sources, des CSV et des résumés avant réutilisation | Preuve manquante ou modifiée : reprise refusée ; sensibilités finales recalculées séparément |
| F14 — validations du pack | Colonnes et types obligatoires, bornes/poids finis, images effectivement décodées, sortie isolée par exécution, arrêt avant rendu si résultats invalides | Trois exemples exécutés et cas volontairement invalides |

Un défaut supplémentaire a été découvert pendant les nouveaux calculs : attendre un backlog strictement nul pour terminer l'amorçage pouvait exclure les 1 825 jours lorsque les livraisons entières laissent une fraction prévisionnelle. L'amorçage s'arrête maintenant au premier service client ; les pénuries ultérieures restent dans le comparatif. Le test inclut explicitement un reliquat fractionnaire puis une pénurie. Le nombre de jours avec reliquat demeure un indicateur prévisionnel, incluant les fractions, et non un décompte de commandes client en retard.

## Le lot PBATCH-411EC755D7110AE0

Le lot produit à J279 contient **14 400 UN**. La vue complète corrigée conserve **53 événements causaux, 16 lots métier et 24 occurrences de stock**. Elle exclut 5 406 événements étrangers à cette chaîne. Aucun événement de consommation d'une autre campagne ni création d'ancêtre après J279 n'apparaît dans les contrôles.

Son aval est conservé : usine → dépôt, 14 400 ; puis **3 473 + 10 927 = 14 400** vers le client. Les réceptions client complètes contiennent respectivement 13 251 et 13 415 unités, provenant de plusieurs lots : la carte distingue leur total de la contribution du lot sélectionné.

La [capture aval](etudecas/artifacts/testing/corrections_20260918/qualification/browser/LOT-00002658-downstream.png) et la [preuve causale](etudecas/artifacts/testing/corrections_20260918/PBATCH-411EC755D7110AE0-causal.json) permettent de revoir ce cas.

## Résultats et preuves

Les résultats corrigés sont dans `etudecas/simulation/result/_reruns/corrected_map_20260918`. Le nominal et les risques portent chacun sur 1 825 jours ; les sensibilités sont dans des sous-dossiers distincts. Les premiers essais de correction restent identifiés comme `actions_initial_review`, hors livraison courante.

**La [qualification finale](etudecas/artifacts/testing/corrections_20260918/qualification/qualification.json) est réussie** : 62 familles de contrôles indépendants sur chacun des quatre calculs, neuf parcours navigateur et neuf contrôles de lots. Le [rapprochement final](etudecas/artifacts/testing/corrections_20260918/delivery-final.json) vérifie aussi packages, CSV, HTML, diagnostic et intégrité des artefacts d'action.

La comparaison à paramètres constants conserve un service cumulé affiché de 100 % au nominal et de 99,632 % avec risques. Au nominal, 25 762 139 unités entières sont servies, avec un reliquat **prévisionnel** final de 0,9999 ; ce reliquat n'est pas un stock physique fractionnaire. Le coût nominal varie d'environ +1,91 sur 289,5 millions d'unités monétaires du modèle. Ces chiffres ne démontrent pas que la calibration économique ou les risques sont justes.

Les anciennes valeurs globales de « pertes » mélangeaient notamment demandes d'achat non exécutées et unités différentes. Elles ne sont pas interprétables comme des quantités de produit fini ; la comparaison utile est maintenant par article et unité.

Preuves locales dans [corrections_20260918](etudecas/artifacts/testing/corrections_20260918/) :

- `nominal-final-invariants.json`, `risk-final-invariants.json` : contrôles indépendants des CSV.
- `adversarial-final.json` : sondes d'entrées invalides, de cache et de dimensions.
- `final-contracts.log` : 101 tests et 4 sous-tests réussis sur documentation, vérification, diagnostic, actions et pack.
- `unittest.log` : 274 tests exécutés, 2 ignorés.
- `final-targeted.log` : 23 tests ciblés réussis, incluant prévisions fractionnaires et transit entier.
- `documentation-review.json` : références documentaires modifiées après revue, sans réaccepter les signatures scientifiques historiques.
- `reference-preserved.json` : 154 fichiers de référence inchangés ; le seul écart attendu concerne le code moteur corrigé.
- `publication-tests.log` : 43 tests et 4 sous-tests réussis après les derniers ajustements de documentation et de vérification ; `home-check.json` contrôle les douze liens de l'accueil et son encodage.

La suite étendue a terminé en 35 minutes : **2 515 tests réussis, 29 ignorés, 62 sous-tests réussis et un échec**. Cet échec est le refus explicite d'un plan dont la dépendance moteur avait changé pendant l'exécution ; le test repasse isolément après stabilisation des sources (`full-failure-recheck.log`). Le [bilan consolidé](etudecas/artifacts/testing/corrections_20260918/test-summary.json) conserve l'échec initial et sa reprise : il ne présente pas cette exécution comme une suite initialement verte.

Les 29 exclusions comprennent 22 intégrations historiques à activer explicitement, quatre anciennes fixtures hors contrat publiable, un contrôle Node.js indisponible et deux tests longs optionnels. La livraison courante sur cinq ans est contrôlée séparément par les invariants CSV et Chromium ; cela ne requalifie pas les archives historiques.

Le fichier complet du test de signature a ensuite été rejoué : **15 tests réussis**. Le contrôle final de livraison a aussi détecté deux seuils différents pour compter les jours avec reliquat prévisionnel (0,001 côté ancien contrôle CSV, 10⁻⁹ côté HTML). Le seuil est maintenant cohérent à 10⁻⁹, sans changer les quantités physiques ni les tolérances de conservation. **27 tests de livraison/diagnostic passent**, dont les nouveaux cas de petit reliquat et de conservation des diagnostics d'échec. L'échec initial est conservé dans `delivery-counter-mismatch.json` et la qualification indépendante finale est verte ; la première commande de livraison n'est pas présentée comme réussie.

## Vérifier les prochains changements

La [procédure exécutable](etudecas/docs/EXECUTION_VERIFICATION.md) combine des cas calculables à la main, des corruptions volontaires, un rapprochement des CSV indépendant du moteur et un contrôle du HTML dans Chromium hors ligne. La commande de qualification échoue si des preuves obligatoires manquent ou si les invariants ne sont pas respectés. La livraison du diagnostic appelle ce contrôle avant publication ; le workflow CI est configuré pour les régressions et les exemples du pack. Son exécution distante n'est pas revendiquée ici.

La documentation technique et métier est reliée aux fonctions et tests dans neuf domaines. Une dérive des sources métier ou du code impose une revue explicite ; régénérer la documentation n'accepte pas automatiquement cette dérive.

## Limites et décision métier en attente

Le coefficient **0,75** appliqué aux jours de sécurité au dépôt est un défaut du moteur, pas une donnée source. Il a été conservé pour ces comparaisons à paramètres constants. L'application intégrale des jours sources — coefficient 1 — reste en attente de réponse métier. Les données sources de sécurité n'ont pas été remplacées par celles des sensibilités.

Ces vérifications ne certifient pas les données industrielles, les probabilités de risque, les coûts ou toutes les branches des prototypes historiques. Le pilote estimé a été vérifié pour le défaut F08 ; il n'est pas requalifié comme moteur de production. Les signatures historiques divergentes et tests ignorés restent explicitement hors preuve.

Les manifestes des nouveaux calculs indiquent la provenance héritée, la commande réellement rejouée et les empreintes disponibles. Des protections de branches inactives dans le nominal ont été ajoutées après le premier recalcul ; elles sont testées séparément et cette chronologie est conservée. Un ancien cache dont l'empreinte applicative diffère doit être recalculé.

Les deux actions finales ont été exécutées avec le moteur physique courant. Les dernières modifications de vérification et de restitution des erreurs, postérieures à ces exécutions, invalident leur empreinte applicative volontairement conservatrice pour une **future reprise automatique**. Leurs signatures originales restent intactes ; leurs fichiers, leur moteur exécuté et leurs invariants ont été vérifiés pour cette livraison. Aucune signature n'a été modifiée pour forcer une réutilisation.
