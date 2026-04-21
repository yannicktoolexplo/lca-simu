Snapshot reconstruit a partir des artefacts encore disponibles localement.

But:
- retrouver l'etat visuel/simulation le plus proche du resultat sauvegarde par l'utilisateur
- sans ecraser la baseline active

Source de reconstruction:
- map HTML sauvegardee localement:
  - `C:\Users\yannick.martz\Downloads\Supply Graph POC - Geocoded Map.html`
- assets locaux associes:
  - `C:\Users\yannick.martz\Downloads\Supply Graph POC - Geocoded Map_files`
- donnees/reports copies depuis la baseline active `..._5y` car aucun snapshot complet du 2026-04-20 14:46 n'a ete retrouve dans Git ou sur disque

Limites:
- ce dossier n'est pas un rollback Git exact
- c'est une reconstruction du meilleur etat restituable avec:
  - l'historique du travail
  - le HTML sauvegarde
  - les horodatages disponibles
  - les sorties encore presentes sur disque

Fichiers principaux:
- map reconstruite:
  - `maps/supply_graph_reference_baseline_real_demand_target_calibrated_mrp_lot_policy_recalibrated_5y.html`
- copie du HTML sauvegarde sous son nom d'origine:
  - `maps/Supply Graph POC - Geocoded Map.html`

Interpretation:
- si le rendu attendu est celui visible dans le HTML sauvegarde, ouvrir la map reconstruite ci-dessus
- si un rollback strict a une heure precise est requis, il faudra une vraie sauvegarde externe ou un artefact complet correspondant
