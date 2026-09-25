# Travail Codex sur Etudecas

Pour une demande Etudecas touchant des couches indépendantes, déléguer explicitement en parallèle à des sous-agents aux périmètres d'écriture disjoints. Pour une correction simple, travailler directement. Le parent conserve l'intégration et la synthèse.

Lire `etudecas/docs/MULTI_AGENT_OPERATIONNEL.md`. Utiliser les profils et skills natifs du projet. Hériter du modèle courant ; ne pas ajouter SDK, service ou appel LLM externe pour orchestrer les outils locaux.

Contrat de délégation : objectif observable, entrées et scénario exacts, fichiers autorisés/interdits, livrable, contrôles attendus. Ne pas lancer deux écritures sur le même fichier. Faire valider une correction métier par un agent distinct utilisant un oracle indépendant. Exécuter les qualifications sur un état stabilisé ; une modification concurrente des sources invalide la preuve.

Préserver les quantités physiques UN entières, les stocks de sécurité sources du nominal, la séparation nominal/sensibilités, et les deux suivis de lots. Distinguer prévu/réservé/exécuté, simulation/observation industrielle, théorie BOM/registre matière, coût opérationnel/approvisionnement externe. Ne pas inventer de donnée industrielle absente.

Décisions utilisateur confirmées : les jours de sécurité suivent lundi-vendredi ; la sécurité dépôt utilise 100 % des jours source. Conserver les références antérieures pour comparaison. `tau_process` reste le paramètre de planification actuel, à confirmer avant de le transformer en durée physique de fabrication.

La toolbox `python -m etudecas.toolbox` fournit doctor, tests ciblés, qualification CSV, navigateur hors ligne, docs et agrégation des preuves. Chaque exécution écrit sous `etudecas/artifacts/testing` dans un dossier unique. Un code retour non nul, une preuve absente ou une empreinte différente interdit de déclarer la vérification réussie. Les invariants ne certifient pas la calibration du modèle.

Le parent restitue changements, tests réellement exécutés, liens des manifestes et limites. Ne pas publier de résultats lourds. Les consignes de rôle limitent l'intention ; elles ne constituent pas une sandbox par fichier.

## Vérifications après l'incident Sophos du 23 septembre 2026

Consigne utilisateur : ne plus exécuter de tests qui altèrent volontairement des fichiers, restaurent leurs dates, simulent leur disparition ou réécrivent en boucle des fichiers factices pour éprouver des contrôles d'intégrité. Ne pas relancer `artifacts/testing/research_triage_20260923/validator/check_source_revision.py` ni une variante de ce test. Conserver les preuves de l'incident pour le service informatique.

Avant de lancer des tests existants, relire les cas sélectionnés et leurs fixtures : ne pas lancer une suite globale susceptible de contenir ces opérations. Privilégier les simulations normales dans un nouveau dossier de résultats, les comparaisons en lecture seule avec les références et les tests de calcul en mémoire. Une vérification exclue reste signalée comme non exécutée ; ne pas la compter comme réussie.

En cas de nouveau refus d'écriture ou d'alerte de sécurité, arrêter les exécutions concernées et diagnostiquer en lecture seule. Ne pas multiplier les sondes d'écriture ni contourner Sophos ; sa gestion relève du service informatique.
