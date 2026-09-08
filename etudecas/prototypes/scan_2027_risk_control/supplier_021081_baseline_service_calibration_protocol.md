# Protocole additif de calibration des baselines 93 % et 80 %

## Objectif

Construire des états de référence dont le service simulé de 268967 se situe autour de 93 %, puis de 80 %, avant d’appliquer un incident fournisseur. La calibration doit expliquer **par quelle couche physique** la supply est affaiblie; elle ne doit jamais modifier la demande pour fabriquer le résultat.

## Quatre chemins testés séparément

1. **Stock 021081 seul** : stock initial du composant réduit; carnet, stock 773474 et production 773474 inchangés.
2. **Stock 773474 seul** : stocks initiaux de 773474 réduits proportionnellement entre SDC-1450 et M-1430; composant, carnet et production inchangés.
3. **Production 773474 seule** : ordre de production d’ouverture retiré et budget de production 773474 réduit; stocks initiaux et composant inchangés.
4. **Joint** : stock 021081, stock 773474 et budget de production 773474 réduits ensemble.

Le chemin « production » est une ablation technique pour localiser le masque. Il n’est pas présenté comme une recommandation opérationnelle.

## Séquence de calcul

### 1. Screening baseline uniquement

- Une seule graine commune.
- Aucun incident fournisseur.
- Grille de couverture proposée : 720, 540, 365, 300, 240, 210, 180, 150, 120, 105, 90, 75, 60, 45, 30, 15 et 0 jours.
- Pour chaque chemin, mesurer le service à date, le retard cumulé, les lots 268967 libérés, le stock minimum 021081, le stock minimum 773474 et la production 773474 réellement exécutée.

Les résultats du screening démasquage 90/30 sont réutilisés; ils ne sont pas recalculés. Les commandes moteur et les empreintes d’entrée doivent être identiques pour qu’un cas soit déclaré réutilisable.

### 2. Localisation des cibles

- Cibles : 93 % et 80 % de service simulé.
- Tolérance initiale : ±1,5 point de pourcentage.
- La réponse est considérée comme discrète à cause des lots; aucune interpolation linéaire n’est tenue pour vraie.
- Si deux niveaux encadrent une cible, ajouter au plus trois valeurs intermédiaires dans un paquet séparé.
- Si un chemin reste masqué même à zéro, noter « cible inaccessible par ce chemin isolé »; ne pas inventer une valeur.
- Toute baseline inférieure à 75 % est classée trop dégradée pour l’étude d’incident et n’est pas utilisée pour vanter une action corrective.

### 3. Confirmation de la baseline

- Dix graines communes pour chaque candidat retenu.
- Publier moyenne, minimum, maximum et dispersion du service.
- Une configuration n’est retenue que si sa moyenne est dans la tolérance et si son intervalle ne mélange pas les zones 93 % et 80 %.
- Les configurations strictement identiques par empreinte de sortie ne sont pas dupliquées.

### 4. Incidents seulement après calibration

Sur chaque baseline confirmée :

- rendement utilisable à 10 %;
- disponibilité fournisseur à 25 %;
- retenue qualité de 180 jours.

Le premier passage utilise une graine appariée. Les dix répétitions ne sont lancées que pour les incidents qui modifient réellement le service, le retard ou la libération des lots par rapport à la baseline de même graine.

## Garde d’interprétation

- Une baseline à environ 35 % comme `joint_30d` est un état structurellement trop dégradé; elle sert à comprendre les couches, pas à évaluer une action fournisseur.
- Une absence de delta signifie « incident masqué dans cet état testé », jamais « chaîne résiliente ».
- Les 23 commandes de 021081 sont des lignes planifiées du snapshot, pas un historique de livraisons ni un OTIF observé.
- Le ratio 8,94 kg / 1000 g de 773474 reste une unité à valider. Les calibrations littérale et ÷1000 doivent rester deux paquets distincts.

## Sorties attendues

- `baseline_calibration_grid.csv` : toutes les baselines, une ligne par chemin et niveau.
- `baseline_target_candidates.csv` : candidats 93/80, écart à la cible et statut atteignable/inatteignable.
- `baseline_confirmation_summary.csv` : moyenne, dispersion et cas défavorable sur dix graines.
- `incident_delta_screen.csv` : incidents appariés, seulement après baseline saine ou affaiblie maîtrisée.
- `calibration_manifest.json` : provenance, commandes normalisées, empreintes et règles de réutilisation.
- `RESUME_METIER_CALIBRATION_93_80.md` : conclusion en français métier.
