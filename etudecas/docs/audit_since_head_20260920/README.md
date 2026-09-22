# Audit des fichiers ajoutés ou modifiés depuis le dernier commit

**La revue est terminée avec douze constats prioritaires : deux P1, neuf P2 et un P3.**
Les ajouts apportent une meilleure séparation des vues, des contrats et des
preuves. Des défauts subsistent dans les raccordements de livraison, la
traçabilité sur certaines entrées et la reproductibilité des vérifications.
Ils doivent être corrigés avant de présenter l'ensemble comme prêt à reprendre
sur un autre poste. Cette passe ne démontre pas que la simulation nominale
et la carte déjà qualifiées sont globalement erronées.

Référence : `f95b1db6bb233cbf9750fc6ab2fda3943d6e82ab`, commit du 15 septembre
2026. Inventaire figé le 20 septembre avant les écritures de cette revue.
Trois agents ont travaillé sur des périmètres disjoints ; le parent a contrôlé
l'inventaire, la conservation, le versionnement et la synthèse. **Aucun code
de production ni résultat de simulation n'a été corrigé pendant cette passe.**

## Portée exacte

| Ensemble | Nombre | Traitement |
|---|---:|---|
| Nouveaux fichiers non suivis et non ignorés | 265 | Inventaire, empreinte, revue de profondeur indiquée et proposition de conservation |
| Fichiers suivis avec différence de contenu | 72 | Diff depuis HEAD, revue ciblée et tests selon le domaine |
| Autres fichiers signalés modifiés | 86 | Octets comparés directement aux blobs HEAD : strictement identiques |
| Total non ignoré dans la baseline | 423 | Une ligne nominative de couverture par fichier ; tous conservés inchangés |
| Fichiers ignorés datés après le commit | 2 629 | Inventaire de métadonnées, environ 30,19 Go ; sélection des scripts et preuves utiles |

Git permet d'identifier les chemins absents de HEAD, pas d'en attribuer l'auteur
ni de prouver leur date de création. Les dates des fichiers ignorés constituent
un indice, pas un historique Git. Les fichiers créés pour cet audit sont exclus
de ces compteurs.

La [couverture fichier par fichier](../../artifacts/testing/audit_since_head_20260920/coverage.csv)
indique propriétaire de revue, méthode, empreinte et contrôles mécaniques.
Les gros moteurs, le constructeur HTML et son template ont été examinés par
diff, contrats et chemins ciblés ; ils n'ont pas été relus intégralement ligne
par ligne. Certains documents historiques ont seulement reçu une lecture
partielle et des contrôles de structure/liens. **Inventorié ou parsé ne signifie
pas validé métier.**

## Constats à traiter

P1 signifie ici correction à traiter en premier pour rendre la chaîne de
vérification exécutable ; P2, défaut conditionnel ou protection incomplète ;
P3, documentation opérationnelle à remettre à jour. Chaque sous-rapport
donne les fichiers/lignes, la reproduction, la portée et le correctif attendu.

