---
name: etudecas-map-review
description: Vérifier les payloads et interactions de la carte HTML Etudecas avec rapprochement numérique et navigateur hors ligne.
---
Identifier le HTML exact, son scénario, son empreinte et les CSV réellement lus. Préserver le suivi détaillé et le nouvel explorateur ; ne pas confondre leurs couvertures.

Exécuter `python -m etudecas.toolbox browser --html chemin_carte.html`, puis les tests ciblés via toolbox. Pour les lots, utiliser aussi la qualification avec `--run` et `--html` lorsque leur provenance commune a été vérifiée. Les captures et logs restent dans le dossier de preuves unique.

Contrôler particulièrement les périodes des cartes et graphiques, les unités séparées, consommations physiques/théoriques, départs/réceptions, coûts opérationnels/externes et l'accès effectif aux onglets. Une valeur présente dans le payload n'est pas nécessairement visible. Un backlog concomitant ne prouve pas un impact causal.

Le navigateur automatisé couvre les interactions prévues par le script, pas tous les contrôles visuels ou utilisateurs. Ajouter une reproduction ciblée si le défaut sort de ce périmètre. Lire `etudecas/docs/MULTI_AGENT_OPERATIONNEL.md` pour agréger les preuves et expliciter les limites.

