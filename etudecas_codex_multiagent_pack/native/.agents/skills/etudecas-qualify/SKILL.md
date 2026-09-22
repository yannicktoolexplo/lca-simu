---
name: etudecas-qualify
description: Vérifier une modification du moteur Etudecas ou un calcul livré par tests ciblés et invariants CSV indépendants.
---
Identifier le manifeste et le graphe préparé du calcul exact, puis ses entrées source. Séparer nominal et actions ; ne pas remplacer la sécurité nominale par une sensibilité.

Utiliser `python -m etudecas.toolbox tests --path chemin/test_module.py` et `python -m etudecas.toolbox qualify --run chemin_du_calcul`. Les résultats sont écrits dans un nouveau dossier de preuves. Ajouter `--html chemin_carte.html` seulement lorsque le HTML correspond au calcul qualifié ; un contrôle de rendu ne démontre pas ce lien à lui seul.

Compléter les invariants existants par un cas calculable indépendamment : demande datée inchangée par lissage prévisionnel, valeur économique invariante sous conversion KG/G, UN physiques entières, délai observé connu à la décision. Ne pas réutiliser le helper de production comme seul oracle.

Lire `etudecas/docs/MULTI_AGENT_OPERATIONNEL.md` pour agréger les manifestes. Rejeter les preuves absentes, altérées ou produites pendant une mutation du code. Rapporter séparément conformité aux conventions programmées et validité industrielle encore non démontrée.

