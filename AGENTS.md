# Travail Codex sur Etudecas

Pour une demande Etudecas touchant des couches indépendantes, déléguer explicitement en parallèle à des sous-agents aux périmètres d'écriture disjoints. Pour une correction simple, travailler directement. Le parent conserve l'intégration et la synthèse.

Lire `etudecas/docs/MULTI_AGENT_OPERATIONNEL.md`. Utiliser les profils et skills natifs du projet. Hériter du modèle courant ; ne pas ajouter SDK, service ou appel LLM externe pour orchestrer les outils locaux.

Contrat de délégation : objectif observable, entrées et scénario exacts, fichiers autorisés/interdits, livrable, contrôles attendus. Ne pas lancer deux écritures sur le même fichier. Faire valider une correction métier par un agent distinct utilisant un oracle indépendant. Exécuter les qualifications sur un état stabilisé ; une modification concurrente des sources invalide la preuve.

Préserver les quantités physiques UN entières, les stocks de sécurité sources du nominal, la séparation nominal/sensibilités, et les deux suivis de lots. Distinguer prévu/réservé/exécuté, simulation/observation industrielle, théorie BOM/registre matière, coût opérationnel/approvisionnement externe. Ne pas inventer de donnée industrielle absente.

Décisions utilisateur confirmées : les jours de sécurité suivent lundi-vendredi ; la sécurité dépôt utilise 100 % des jours source. Conserver les références antérieures pour comparaison. `tau_process` reste le paramètre de planification actuel, à confirmer avant de le transformer en durée physique de fabrication.

La toolbox `python -m etudecas.toolbox` fournit doctor, tests ciblés, qualification CSV, navigateur hors ligne, docs et agrégation des preuves. Chaque exécution écrit sous `etudecas/artifacts/testing` dans un dossier unique. Un code retour non nul, une preuve absente ou une empreinte différente interdit de déclarer la vérification réussie. Les invariants ne certifient pas la calibration du modèle.

Le parent restitue changements, tests réellement exécutés, liens des manifestes et limites. Ne pas publier de résultats lourds. Les consignes de rôle limitent l'intention ; elles ne constituent pas une sandbox par fichier.

## Méthode de diagnostic et de calibration métier

1. **Diagnostiquer avant de modifier.** Pour chaque écart, vérifier successivement le périmètre article/site/produits partagés, les unités et conversions BOM, les conventions de semaines et de dates, les stocks et ordres en cours à l'initialisation, puis les bilans physiques, les délais de disponibilité et les règles MRP. Examiner ensuite les aléas sans présumer qu'un écart prouve une erreur du modèle ou un incident industriel. Distinguer entrée en stock, fabrication, libération, transfert et livraison client.

2. **Suivre la propagation dans toute la chaîne.** Évaluer chaque correction depuis le fournisseur ou Gaillac jusqu'à Avène/Gien, Muret et au client. Comparer stocks physiques et utilisables, consommations, fabrications, transferts et service client. Une amélioration locale peut déplacer un écart ; une rupture amont peut être absorbée par les stocks aval. Quantifier ces effets et les éventuelles dégradations.

3. **Rendre le niveau de preuve explicite.** Identifier chaque information comme fait source, reconstruction par calcul, hypothèse ou résultat simulé. Citer fichier, onglet, colonnes ou cellules, période et périmètre ; donner l'équation des reconstructions et leurs limites. Une donnée absente reste inconnue. Une courbe plus proche ne démontre ni une cause industrielle ni une loi probabiliste.

4. **Tester des hypothèses discriminantes.** Avant un essai, préciser l'écart visé, le mécanisme supposé, les paramètres modifiés, les éléments conservés et les résultats qui soutiendraient ou contrediraient l'hypothèse. Isoler d'abord les mécanismes, puis tester leurs combinaisons pertinentes. Consigner le résultat et l'apprentissage, y compris en cas d'échec ; ne pas multiplier les variantes équivalentes sans nouvelle question vérifiable.

5. **Séparer reproduction historique et simulation autonome.** Déclarer quelles données alimentent le calcul et lesquelles servent uniquement à la comparaison. Distinguer les informations connues à la date de décision des observations ultérieures. Toute injection de mouvements réalisés, de réceptions futures observées ou de dates d'incidents choisies après coup doit être identifiée comme rejeu ou scénario rétrospectif ; elle ne valide pas à elle seule un MRP autonome. Les prévisions sources restent des entrées légitimes selon leur date de publication.

6. **Valider des règles communes et reproductibles.** Privilégier des règles paramétrées par les données sources ; justifier les exceptions par une contrainte identifiée. Documenter formules de quantités et de dates, variables unifiées, calendriers et conditions d'application. Tester une règle sur plusieurs références et périodes, dont certaines non utilisées pour son ajustement, à périmètres et dates comparables. Évaluer stocks, quantités et dates d'ordres/réceptions, mouvements et service ; distinguer ratio d'unités livrées et part de CA livré. Ne promouvoir une nouvelle référence qu'après une comparaison explicite des gains, dégradations et limites ; les invariants techniques ne suffisent pas à valider le comportement industriel.