| Priorité / identifiant | Constat et conséquence | Preuve / portée |
|---|---|---|
| P1 — T-01 | La CI et la recette de tests n'installent pas Playwright/Chromium alors que les tests navigateur sont collectés. | Échec de collecte reproduit en isolant l'absence de la dépendance ; workflow inspecté, sans exécution GitHub. [Détail](tooling.md#t-01--p1--la-ci-collecte-des-tests-playwright-sans-installer-playwright-ni-chromium) |
| P1 — MAP-01 | La livraison décisionnelle appelle le contrôle des lots sans les CSV sources désormais requis : faux échec de livraison. | Navigateur réel sur la carte livrée : huit contrôles réussis, un refus pour oracle absent. [Détail](map.md#map-01--p1--le-parcours-de-livraison-omet-les-sources-exigées-par-son-contrôle-des-lots) |
| P2 — MHEAD-01 | L'origine fabricant peut être surallouée entre réceptions filles : 60 UN attribuées à A alors que le parent contient 50 A. | Contre-exemple sur le constructeur réel ; aucune occurrence nominale fautive établie. [Détail](model.md) |
| P2 — MHEAD-02 | Une réservation totale peut suffire à afficher « sorti du stock usine », avant tout départ physique. | Fixture minimale ; aucun PF nominal répondant à ce cas trouvé. [Détail](model.md) |
| P2 — T-02 | Le gate des tests peut rester vert après modification d'une fixture CSV absente des empreintes. | Vrais tests et gate dans une racine isolée : ancien gate accepté, test rejoué en échec. [Détail](tooling.md) |
| P2 — MAP-02 | Le rafraîchissement matière peut mélanger UN/KG et deux scénarios malgré une garde de provenance positive. | Contre-exemple exécuté via l'utilitaire ; aucun mélange constaté dans la carte livrée. [Détail](map.md) |
| P2 — MAP-03 | Des quantités physiques vides deviennent zéro et peuvent produire « Bilan physique rapproché ». | Helper du builder reproduit ; la qualification CSV indépendante rejette déjà les valeurs vides. [Détail](map.md) |
| P2 — MAP-04 | Une tolérance d'arrondi des coûts trop étroite peut refuser un résultat arithmétiquement valide. | Contre-calcul appliqué à la comparaison réelle ; aucune erreur économique nominale démontrée. [Détail](map.md) |
| P2 — MHEAD-03 | Une configuration JSON chargée implicitement n'invalide pas le cache Monte-Carlo. | Contrat de checkpoint réel et faux moteur minimal ; lacune héritée, aucune campagne actuelle déclarée périmée. [Détail](model.md) |
| P2 — T-03 | Les contrats natifs et les tests de toolbox ne sont pas couverts correctement par les filtres/commandes CI. | Inspection des chemins et sélecteurs, sans lancer de PR. [Détail](tooling.md) |
| P2 — V-01 | Des oracles et leurs preuves restent seulement dans un dossier ignoré : un futur checkout sera incomplet pour reproduire l'audit. | 49 scripts d'audit/livraison locaux, plus 40 copies de sources d'un essai isolé ; 100 liens vers des preuves ignorées. [Détail](inventory_and_versioning.md) |
| P3 — T-04 | La documentation de couverture annonce neuf registres au lieu de onze et une absence d'import moteur devenue inexacte. | Catalogue, `check-all`, workflow et imports confrontés. [Détail](tooling.md) |

Les constats ne sont pas tous de nouvelles régressions : le défaut de dépendance
JSON du cache est hérité ; la conservation des preuves est une lacune de
transmission. Les préconditions et points secondaires sont conservés dans les
sous-rapports, sans les transformer artificiellement en défauts du nominal.

## Ce qui est solide et ce qui a réellement été vérifié

Les vues de lots détaillée et simplifiée restent distinctes. Les transports
partagés ne sont pas assimilés à des consommations communes. Les mélanges
conservent des bornes lorsque l'origine exacte manque. Les contrats d'entrée,
la séparation des scénarios, les exports de preuve et les tests de refus
constituent des bases utiles à poursuivre. Les neuf fichiers de déploiement
natif correspondent à leurs copies racine ; les onze registres documentaires
sont synchronisés.

| Exécution de cette revue | Résultat | Preuve |
|---|---|---|
| Moteur/API/prototypes, suite ciblée 1 | 111 tests et 6 sous-tests réussis | [JUnit](../../artifacts/testing/audit_since_head_20260920/model/targeted-existing.xml) |
| Moteur/traçabilité/intégration, suite ciblée 2 | 135 tests et 57 sous-tests réussis | [JUnit](../../artifacts/testing/audit_since_head_20260920/model/targeted-integration.xml) |
| Carte, décision et vérificateurs | 275 tests et 3 sous-tests réussis | [JUnit](../../artifacts/testing/audit_since_head_20260920/map/tests.xml) |
| Documentation, toolbox et pack | 64 tests et 4 sous-tests réussis | [JUnit](../../artifacts/testing/audit_since_head_20260920/tooling/targeted.xml) |
| Catalogue documentaire | Onze registres synchronisés | [Journal](../../artifacts/testing/audit_since_head_20260920/tooling/docs-check.log) |

Les contre-exemples sont conservés séparément des tests existants : ces derniers
peuvent tous réussir sans détecter les défauts nouvellement exposés. Les refus
volontairement reproduits ne sont ni masqués ni comptés comme des tests produit
réussis. La vérification de structure `doctor` et son gate ne valent pas
qualification du simulateur ; leurs manifestes sont référencés dans la synthèse.

Les contrôles transversaux ont lu 501 fichiers texte et analysé la syntaxe de
312 Python, 70 JSON, quatre YAML et onze TOML. Les 827 liens Markdown locaux
inspectés ont une cible présente ; neuf suffixes de ligne restent dépendants
du lecteur. Il n'y a pas eu de nouvelle grande simulation ni d'exécution CI
distante. Le code tiers minifié, les environnements et tous les gros résultats
ignorés n'ont pas fait l'objet d'une relecture intégrale.

La carte finale conserve le SHA-256
`51a019257f42ae3909ee17d87a3943d3a0b87f6da0f65e41325cf9d5a210a10f`.
Le rapprochement numérique antérieur reste attaché à cet artefact identique ;
il n'est pas présenté comme recalculé pendant cette nouvelle passe.
Le lot signalé conserve **1 835 + 12 565 = 14 400 UN** dans ce nouveau nominal.
L'échec MAP-01 porte sur l'absence de source de comparaison, pas sur cette somme.

## Ordre de correction recommandé

1. **Rendre les vérifications exécutables de bout en bout** : dépendances CI et
   navigateur, transmission du run au contrôle des lots, couverture native/toolbox.
2. **Sécuriser le sens métier du suivi** : réserver/départ distincts, conservation
   des quantités par origine, refus des mélanges d'unités/scénarios et des mesures
   vides qualifiées à tort.
3. **Compléter l'identité des preuves** : fixtures externes du gate et configurations
   implicites des checkpoints, avec tests de modification/ajout/suppression.
4. **Aligner les oracles numériques** : bornes d'arrondi dérivées de chaque chaîne
   de calcul ; conserver les corruptions volontaires effectivement refusées.
5. **Préparer un ensemble transmissible** : scripts réutilisables versionnés,
   archives de résultats séparées et identifiées, documentation actualisée.

Chaque correction devra ajouter le cas qui échoue ici, puis repasser les tests
ciblés et le contrôle indépendant adapté. Un recalcul lourd n'est nécessaire
que si le comportement de simulation ou les données changent. Les sources
de sécurité du nominal et les conventions métier confirmées restent la référence.

Le [plan de conservation fichier par fichier](../../artifacts/testing/audit_since_head_20260920/versioning-plan.csv)
couvre les 265 nouveaux chemins. Il propose notamment de garder locaux les
28 fichiers d'exemples générés du pack ; les neuf doublons du déploiement natif
sont intentionnels. **Aucun nettoyage, staging ou commit n'a été effectué.**

## Livrables et traçabilité de la revue

- [Inventaire, conservation et limites Git](inventory_and_versioning.md).
- [Moteur, API, traçabilité et prototypes](model.md).
- [Carte HTML, décision et vérificateurs](map.md).
- [Toolbox, pack, documentation et CI](tooling.md).
- [Synthèse machine, preuves et empreintes](../../artifacts/testing/audit_since_head_20260920/audit-summary.json).
- [Couverture nominative complète](../../artifacts/testing/audit_since_head_20260920/coverage.json).
- [Conservation des 423 fichiers de baseline et de HEAD](../../artifacts/testing/audit_since_head_20260920/preservation.json).

Les preuves de cette revue restent locales sous `artifacts`, comme annoncé dans
V-01. Ce rapport distingue leur présence actuelle de leur future conservation
hors de ce poste ; il ne prétend pas avoir déjà résolu ce point.
