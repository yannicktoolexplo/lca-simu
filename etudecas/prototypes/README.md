# Recherche autour du simulateur

[Revenir au parcours principal](../README.md)

Les études courantes réutilisent le moteur Etudecas. Commencer par leur besoin
métier, puis par `python -B -m etudecas.simulation.studies MODE --help`.
L'aide décrit les paramètres et prérequis sans lancer de calcul.

| Besoin | Mode courant |
|---|---|
| Cascades d'incidents et comparaison d'interventions | `cascade` |
| Comparaison des configurations de supply chain | `supplier-configurations` |
| Calibration de configurations de service | `supplier-calibration` |
| Comparaison des incidents fournisseurs sur des fenêtres comparables | `supplier-campaign` |

Le [guide des études fournisseurs et cascades](scan_2027_risk_control/README.md)
indique les implémentations, leurs dépendances et leurs limites. Le parcours est :
**plan d'étude → simulations → indicateurs → validation → présentation**.
La sensibilité, le rejeu ciblé et la propagation des incertitudes restent accessibles
par les modes `sensitivity`, `targeted`, `paired` et `temporal` de la même entrée.

## Ce que contiennent les dossiers

| Dossier | Rôle |
|---|---|
| [scan_2027_risk_control/](scan_2027_risk_control/README.md) | Méthodes fournisseurs, cascades, commande et analyse fréquentielle, avec leurs tests. |
| [prediction/](prediction/README.md) | Démonstration de prédiction sur un historique synthétique ; elle ne constitue pas une calibration industrielle. |

La campagne fournisseur courante utilise encore des fonctions issues des versions
précédentes. Il n'est pas nécessaire de lancer chaque version : les différences de
fenêtres, de graines et de validation restent portées par le protocole choisi.
Les calculs communs sont dans `scan_2027_risk_control/supplier_campaign_mechanics.py`.
La publication autonome des HTML utilise
[`visualization/standalone_html.py`](../visualization/standalone_html.py).

Les anciennes publications intermédiaires, moniteurs ponctuels et commandes d'une
exécution passée quittent le code actif après contrôle et sauvegarde. Leurs sources
historiques restent identifiées dans le
[bilan de simplification](../artifacts/testing/human_code_20260925/BILAN.md).
Conserver une capacité ne signifie pas conserver toutes ses anciennes commandes.

Le [plan global](../docs/PLAN_SIMPLIFICATION.md) fixe la cible d'environ 50 fichiers
de code, tests et interface compris. Cette refonte est en cours ; la cible n'est pas
atteinte. Les tests d'altération physique de fichiers sont exclus de la procédure
de vérification après l'incident Sophos.
