# Horizon Adaptation POC

Ce dossier contient un nouveau POC a horizon long terme, distinct du POC court-terme.

Objectif :
- projeter une supply chain sur 20 ans ;
- representer explicitement le rechauffement climatique, les aleas et la rarefaction des ressources ;
- introduire des technologies d'adaptation energetique (solaire, batterie, biomasse) ;
- suivre a la fois les impacts environnementaux et les couts economiques ;
- comparer `LCA classique`, `Time-Dependent DLCA` et `State-Dependent Dynamic LCA`.

Le script principal est :
- `horizon_adaptation_poc.py`

Les sorties sont ecrites dans :
- `outputs/csv`
- `outputs/images`

Les strategies comparees sont stylisees :
- `Reference 2045`
- `Stock de resilience`
- `Autonomie energetique`
- `Adaptation integree`
- `Lean expose`

Le modele est volontairement pedagogique :
- il ne cherche pas a etre un jumeau industriel complet ;
- il cherche a tester jusqu'ou le cadre `state-dependent` peut aller quand on combine climat, operations, energie et cout.
