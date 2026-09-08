# Livraison finale V4 — démonstration des risques fournisseurs

## Objet

Ce runbook fabrique un nouvel HTML autonome en français, limité à trois vues. La
livraison est strictement additive : elle lit les preuves déjà calculées mais ne
lance aucune simulation, ne modifie aucun résultat Stage3 et ne change aucun
dossier retenu par l'analyse scientifique.

Le fichier à ouvrir après validation est :

`OUVRIR_DEMONSTRATION_RISQUES_FOURNISSEURS_FINAL_V4.html`

Il est publié avec son manifeste signé :

`OUVRIR_DEMONSTRATION_RISQUES_FOURNISSEURS_FINAL_V4.html.manifest.json`

## Ce que montrent les trois vues

1. **Focus 338929** — deux hypothèses testées séparément sur la voie
   SDC-VD0914360C → M-1810 pour le composant 338929 et le produit 268091 : un
   retard de transport et une quantité livrée inférieure au plan. La vue relie
   l'expédition, les lots matière, les encours, les lots finis et les événements
   clients disponibles dans la trace native. Le cas détaillé est une trajectoire
   illustrative choisie sur l'exposition physique, pas une moyenne ni un nouveau
   classement fournisseur.
2. **Robustesse du réseau** — comparaison des trois niveaux de fonctionnement
   signés (référence, niveau proche de 93 %, niveau proche de 80 %), portefeuille
   complet des dossiers Stage3, sensibilité par voie et 108 courbes nominales
   couvrant exactement 36 sujets métier.
3. **Décisions et limites** — actions réellement testées dans Stage3, refus
   scientifiques, éléments observés en 2025 et limites à conserver dans toute
   présentation client.

## Vocabulaire à employer face à l'industriel

- **Observé** : valeur issue des données industrielles 2025. Elle décrit ce qui
  est présent dans les fichiers fournis ; elle ne prouve pas la cause d'un risque.
- **Simulé** : résultat du moteur sous une hypothèse explicitée. Il ne constitue
  ni un historique réel ni une prévision probabiliste d'occurrence.
- **Signal de priorité** : dossier à instruire en premier au vu des conséquences
  simulées et de leur récurrence. Ce n'est pas une probabilité de défaillance du
  fournisseur.
- **Hypothèse** : incident, niveau de fonctionnement ou action à confirmer avec
  les équipes métier avant toute décision.

## Prérequis obligatoires

Préparer quatre chemins distincts :

- le répertoire de supervision de la livraison Stage3 V3 finalisée ;
- le rapport de clôture indépendant reproduisant cette livraison ;
- la racine du focus 338929 avec le statut public `complete_validated` ;
- une nouvelle racine de sortie V4, extérieure aux trois sources précédentes.

Avant publication client, la revue indépendante du module focus doit être
formellement déclarée **GO**. La V4 ne fige volontairement aucun SHA du code focus :
elle impose son schéma, sa signature et son validateur public, puis recalcule en
lecture seule la graine commune et le prédicat complet d'exposition physique.

Le programme refuse notamment :

- une Stage3 non finale, non signée ou non reproductible ;
- une clôture qui ne conclut pas à la conformité technique, ou qui déclare un
  lancement de moteur ; le verdict métier Stage3 peut rester
  `INSUFFISANT_METIER`, car le focus séparé doit être `complete_validated` et
  apporter la traçabilité lot manquante ;
- un focus seulement planifié, incomplet, altéré ou physiquement non exercé ;
- une sélection Stage3 différente entre le plan signé et l'HTML source ;
- un inventaire autre que 108 séries et 36 sujets nominaux ;
- une racine de sortie imbriquée dans une source ;
- l'écrasement d'une sortie différente ou contenant un fichier étranger ;
- tout chemin Windows, URL externe ou appel réseau dans le document public.

## Construction

Depuis la racine du dépôt, exécuter uniquement le constructeur de livraison :

```powershell
python -m etudecas.prototypes.scan_2027_risk_control.supplier_v8_post_stage3_delivery_v4 build `
  --stage3-supervision-dir "<REPERTOIRE_STAGE3_V3_FINAL>" `
  --closure-report "<RAPPORT_CLOTURE_JSON>" `
  --focus-root "<REPERTOIRE_FOCUS_338929_COMPLET>" `
  --output-root "<NOUVEAU_REPERTOIRE_LIVRAISON_V4>"
```

La commande est « nouveau ou identique » : elle crée atomiquement une nouvelle
racine ; si cette racine existe déjà, son contenu doit être strictement identique.
Elle ne possède aucune option d'écrasement.

Une réussite renvoie un JSON contenant notamment `valid: true`, les SHA du HTML
et du manifeste, `view_count: 3`, `nominal_series_count: 108`,
`nominal_subject_count: 36`, `focus_detail_count: 2` et
`engine_runs_performed: 0`.

## Validation indépendante du paquet

Relancer ensuite la reconstruction en lecture seule :

