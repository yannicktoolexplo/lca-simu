# Complément de la carte historique — 15 septembre 2026

La démonstration du 31 août reste intacte. Sa copie enrichie est :

`C:/dev/lca-simu-pr40-validation-artifacts-20260726/DEMONSTRATION_CONTEXTE_AUDITS_FOURNISSEURS_20260915_V3.html`

Dans la carte principale, ouvrir **Criticité fournisseurs**, puis utiliser
le sélecteur **Audit fournisseur**. Les onglets existants donnent accès à la
synthèse, au contexte public, aux trois radars et aux 28 critères. La criticité
simulée précédente reste accessible dans un onglet séparé.

Les calculs utilisent les fonctions déjà présentes dans `risk/supplier_audit.py`.
Les scores locaux, système et globaux ainsi que les rangs des 29 fournisseurs
ont été rapprochés de la carte avant de charger le fichier :

`paired_mrp_vs_v3_all_nodes_full_20260828_v2/canonical_feedback/seed_320270/data/supplier_local_criticality_ranking.csv`

Le classeur fournit un audit renseigné pour `SDC-VD0993480A` et la trame de
28 critères. Les 28 autres profils reçoivent les estimations prévues par la
méthode existante, sans réponses d'audit inventées. Le conflit d'identité déjà
signalé pour l'audit renseigné reste visible ; il n'est pas résolu par cet ajout.

Les sources conservées comprennent 29 profils de contexte et 31 informations
publiques sur 20 fournisseurs. Aucune nouvelle collecte Internet n'a été faite.
L'absence d'information publique vérifiée ne devient pas une absence de risque.
Les coefficients de contexte et les estimations restent indicatifs, non calibrés
par un audit terrain.

Le volet **Sources contexte et audit** permet de télécharger les deux classeurs,
les informations publiques avec leurs URL, les coefficients de contexte et le
classement de référence depuis le fichier HTML autonome.

Le script `enrich_supplier_audit_archive.py` ne lance aucune simulation et ne
réécrit aucun indicateur historique. Il ajoute deux clés de données pour l'audit
et enveloppe les panneaux de criticité existants. Les 43 autres ressources
embarquées restent identiques, dont les autres vues, les données de sensibilité,
les risques et RESILIENCE-SCAN. Le moteur et le template restaurés ne sont pas modifiés.

Un rapport `.audit_addition.json` accompagne le HTML et contient les empreintes
des sources et la couverture. L'empreinte de l'original reste
`f26d4dc0a86c932cd57ac185593b1cf946bbc517859bf232bb3c28584fc26a0b`.

Reproduction depuis la racine du dépôt, en choisissant un nouveau fichier de sortie :

```powershell
python -m etudecas.visualization.maps.enrich_supplier_audit_archive --source <original.html> --ranking <supplier_local_criticality_ranking.csv> --output <nouvelle_copie.html>
```

Les fichiers de sources sont ceux du dépôt restauré. Le script refuse un
classement incompatible ou une sortie existante. Les contrôles ciblés refusent
également un score non fini, une couverture différente et un rang incorrect.

Validation : 8 tests ciblés réussis et validation structurelle du fichier autonome.
Le contrôle Chromium a parcouru les 28 critères des 29 fournisseurs, les trois
radars et le contexte public de trois profils, cinq modes historiques et le
téléchargement de la trame. Aucune erreur JavaScript ; fond de carte vérifié.
Le fond utilise la topographie déjà embarquée, sans requête réseau.

