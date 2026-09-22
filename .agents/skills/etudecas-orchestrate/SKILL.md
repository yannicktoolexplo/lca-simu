---
name: etudecas-orchestrate
description: Organiser une modification Etudecas couvrant plusieurs couches indépendantes et agréger ses preuves locales.
---
Identifier les fichiers et les dépendances avant de déléguer. Utiliser les sous-agents natifs et attribuer une propriété d'écriture disjointe. Ne pas déléguer un travail qui bloque toute progression utile du parent.

Donner à chaque agent objectif, fichiers autorisés et interdits, scénario, données sources, preuve attendue. Explorer reste en lecture seule ; simulation et carte corrigent leur couche ; validator utilise un oracle distinct. Le parent intègre séquentiellement les résultats.

Lire `etudecas/docs/MULTI_AGENT_OPERATIONNEL.md` pour les commandes exactes. Exécuter doctor sur la racine, puis les tests ciblés et la qualification correspondant aux changements. Stabiliser les sources avant ces contrôles. Conserver les manifestes de chaque commande ; agréger avec gate et les types de preuves requis par le livrable. Un gate de tests seuls ne qualifie pas une carte.

Préserver le nominal, les sensibilités séparées, les quantités physiques UN entières et les deux parcours de lots. Ne pas convertir une réussite d'invariant en preuve scientifique. Restituer les preuves, les fichiers modifiés et les limites ; ne pas présenter le mini-kit du pack comme le moteur principal.