```powershell
python -m etudecas.prototypes.scan_2027_risk_control.supplier_v8_post_stage3_delivery_v4 validate `
  --stage3-supervision-dir "<REPERTOIRE_STAGE3_V3_FINAL>" `
  --closure-report "<RAPPORT_CLOTURE_JSON>" `
  --focus-root "<REPERTOIRE_FOCUS_338929_COMPLET>" `
  --output-root "<NOUVEAU_REPERTOIRE_LIVRAISON_V4>"
```

Ne transmettre le dossier V4 qu'après cette seconde réponse `valid: true`. Ouvrir
ensuite le HTML directement depuis le disque, couper le réseau et vérifier que les
trois onglets, les sélecteurs, les graphiques et la pagination des lots restent
fonctionnels.

## Inventaire des 108 courbes nominales

L'horizon quotidien brut couvre J0 à J719. Après lissage contractuel, chaque
série validée contient la moyenne, P10, la médiane et P90 sur 30 simulations de
J27 à J719 pour la MM28, ou de J6 à J719 pour la MM7. La moyenne n'est pas
mathématiquement obligée de rester entre P10 et P90. Les 108 séries correspondent
à trois niveaux de fonctionnement appliqués à 36 sujets logiques :

| Domaine | Sujets | Mesures et lissage | Séries physiques |
|---|---:|---|---:|
| Service | global, 268091, 268967 | service à l'heure MM28 ; retard client MM7 | 18 |
| Production | 268091, 268967 | libérée MM28 ; achevée MM28 ; encours MM7 ; stock fini MM7 | 24 |
| Stocks entrants | 18 couples usine–article | stock entrant MM7 | 54 |
| Contraintes | 268091, 268967 | écart au plan de lots MM28 ; jours avec manque d'entrée MM7 | 12 |
| **Total** | **36 sujets** | **3 niveaux par sujet** | **108** |

Les 108 séries quotidiennes sources sont revalidées intégralement. Pour alléger
la page autonome, l'affichage applique d'abord la moyenne glissante contractuelle
(MM28 pour le service et les flux, MM7 pour les autres indicateurs), puis
n'embarque qu'un point hebdomadaire. Cet échantillonnage réduit uniquement
l'affichage dans le navigateur, jamais la validation des données sources.

## Contrôles développeur sans simulation

Ces commandes testent le constructeur et les validateurs sur des fixtures. Elles
ne lancent ni campagne ni moteur :

```powershell
python -m pytest -q etudecas/prototypes/scan_2027_risk_control/tests/test_supplier_v8_post_stage3_delivery_v4.py
python -m ruff check etudecas/prototypes/scan_2027_risk_control/supplier_v8_post_stage3_delivery_v4.py etudecas/prototypes/scan_2027_risk_control/tests/test_supplier_v8_post_stage3_delivery_v4.py
python -m ruff format --check etudecas/prototypes/scan_2027_risk_control/supplier_v8_post_stage3_delivery_v4.py etudecas/prototypes/scan_2027_risk_control/tests/test_supplier_v8_post_stage3_delivery_v4.py
python -m py_compile etudecas/prototypes/scan_2027_risk_control/supplier_v8_post_stage3_delivery_v4.py etudecas/prototypes/scan_2027_risk_control/tests/test_supplier_v8_post_stage3_delivery_v4.py
```

Si Node.js est installé, le test dédié vérifie aussi la syntaxe du JavaScript
embarqué. Dans tous les cas, le parseur statique impose trois vues réelles, des
identifiants HTML uniques et la CSP `connect-src 'none'`.

## Limites à annoncer, sans exception

- Le focus 338929 est demandé pour la démonstration ; il ne modifie pas la
  sélection scientifique Stage3 et ne doit pas être présenté comme le « pire »
  fournisseur.
- Le retard et la réduction de quantité sont deux incidents fournisseurs testés
  séparément. Pour chacun, la page suit la cascade d'effets physiques de
  l'expédition au stock entrant et au lot, puis à la consommation et aux encours,
  au lot fini et au client agrégé. Les incidents simultanés ou corrélés ne sont
  pas testés et ces hypothèses ne sont pas des incidents observés.
- Les détails de lots proviennent d'une réalisation appariée commune. Ils
  illustrent un chemin possible ; les indicateurs agrégés reposent, eux, sur 30
  simulations.
- Une trace partielle signifie que seuls les contacts physiquement reconstruits
  sont affichés. L'absence d'une ligne ne prouve pas l'absence d'exposition.
- Les identifiants de lots des deux simulations sont distincts. Les retards à
  volume cumulé égal ne signifient jamais qu'il s'agit du même lot.
- Aucune capacité, disponibilité de produit fini, retenue qualité, probabilité
  fournisseur, causalité historique, coût, chiffre d'affaires perdu ou ROI n'est
  inventé.
- Les actions affichées sont exclusivement celles déjà testées et signées dans
  Stage3. Si aucune action Stage3 ne porte exactement sur 338929, aucun gain
  d'un autre dossier ne lui est attribué.
- Le document ne démontre pas une régulation en boucle fermée, une analyse
  fréquentielle, des pôles, la contrôlabilité ou l'observabilité du système.
