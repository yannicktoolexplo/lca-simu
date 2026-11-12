# Parcourir les données industrielles reliées — 12 novembre 2026

L'[explorateur local](../../resultats/donnees_reliees_20261112/explorateur_donnees.html)
relie les sources par article, division et période. Le bouton **Données réelles**
de la [carte nominale](../../resultats/campagne_complete_20261109/carte_nominale_reel_2025.html)
l'ouvre ; le même lien dans une fiche de site transmet la division et la date
de début de la période sélectionnée. Le lien de retour conserve l'accès à la carte.

Choisir un article/site, puis cliquer sur une photo de stock ou une ligne.
La fiche donne fichier, onglet, ligne et cellules, ainsi que les observations,
mouvements, plans MRP et lignes de carnet voisins. Les onglets permettent de
parcourir toute la période, les différentes versions MRP, la demande, les règles
de sécurité, les tailles de lots et les nomenclatures disponibles. Les tableaux
sont paginés ; les points de stock sont représentés sans interpolation.

## Parcours interactif d'une arrivée

La deuxième livraison ajoute une **enquête synchronisée** au même explorateur.
Choisir une matière, un site et une arrivée observée ou prévue. Trois colonnes
montrent ensemble les données amont, le contexte local et le MRP. Un clic sur
un mouvement, un stock, une ligne de carnet ou de plan recentre article, site,
date et contexte ; l'historique permet de revenir à une étape précédente.
L'adresse conserve la ligne sélectionnée et le type de date pour rouvrir
l'étape. Les anciennes entrées par article/site/date restent compatibles.

Une livraison prévue du carnet et sa disponibilité prévue sont deux choix
distincts. Un mouvement hebdomadaire est ancré au lundi de sa période, avec
son repère source du dimanche conservé : ce lundi n'est pas présenté comme
le jour industriel exact d'arrivée. La version MRP par défaut est la dernière
calculée au plus tard à cette borne ; une version explicite reste consultable,
avec avertissement si elle est ultérieure. La vue compare aussi le plan précédent
sur les mêmes semaines et permet de parcourir les prévisions successives d'une
même semaine. Une semaine absente reste inconnue, jamais une entrée nulle déduite.

Le parcours amont repose sur **48 liaisons sourcées** : 29 relations décrites
dans le classeur structurel, 17 rapprochements de contexte FIA/article/site et
deux anciennes relations PF vers Muret réconciliant explicitement 1910 et 1920.
Les trois catégories sont affichées séparément. La coprésence d'un article sur
plusieurs sites ne suffit pas à créer une relation amont. Les routes candidates
001893 et 002612 vers Gaillac sont exclues de ces relations documentées.

Pour 693055 à Avène, le parcours ouvre les mouvements, stocks, plans et carnet
de Gaillac. Les sorties amont restent des candidates à examiner ; ni leur
proximité ni une quantité concordante ne prouvent l'identité de l'expédition.
Les délais prévisionnels FIA de 70 et 10 jours ne sont pas soustraits d'une
arrivée pour inventer un départ réel. Chez les fournisseurs externes, les
historiques opérationnels absents restent inconnus.

Deux ancrages évitent une confusion de site : **movement:1067**, 693055/Avène,
correspond à 1 190 kg au repère du 19 janvier, période du 20 au 27 janvier ;
les 600 kg reçus à Avène sont **movement:1070**, repère du 9 février, période
du 10 au 17 février. La ligne de carnet de 600 kg livrable le 27 janvier est
à Gaillac. Ces trois événements ne sont pas fusionnés.

Le dossier local `etudecas/artifacts/testing/parcours_arrivees_20261112/`
conserve `journey_core.js`, l'UI, l'extraction des liaisons et les preuves
indépendantes de cette deuxième livraison. Les 58 040 lignes opérationnelles
de la première livraison restent identiques ; seules les liaisons sont ajoutées
au jeu embarqué. La carte nominale et ses deux interfaces de lots ne changent pas.

