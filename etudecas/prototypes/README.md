# Prototypes et recherche

[Organisation du projet](../README.md)

| Dossier | Rôle |
|---|---|
| `prediction/` | Démonstration de prédiction fournisseur sur des données synthétiques. |
| `scan_2027_risk_control/` | Protocoles, campagnes, calibrations, contrôles et outils de présentation de recherche, avec plusieurs générations de code et leurs tests. |

Le conditionneur d'archives HTML a été déplacé dans
[`visualization/standalone_html.py`](../visualization/standalone_html.py).
`scan_2027_risk_control/standalone_single_html.py` est désormais un relais vers
ce module commun. L'enrichisseur d'audit fournisseur importe directement le
nouvel emplacement ; les anciennes commandes de recherche restent compatibles.

Les autres familles de recherche gardent leurs commandes, configurations et
références historiques. Les suffixes de version ne suffisent pas à décider
quelle génération est remplaçable. Le rangement du module partagé ne déplace
ni les campagnes ni leurs résultats et ne fusionne pas leurs implémentations.
