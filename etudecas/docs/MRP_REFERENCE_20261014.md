# Référence MRP courante — 14 octobre 2026

La référence courante est `coherent-MRP-20261014`. Elle regroupe dans
`etudecas/config/mrp_reference_20261013/` le graphe, les paramètres du moteur,
le profil des usages partagés et les seuils fournisseurs nécessaires au rejeu.
Elle ne dépend d'aucun ancien dossier de résultats ou d'artefacts de travail.

Le parcours courant est :

```powershell
python -B -m etudecas.regenerate --reference current --days 1825 --with-map --output-dir <nouveau_dossier>
```

Le mode prospectif par défaut est `coherent_scenario`. Les observations et
comparaisons industrielles restent limitées à 2025. Les années suivantes sont
un scénario déclaré, avec reconduction saisonnière et croissance ; elles ne
sont pas présentées comme des observations.

## Livrables conservés

- carte courante :
  `etudecas/resultats/corrections_5ans_20261014/carte_simulation_5ans_corrigee.html` ;
- référence antérieure :
  `etudecas/resultats/corrections_5ans_20261014/reference_corrigee.html` ;
- règles actives : `etudecas/docs/REGLES_MRP.md` ;
- historique des essais et décisions :
  `etudecas/docs/archive/MRP_EXPERIENCES_2025.md`.

## Vérifications exécutées

- simulation normale de 1 825 jours :
  `etudecas/artifacts/testing/final_mrp_cleanup_20261014/simulation/coherent_1825_capacity20_v2/run_manifest.json` ;
- qualification indépendante du run et de la carte :
  `etudecas/artifacts/testing/final_mrp_cleanup_20261014/qualify-e228f53c8a9e4c8bb59b1edf3b4ea518/manifest.json` ;
- 18 tests ciblés sur le bundle, la projection, les usages partagés, la
  provenance Scan3 et la réponse client :
  `etudecas/artifacts/testing/final_mrp_cleanup_20261014/tests-870279a773cf4e90ab3dd03b4b58b766/manifest.json` ;
- test du bundle autonome après déplacement du dernier CSV historique :
  `etudecas/artifacts/testing/final_mrp_cleanup_20261014/tests-b81a57499a3b472c8c05d9a5fe012f70/manifest.json` ;
- rejeu autonome de 14 jours :
  `etudecas/artifacts/testing/final_mrp_cleanup_20261014/simulation/self_contained_smoke_14d/run_manifest.json`.
- diagnostic de l'environnement et des outils :
  `etudecas/artifacts/testing/final_mrp_cleanup_20261014/doctor-f97c5871782c45038277b3a705658f64/manifest.json`.

L'empreinte SHA-256 de la carte livrée est
`a6cde094039b25c47e3516f5d3e217e833d3714d3693cee3dd88b839061a12a2`.
La qualification vérifie les invariants CSV et les charges utiles HTML. Le
navigateur n'a pas été relancé après le précédent refus de sécurité ; aucune
validation d'interaction visuelle n'est donc revendiquée. Ces contrôles ne
certifient pas à eux seuls la calibration industrielle du modèle.

## Nettoyage

Les anciens CSV, cartes et campagnes intermédiaires ont été retirés des
résultats courants. Les artefacts de travail sont passés d'environ 80 Go à
1,40 Go après ajout des preuves finales. Le dossier de preuve de l'incident
Sophos du 23 septembre 2026 est conservé sans modification.