La contre-vérification de cette deuxième livraison passe 23 oracles de cellules,
3 192 contrôles des liaisons et de la conservation du jeu initial, 595 contrôles
du HTML et 376 contrôles V8, dont 343 sur les calculs de contexte et 33 sur la
navigation. Ces derniers exécutent notamment la remontée à un mouvement de
Gaillac, la synchronisation article/site/date/MRP, le retour arrière, la
réouverture par adresse, les deux dates du carnet et le carnet amont lorsque
c'est la seule donnée fournie. Les 34 contrôles DOM de l'auteur passent aussi.
Les manifestes finaux de cette version sont dans `parcours_arrivees_20261112/`.
Leur portée reste une vérification technique en mémoire ; la revue visuelle
dans un navigateur demeure non exécutée.

L'empreinte de la page publiée V2, identique à la candidate vérifiée, est
`b6fb5e31b15f1c29be2dfd28149a69fa4f10585c49022df103506aa9b2d08eb7`.
La publication au chemin existant conserve la première page sous
`parcours_arrivees_20261112/previous_explorer_v1.html`. Les liens de la carte
n'ont pas besoin d'être modifiés.
Le manifeste de publication est
`etudecas/artifacts/testing/parcours_arrivees_20261112/delivery_manifest.json`.
Deux premières attentes du validateur ont été corrigées en lecture seule
(article numérique Excel comparé à une chaîne ; champ `items` du graphe actif
traité initialement comme un champ singulier). Ces refus sont conservés ;
aucune donnée ni règle de navigation n'a été modifiée pour les faire passer.

## Périmètre et conventions

L'extraction couvre **58 040 lignes**, **14 feuilles dans neuf classeurs** :

| Données | Lignes |
|---|---:|
| Photos de stock actualisées | 1 646 |
| Anciennes photos initiales, conservées séparément | 32 |
| Mouvements hebdomadaires signés | 1 319 |
| Plans MRP, 52 dates de calcul distinctes | 53 398 |
| Carnet partiel `Extract_En_cours.xlsx` | 104 |
| Demande historique et versions prévisionnelles | 106 + 1 352 |
| Règles de sécurité, deux fichiers sources | 52 |
| Règles de lots, deux fichiers sources | 7 |
| Lignes de nomenclature disponibles | 24 |

Le fichier partiel est confirmé par l'utilisateur dans cette session. Il donne
livraison prévue et disponibilité prévue, mais aucune date de création ni numéro
d'ordre. Une date prévue après le 1er janvier ne prouve pas une création après
cette date. Les lignes 63 et 66 identiques sont conservées comme deux lignes
source, sans prétendre qu'elles désignent deux ordres industriels distincts.

Les quantités et signes source sont conservés. La lecture convertit explicitement
les grammes en kilogrammes et les ZUN en unités ; les cellules restent traçables.
Une absence reste inconnue. Les unités absentes des règles de lots ne sont pas
inventées. Les noms commerciaux des médicaments ne sont pas intégrés.

La date du calcul MRP reste distincte de la semaine prévue. Une seule version
est sélectionnée à la fois, par défaut la dernière calculée au plus tard à la
date repère. Une sélection explicite postérieure est signalée comme rétrospective.
Les plans datés de 2025 peuvent prévoir 2026 : ils ne représentent pas des
réalisations observées en 2026. Le stock physique MRP reporté dans le futur
est déjà présent mais disponible plus tard, selon la convention confirmée.

Le dimanche des mouvements est un repère hebdomadaire, pas le jour exact d'un
événement. Le rapprochement utilise les photos des deux lundis suivants ; tous
les mouvements signés sont additionnés. Les résidus restent visibles. À Muret,
les sorties de l'export ne sont pas assimilées aux livraisons clients brutes.
Un rapprochement article/site/période ou quantité ne prouve pas l'identité d'un
ordre ni une cause industrielle. La nomenclature décrit une relation théorique,
sans inventer une généalogie réelle de lots.

## Trois parcours de départ