## Efficacité et continuité du travail

- **Lire de façon ciblée.** Rechercher d'abord les fichiers, fonctions, références et colonnes pertinents. Pour les gros CSV, classeurs et journaux, extraire des agrégats, quelques exemples et les anomalies ; éviter les chargements en contexte et sorties d'outils intégraux. Regrouper les lectures indépendantes et limiter les sorties à ce qui permet une décision.
- **Maintenir un point de reprise court.** Dans le suivi existant, conserver la référence actuelle, les résultats décisifs, les problèmes ouverts, les liens vers les preuves et la prochaine expérience. Actualiser ce suivi plutôt que multiplier les comptes rendus et fichiers Markdown. Garder les détails volumineux dans les artefacts locaux.
- **Réutiliser les travaux compatibles.** Avant de refaire une extraction, une analyse ou une simulation, rechercher un résultat existant et vérifier code, données, paramètres et conventions. La réutilisation des preuves reste soumise aux empreintes et contrats de validation ; une preuve incompatible ne devient pas valide par simple proximité des résultats.
- **Déléguer sans doublonner.** Pour les couches indépendantes, conserver la délégation prévue plus haut ; chaque agent reçoit une question précise, un périmètre disjoint et le contexte nécessaire. Éviter les explorations redondantes et les délégations de tâches triviales. Les retours contiennent conclusion, chiffres décisifs, fichiers modifiés, preuves et limites, sans recopier les journaux ni l'historique complet.
- **Augmenter progressivement le coût des essais.** Lorsque pertinent, commencer par un calcul manuel ou en mémoire, puis un scénario ciblé, une année complète et enfin cinq ans ou une campagne de sensibilité. Vérifier le fonctionnement et le coût de la baseline avant de lancer une campagne ; chaque étape doit répondre à une question supplémentaire.
- **Vérifier qu'un essai agit réellement.** Si plusieurs variantes donnent les mêmes courbes, contrôler dans les entrées et traces exécutées que les paramètres atteignent le moteur et que le mécanisme ciblé est sollicité. Examiner les stocks tampons et les compensations avant de lancer d'autres variantes ; une absence d'effet peut être un résultat métier valide.
- **Conserver les apprentissages négatifs.** Tenir dans le suivi existant un registre concis des questions non résolues et des hypothèses soutenues, réfutées ou indécidables, avec périmètre et preuve. Ne pas présenter une ancienne piste comme une découverte ; la rouvrir seulement si une nouvelle donnée ou un changement pertinent le justifie.
- **Économiser le contexte sans écourter le travail utile.** Privilégier des synthèses et des liens vers les preuves. Ne pas imposer un plafond arbitraire de tokens qui interromprait une investigation nécessaire, ni supprimer des vérifications requises pour réduire le coût.

## Skills métier et suivi des investigations

Pour rechercher l'origine d'un écart de stock, de flux ou de service, utiliser [etudecas-supply-diagnose](.agents/skills/etudecas-supply-diagnose/SKILL.md). Pour départager les causes par des essais MRP ou des aléas, utiliser [etudecas-supply-calibrate](.agents/skills/etudecas-supply-calibrate/SKILL.md). Le parent orchestre les couches indépendantes avec le skill existant `etudecas-orchestrate` et tient un registre léger selon le [contrat des tickets](.agents/skills/etudecas-supply-diagnose/references/tickets.md). Les agents retournent des résultats et propositions de mise à jour ; le parent seul édite ce registre. Un symptôme expliqué par une contrainte immédiate ne démontre pas encore la cause de cette contrainte.

## Vérifications après l'incident Sophos du 23 septembre 2026

Consigne utilisateur : ne plus exécuter de tests qui altèrent volontairement des fichiers, restaurent leurs dates, simulent leur disparition ou réécrivent en boucle des fichiers factices pour éprouver des contrôles d'intégrité. Ne pas relancer `artifacts/testing/research_triage_20260923/validator/check_source_revision.py` ni une variante de ce test. Conserver les preuves de l'incident pour le service informatique.

Avant de lancer des tests existants, relire les cas sélectionnés et leurs fixtures : ne pas lancer une suite globale susceptible de contenir ces opérations. Privilégier les simulations normales dans un nouveau dossier de résultats, les comparaisons en lecture seule avec les références et les tests de calcul en mémoire. Une vérification exclue reste signalée comme non exécutée ; ne pas la compter comme réussie.

En cas de nouveau refus d'écriture ou d'alerte de sécurité, arrêter les exécutions concernées et diagnostiquer en lecture seule. Ne pas multiplier les sondes d'écriture ni contourner Sophos ; sa gestion relève du service informatique.