- **693055 / Gaillac / janvier** : ligne de carnet de 600 kg, livraison prévue
  le 27 janvier, disponibilité prévue le 25 février ; entrée prévue de 600 kg
  dans le MRP du 5 janvier et mouvement de 600 kg au repère du 26 janvier ;
  photos passant de 610 à 1 210 kg du 27 janvier au 3 février. Quantité et
  semaine concordent ; l'identité de l'ordre reste inconnue.
- **773474 / Gien / janvier** : du 13 au 20 janvier, les photos augmentent de
  3 206,8 kg. Le mouvement donne −27,2 + 6 400 + 0 − 3 166 = 3 206,8 kg.
  Aucun ordre de cet article à Gien dans le carnet partiel ; ceux de Gaillac
  ne lui sont pas réattribués.
- **268091 / Muret / octobre** : du 13 au 20 octobre, variation de −1 370 unités,
  cohérente avec −435 −935 dans les mouvements. La demande de la semaine est
  de 72 428 unités. Le bilan de stock ne permet pas d'en déduire le service livré.

## Reproduction et preuves locales

Le dossier `etudecas/artifacts/testing/donnees_reliees_20261112/` conserve
le protocole, un ticket commun, les extracteurs, le HTML/CSS/JavaScript,
les candidats assemblés et les contrôles indépendants. La reproduction locale
utilise `extractor/extract.py`, puis `assemble.py` sur une nouvelle livraison
avec les empreintes de référence mises à jour explicitement. Les sorties sont
créées une seule fois ; une reproduction ne remplace pas les preuves existantes.

La comparaison indépendante `validator/dataset_review.json` contrôle chaque
champ et provenance depuis les Excel, sans rappeler l'extracteur évalué.
Les contrôles d'interface et de publication sont référencés par
`delivery_manifest.json`. Les vérifications V8 avec DOM simulé ne remplacent
pas une revue visuelle dans un navigateur ; celui-ci reste non exécuté après
les refus de sécurité antérieurs non levés.

L'état publié passe 1 029 224 contrôles de valeurs/provenance Excel,
59 contrôles directs des cellules des trois exemples, 139 contrôles HTML et
1 205 contrôles V8, dont 37 de navigation et 13 des liens depuis la carte.
Le validateur utilise un oracle indépendant et ne modifie pas le code évalué.
Deux attentes initiales de validation ont été corrigées sans changer l'interface :
pagination essayée sur un plan de 26 lignes au lieu d'un plan de 48 lignes,
et recherche trop large d'un ancien texte de titre au lieu du div visible.
Les rapports refusés sont conservés. Des objets URL bornés sont fournis au
DOM simulé pour exercer réellement les quatre liens de site.

Empreintes SHA-256 de la première livraison : explorateur
`4fd933e19c22e77f13214583a97a0094d1c0b16485de0f84638431e35dc8a0f9` ; carte
`af8d5af3864dcd928c1b48865a15046550801c196149e3d5c9c4ec7ca861a56f`.
Les fichiers publiés à cette étape sont identiques aux candidats vérifiés ; l'ancienne carte
avec dates reste conservée dans le dossier de preuves.

Le nominal, les deux suivis de lots, ses courbes et les observations ajoutées
restent conservés. L'assemblage uniformise les fins de ligne du HTML ; hors des
liens ajoutés, le texte est identique après cette normalisation et les blocs
de données compressés restent strictement identiques. Aucun recalcul n'est lancé et aucune donnée réelle future
n'est injectée dans une décision. Le code applicatif reste gelé à l'empreinte
`236ab838600cdfaa1e1c1f8c01a3b6a175f0991555dec434bcc6c5cc00293946`
pour préserver l'étude annuelle en cours. Cette livraison utilise des adaptateurs
locaux sous artefacts. Leur intégration permanente au générateur attend la fin
de cette étude ; les pages et les données lourdes ne sont pas poussées dans Git.

Restent hors périmètre de ce premier parcours les agrégats financiers de CA et
d'immobilisation, les audits fournisseurs et les scénarios de risques. Leur
simple proximité temporelle ne fournirait pas un identifiant d'ordre commun.
