# Consulter les résultats ou les recalculer

Les HTML à conserver sont dans [resultats](../resultats/), accessibles par
l'[accueil](../index.html). Ils embarquent leurs données de consultation.
Les anciens dossiers de calcul sont supprimés conformément au choix de conservation
du 22 septembre 2026 ; les données sources et les programmes restent disponibles.

## Ce qui est réellement reconstructible

Il faut distinguer **refaire un HTML à partir de résultats calculés** et
**recalculer ses résultats depuis les entrées du modèle**. Une copie autonome
ou une simulation courte réussie ne démontre pas, à elle seule, les deux.

| Document | Reconstruction de la présentation | Recalcul des résultats |
| --- | --- | --- |
| 01 — Démonstration complète | Réassemblage depuis le seul HTML, neuf vues et 50 ressources : résultat identique octet par octet. | Plusieurs campagnes historiques ; deux moteurs historiques recherchés pour 01/03 restent introuvables. Le commit déclaré avait des modifications locales. |
| 02 — Carte récente et lots | La commande `--delivery lots` rassemble les quatre calculs, les comparaisons et le diagnostic autonome. | Quatre recalculs de 1 825 jours effectués : 124 fichiers et 47 sections de la carte concordent avec la référence. |
| 03 — Configurations de supply chains | HTML reconstruit à l'identique depuis ses tables embarquées, sans dossier externe. | Graphe, profil exact et entrées retrouvés ; version exacte du moteur non retrouvée. Le code courant ne remplace pas cette preuve historique. |
| 04 — Criticité selon la configuration | Réassemblage identique depuis les données embarquées. | Campagne préliminaire : une seule graine. Les essais du moteur actuel montrent que la calibration historique doit être requalifiée. |

Les présentations 01, 03 et 04 se réassemblent désormais **sans le dossier de recherche
externe**, à partir de leurs données embarquées. Le contrôle a explicitement interdit
les lectures des anciennes racines pendant la reconstruction. Les trois HTML reconstruits
sont identiques octet par octet. Il s'agit d'une restauration des présentations et des
résultats enregistrés, pas d'une nouvelle exécution des modèles historiques.

Les entrées historiques effectivement retrouvées sont regroupées dans
[config/reproduction_historique](../config/reproduction_historique/) : un ZIP compact
pour 01/03 et son manifeste, avec les empreintes et les lacunes explicites ; un second
ZIP conserve les intrants de la comparaison fournisseurs. Les 14
entrées déclarées par le manifeste de la démonstration sont localisées à l'identique.
Cela ne ferme pas la dépendance aux versions manquantes du moteur.

La recherche a couvert l'historique Git, les reflogs, les objets non référencés et les
sauvegardes locales examinées, en vérifiant également les variantes de fins de ligne
Windows/Unix. Les journaux de travail du projet ont également permis de reconstruire
des versions intermédiaires, sans atteindre les deux empreintes exactes attendues.
Ces candidats ne sont donc pas présentés comme les moteurs recherchés.
Les manifestes historiques déclarent un arbre de travail modifié :
restaurer le commit seul ne suffit pas. Une autre sauvegarde contenant ces versions
serait nécessaire pour revendiquer leur recalcul exact ; sinon, recalculer une nouvelle
étude avec le moteur corrigé et conserver son identité distincte.

Les quatre HTML de `resultats/` restent à conserver : un clone du code seul ne contient
pas ces archives de présentation, actuellement ignorées par Git. La fonction de
réassemblage exige le HTML source ; elle ne peut pas reconstituer des résultats
historiques dont on aurait supprimé à la fois l'archive et les entrées exécutables.

## Recalculer les CSV de la référence actuelle

### Comparaisons des stocks et du MRP en 2025

La carte `resultats/02_carte_lots_recente.html` dispose d'un bouton
**Comparaisons 2025** : stocks observés/simulés, besoins MRP, entrées/sorties,
production/service et écarts. Les deux suivis de lots restent disponibles.
Les photos de stock et les plans proviennent des deux classeurs `Flow_Data_*.xlsx`.
Les prévisions MRP restent distinctes des mouvements exécutés ; une absence de
semaine ou de série n'est jamais remplacée par zéro.

Pour reconstruire cet ajout à partir des classeurs et de trois nouveaux calculs :

```powershell
python -B -m etudecas.regenerate --delivery comparaison_2025
```

La commande exécute le nominal et deux diagnostics distincts sur 338929 : retrait
du besoin statique seul, puis activation explicite du mode dynamique. Le nominal
et ses règles sources ne sont pas modifiés. Chaque calcul conserve par défaut
1 825 jours ; les courbes ajoutées comparent uniquement 2025. Les invariants CSV
sont contrôlés. La commande ne revendique pas de validation navigateur : celle-ci
reste à exécuter sur le HTML livré.

Le fichier obtenu est `maps/02_carte_lots_recente.html` dans le nouveau dossier
de calcul. Les anciennes vues sont conservées à partir de la carte existante,
prise comme entrée ; elles ne sont pas recalculées par cette commande.
`--base-map CHEMIN_HTML` permet de choisir une carte nouvellement produite par
`--delivery lots`. La carte conservée n'est pas écrasée par la commande.
Les ajouts de comparaison antérieurs sont remplacés dans la nouvelle sortie,
sans dupliquer les boutons. Conserver la carte source demeure nécessaire.

Deux fichiers portent cette fonctionnalité :
`visualization/maps/source_comparison.py` rapproche les données et
`visualization/maps/source_comparison_view.html` affiche les courbes sans réseau.
L'assemblage réutilise `portable_diagnostic.py`. Les templates HTML applicatifs
sont inclus dans les nouvelles capsules de sources ; les petits fichiers
temporaires de verrouillage Excel `~$…` en sont exclus, sans être modifiés.

Les diagnostics utilisent une seule graine et ne sont pas des remplacements
calibrés du nominal. Les stocks totaux des sources peuvent inclure des statuts
industriels non décrits ; les deux alignements ouverture/clôture sont proposés.

### Simulation seule ou livraison des lots

Depuis la racine du dépôt :

```powershell
python -m etudecas.regenerate --scenario nominal
python -m etudecas.regenerate --scenario risques
python -m etudecas.regenerate --scenario securite_150
python -m etudecas.regenerate --scenario acceleration_50
```

Chaque commande crée un nouveau dossier daté sous `simulation/result`, avec ses CSV
et résumés. L'horizon conservé est de 1 825 jours. Ajouter `--days 7` pour un contrôle
court, `--with-map` pour produire la carte de ce seul calcul, ou `--dry-run` pour afficher la commande.
Un dossier de sortie déjà rempli est refusé. Les sensibilités restent distinctes du nominal.

**`--with-map` seul ne reconstruit pas le document 02 complet.** Pour refaire aussi
les comparaisons nominal/risques, les deux sensibilités du diagnostic et ses quatre
pièces jointes embarquées :

```powershell
python -B -m etudecas.regenerate --delivery lots
# Horizon minimal accepté par les comparaisons :
python -B -m etudecas.regenerate --delivery lots --days 300
```

La sortie se trouve dans le nouveau dossier daté `simulation/result/lots_.../`,
sous `maps/02_carte_lots_recente.html`. La carte de référence conservée n'est pas
écrasée. Cette commande contrôle les invariants CSV et les rapprochements des
quatre calculs. Elle ne lance pas de vérification des interactions du navigateur.
Elle n'ajoute ni Monte Carlo ni SCAN à cette livraison.
Le module de comparaison exige au moins 300 jours : un horizon plus court est
refusé avant calcul pour cette livraison. Les simulations individuelles restent
testables sur sept jours.
Choisir un dossier parent sans ancienne campagne `risk_amplitude_duration_sweep_5y` :
le lecteur historique explore encore ce voisinage. La commande refuse ce cas avant
de lancer les calculs, pour éviter tout mélange involontaire.

La première reprise du **25 septembre 2026** a vérifié à nouveau quatre calculs de
1 825 jours, 124 exports exacts, 47 sections de carte, 197 contrôles de contenu
et provenance et 29 contrôles interactifs contre les CSV. Les trois autres
présentations ont été réassemblées à l'identique. Voir le
[bilan de cette reprise](../artifacts/testing/human_code_20260925/BILAN.md) :
120 tests ciblés et huit comparaisons complémentaires, sans relance des anciennes
suites d'altération de fichiers.
Les sorties temporaires ont été retirées après qualification ; les références
HTML et les preuves compactes restent disponibles.

La passe suivante de simplification a retiré dix fichiers Python et vérifié
quatre nouveaux calculs de 1 825 jours : 124 exports identiques, 47 sections de
carte et cinq volets de diagnostic concordants, 197 contrôles de contenu et
provenance, 27 tests ciblés, neuf contrôles du navigateur et neuf contrôles du
suivi de lots. Le [relevé de cette passe](../artifacts/testing/simplification_suite_20260925/simplification.json)
contient les manifestes et les limites. Les trois présentations historiques
n'ont pas été réassemblées pendant cette seconde passe ; leurs HTML conservés
sont inchangés.

La simplification du **28 septembre 2026** a de nouveau reconstruit la carte
récente à partir de quatre calculs de 1 825 jours : 124 exports identiques,
47 blocs de carte et cinq volets de diagnostic concordants, 197 contrôles de
contenu et provenance, neuf contrôles de navigation et neuf contrôles des lots.
Les 25 tests ciblés et les comparaisons en mémoire couvrent les changements de
cette tranche. Le [relevé du 28 septembre](../artifacts/testing/simplification_campagnes_20260928/simplification.json)
conserve les commandes, sources, manifestes et limites. Les trois présentations
historiques n'ont pas été réassemblées pendant cette tranche ; les quatre HTML
de référence restent inchangés.

Vérification historique du 23 septembre 2026, après la quatrième passe : les quatre
calculs de 1 825 jours retrouvent **124 fichiers identiques octet par octet**.
Les 47 sections de la carte et les cinq volets métier du diagnostic concordent
sans tolérance numérique. Les 25 différences de métadonnées autorisées sont
des chemins ou identifiants examinés ; deux reformulations descriptives déjà
signalées restent distinctes. L'ordre des listes est conservé.

Les contrôles comprennent 197 vérifications d'intégrité, la qualification des
62 familles d'invariants du nominal et le navigateur sur les versions autonome
et multipage. Un parcours complémentaire vérifie 29 interactions contre les CSV :
deux vues de lots, origines/destinations, bilans datés, transports, impacts et quatre
téléchargements réels. Le lot témoin `PBATCH-411EC755D7110AE0` retrouve ses
14 400 unités produites et expédiées. Les trois présentations historiques ont
également été réassemblées à l'identique.

Le temps d'une livraison inclut quatre simulations, leurs exports, les contrôles
et l'assemblage ; ce n'est pas le temps d'une seule simulation. Le dernier
recalcul a activé le relevé des imports et ne constitue pas un benchmark.
Les durées observées restent dans ses manifestes ; les mesures appariées
et leurs limites sont détaillées dans le
[plan de simplification](PLAN_SIMPLIFICATION.md).
La [synthèse courante](../artifacts/testing/human_code_20260925/verification-summary.json)
réunit les dernières preuves de recalcul. Les bilans des étapes précédentes sont
conservés, avec leurs chemins d'origine, dans [l'archive historique](../archive/README.md).
Ces vérifications établissent la conformité à la référence simulée, pas la
calibration industrielle ni la validité de toutes les campagnes de recherche.

Les quatre HTML de référence restent inchangés. Les résultats temporaires sont
retirés après qualification, en gardant les capsules de sources et les preuves
compactes. Pour refaire les contrôles sur les CSV, régénérer le calcul : les
chemins des anciens manifestes décrivent une exécution datée. La génération
seule ne revendique jamais une validation navigateur ; celle-ci reste séparée.

Les commandes et trois entrées déplacées sont conservées sous
[config/reproduction_20260920](../config/reproduction_20260920/).
Les paramètres métier d'origine ont été conservés ; seuls les chemins ont été adaptés.
Le graphe nominal reste sous `simulation_prep/result/reference_baseline/`.
Les originaux des manifestes sont consignés dans la preuve locale du nettoyage.

### Préserver les sources du prochain calcul

Chaque exécution de **`python -m etudecas.regenerate`** sauvegarde désormais, avant
calcul, les fichiers de code présents sur disque, les entrées explicites, les
commandes et les versions Python installées dans un ZIP sous
`config/reproduction_20260920/sources/`. Une livraison de quatre scénarios partage
une seule archive. Son empreinte est inscrite dans le plan et les manifestes de
calcul ; l'archive reste en dehors des résultats jetables.

Après chaque calcul et à la fin de la livraison, la commande vérifie que les sources
et intrants capturés sont toujours identiques. Une modification, disparition ou
nouvelle source détectée provoque un refus. Un `--dry-run` ne crée pas d'archive.
La capture utilise les fichiers réels, y compris les modifications non commitées.

Vérifier ou extraire une archive, en remplaçant `ARCHIVE.zip` par son chemin et en
choisissant un dossier vide dans le projet :

```powershell
python -B -m etudecas.reproduction_bundle verify ARCHIVE.zip
python -B -m etudecas.reproduction_bundle extract ARCHIVE.zip etudecas/artifacts/testing/rejeu_isole
```

La copie extraite contient ses commandes et son inventaire dans
`reproduction-bundle.json`. Depuis cette copie, les commandes `etudecas.regenerate`
fonctionnent sans Git ; choisir le scénario et l'horizon du manifeste à reproduire.
Les dépendances Python et le navigateur ne sont pas inclus dans le ZIP : leurs
versions sont enregistrées, et un environnement compatible reste nécessaire.
Le contrôle isolé sur ce poste utilise les dépendances déjà installées.

La version intégrée a été vérifiée depuis une copie sans Git, réseau ni accès aux
sources d'origine : quatre calculs d'un jour réussis, leurs quatre sauvegardes
automatiques vérifiées, et les 32 CSV du nominal identiques à l'original.
Ce test valide l'intégration et la présence des entrées ; les événements prévus
après le premier jour étaient couverts par le premier recalcul complet de 1 h 35,
exécuté avant l'ajout de cette protection au lanceur. La livraison finale de
35 min 30 utilise bien la protection intégrée.

Cette protection concerne l'entrée `regenerate`. Les anciens scripts de recherche
ne sont pas encore tous raccordés à ce mécanisme ; leur convergence vers une entrée
commune reste une étape du plan de simplification.

Des instantanés compacts sont conservés pour les versions effectivement vérifiées,
y compris avant et après optimisation. Les résultats détaillés et copies HTML créés
pour ces essais sont retirés après validation. Les preuves gardent leur date et
leurs empreintes ; relancer un contrôle exige de régénérer les données dont il a
besoin, et non de réutiliser un ancien statut de succès.

Après rangement, les capsules directement référencées restent dans le dossier
`sources/`. Les treize autres sont conservées dans
`archive/preuves_et_documents_20260925.zip`, sous leur chemin d'origine : extraire
la capsule nécessaire avant de lancer les commandes de vérification ci-dessus.

### Vérifier une simplification ou une optimisation

Le lanceur inscrit maintenant `elapsed_seconds` dans chaque manifeste. Pour la
livraison complète, `portable-delivery.json` détaille le temps des quatre simulations,
celui de la construction de carte et le temps total. Le temps d'une simulation
inclut ses exports ; le total comprend aussi les contrôles et l'assemblage.

Conserver temporairement un calcul avant modification et un calcul après, sur
**1 825 jours**, avec les mêmes données, options et graines. Comparer leurs exports :

```powershell
python -B -m etudecas.testing.replay_comparison --before CHEMIN_AVANT --after CHEMIN_APRES --output NOUVELLE_PREUVE.json
```

Ce contrôle compare tous les fichiers de `data/` et `summaries/`, les en-têtes,
l'ordre et le texte exact des cellules CSV, et les valeurs JSON sans tolérance
numérique. Il refuse aussi les fichiers ajoutés, manquants ou modifiés pendant
la comparaison. Il ne compare pas les manifestes d'exécution ni le HTML.

Si une copie isolée modifie uniquement des chemins techniques, l'option
`--metadata-rules FICHIER.json` permet une liste explicite de substitutions :
fichier, pointeur JSON ou colonne CSV, type technique, ancienne et nouvelle valeurs
exactes. Chaque utilisation est rapportée ; aucune règle ne peut masquer une
quantité, une date métier, un identifiant de lot ou une graine. Une règle non
utilisée provoque un refus. Vérifier séparément les empreintes des intrants.

La [première passe de simplification](PLAN_SIMPLIFICATION.md) décrit les mesures
comparables et les vérifications réellement exécutées. Reconstruire ensuite les
cartes concernées et vérifier leurs données et interactions ; un résumé identique
ou un test court ne suffit pas à qualifier la simulation complète.

L'étape d'export autonome est aussi réutilisable séparément après génération
d'une carte et de son diagnostic :

```powershell
python -B -m etudecas.visualization.maps.portable_diagnostic --map CHEMIN_CARTE --diagnostic CHEMIN_DIAGNOSTIC_INDEX --output NOUVEAU_HTML
```

Son contrôle sur le document 02 a reproduit exactement ses octets et ceux de ses
quatre téléchargements. Ce contrôle porte sur l'emballage du document, pas sur
un nouveau calcul scientifique.

## Réassembler les présentations historiques

Ces commandes n'utilisent que le HTML conservé et le code du projet. Elles refusent
un fichier de sortie déjà présent :

```powershell
python -B -m etudecas.visualization.rebuild_archives --kind demonstration --source-html etudecas/resultats/01_demonstration_complete.html --output-html demonstration_reassemblee.html
python -B -m etudecas.visualization.rebuild_archives --kind supply_chains --source-html etudecas/resultats/03_comparaison_supply_chains.html --output-html comparaison_reassemblee.html
python -B -m etudecas.visualization.rebuild_archives --kind fournisseurs --source-html etudecas/resultats/04_criticite_fournisseurs_configurations.html --output-html fournisseurs_reassembles.html
```

Les commandes longues ci-dessus servent à vérifier la provenance. Elles
ne relancent pas les simulations.

## Comparer les fournisseurs selon la configuration

Le [quatrième HTML](../resultats/04_criticite_fournisseurs_configurations.html)
expose les 108 cas retrouvés dans la matrice du 4 septembre : 18 liaisons,
deux causes et trois états. Il compare les pertes de service après le même type
d'incident, avec classement par état, matrice entre états, recherche et détail.

Les références de service client simulé sont **100 %, 92,33 % et 79,47 %**.
Ce ne sont pas des disponibilités fournisseurs observées. L'étude conserve une
seule graine commune, un retard ajouté de 120 jours ou une disponibilité réglée
à 50 %, et les anciennes conventions du moteur. Les six cas non exercés ne
permettent aucune conclusion sur leur fournisseur. Les expositions aux incidents
varient entre états : ce classement descriptif ne constitue pas une confirmation
statistique de criticité. La qualité et les risques fournisseurs dépendants de
l'état étaient désactivés dans cette étude.

Le HTML embarque les octets du CSV et du manifeste sources avec leurs empreintes.
On peut le reconstruire sans le dossier externe, depuis l'HTML ou le JSON exporté :

```powershell
python -B -m etudecas.visualization.supplier_configuration_comparison rebuild --source-html etudecas/resultats/04_criticite_fournisseurs_configurations.html --output-html etudecas/resultats/comparaison_fournisseurs_reassemblee.html
python -B -m etudecas.visualization.supplier_configuration_comparison build --input-json fournisseur-configurations.json --output-html nouvelle-comparaison.html
```

Producteur historique des calculs :
`prototypes/scan_2027_risk_control/supplier_operating_point_incident_preliminary.py`,
puis les scripts de consolidation de la matrice. La campagne ultérieure de
confirmation à 30 répétitions ne dispose pas d'une livraison complète retrouvée
pour les trois états. Pour la reprendre avec le moteur actuel, requalifier les
configurations puis recalculer des expériences comparables ; ne pas mélanger
des exécutions issues de versions différentes du moteur.

Les contrôles du 22 septembre précisent cette réserve :

- Deux graines de la référence historique `op_100` donnent 99,9925 % de service
  avec le moteur actuel. Les délais réalisés diffèrent pour 2 604 groupes de
  transport communs : l'aléa fonctionne, malgré ce même indicateur de service.
- Sur la **même graine**, `op_93` passe de 94,3227 % dans la confirmation historique V7 à **99,5585 %**.
  Ce seul essai ne mesure pas sa nouvelle moyenne ; il interdit de transférer
  automatiquement l'ancienne qualification. `op_80` n'a pas été requalifié.
- Les 1 110 exécutions retrouvées de la campagne V8 couvrent uniquement `op_100`.
  Elles sont liées à l'ancien moteur et ne complètent pas les deux autres états.

Les graphes, le profil, les 18 liaisons et le protocole sont sauvegardés dans
[supplier_inputs.zip](../config/reproduction_historique/supplier_inputs.zip),
avec leurs empreintes et commandes relatives dans
[supplier_manifest.json](../config/reproduction_historique/supplier_manifest.json).
Ce sont les entrées d'une étude historique ; le profil d'une nouvelle étude doit
être revu selon les conventions du nominal corrigé.

La prochaine étape proposée est un **plan limité à neuf couples de délais**, puis
une confirmation sur d'autres graines si les niveaux de service sont encadrés.
Ce plan n'est pas lancé. Il modifie seulement des graphes d'étude, jamais les
stocks réels ni les cibles de sécurité du nominal. Le protocole de comparaison
exhaustif représente 3 240 incidents et 90 références, soit **3 330 simulations**,
hors recalibration ; les essais indiquent plusieurs jours de calcul. La
spécification `supplier-recalibration-spec.json`, conservée sous
`etudecas/artifacts/testing/reproducibility_closure_20260922/` dans
[l'archive historique](../archive/README.md), explicite le budget, les arrêts
et les conditions de validation. Le nombre de
répétitions seul ne suffit pas à qualifier un classement industriel.
Le mécanisme de manque à livrer de V8 diffère aussi de la réduction de disponibilité
utilisée dans l'ébauche du HTML 04 : ces expériences ne sont pas interchangeables.

## Recalculer les autres analyses

Le pipeline complet reste disponible :

```powershell
python etudecas/run_etudecas_pipeline.py rebuild-map-5y
```

Cette commande est plus coûteuse : elle prépare les scénarios, sensibilités et campagnes
Monte Carlo selon ses options. Les outils spécifiques de criticité, de propagation
d'incertitude et de recherche restent dans le code. Fournir les chemins des nouveaux
résultats aux analyses qui utilisaient par défaut un ancien dossier.

La démonstration du 15 septembre et l'ébauche du 1er septembre restent des résultats
historiques. Leur export n'est pas une promesse de reproduction identique avec le code
courant : elles regroupent plusieurs protocoles et hypothèses de recherche.
Leurs programmes producteurs et le dossier de recherche externe ont été conservés.

Les liens vers les anciens CSV dans les rapports datés peuvent désormais être indisponibles.
Les anciennes preuves ne sont pas réacceptées ou remplacées par des empreintes nouvelles.
Les tests d'intégration qui demandaient un ancien calcul doivent recevoir un calcul régénéré.

## Étude des composants potentiellement partagés

Le parcours `shared-components` prépare une hypothèse séparée : stock global conservé,
consommation de la production modélisée et usages complémentaires tracés séparément.
Il examine les besoins du premier plan MRP du 5 janvier, hors semaine courante,
et retire les besoins BOM propres ainsi que les compléments déjà transmis en amont.
Le ratio de présélection 1,25 est une convention d'étude, pas une règle industrielle.
Les absences de semaines ne prouvent pas une consommation nulle.

```powershell
python -B -m etudecas.simulation.studies shared-components prepare --workdir etudecas/artifacts/testing/mon_essai_partage
python -B -m etudecas.simulation.studies shared-components run --workdir etudecas/artifacts/testing/mon_essai_partage
python -B -m etudecas.simulation.studies shared-components render --workdir etudecas/artifacts/testing/mon_essai_partage --html etudecas/resultats/mon_essai_partage/carte.html
```

Choisir des chemins nouveaux : les calculs et HTML précédents ne sont pas remplacés.
`--reference` désigne le dossier contenant `plan.json`, `source_forecasts_graph.json`
et les résultats témoins ; par défaut, il s'agit de
`artifacts/testing/mrp_execution_20260928/simulation_v6` sous Etudecas.
Conserver cette référence pour reconstruire exactement le protocole comparatif.
Les trois calculs durent 1 825 jours ; les CSV du nominal et du témoin daté sont
rapprochés octet par octet de leurs références. Les nouvelles sorties complémentaires
débitent les lots disponibles et gardent un reste à servir distinct en cas de manque.
Les jours de sécurité sources couvrent la demande totale connue, sans changer leur valeur.

Le HTML compare les calculs dans le panneau des données sources. Ses autres onglets
et les deux suivis de lots restent ceux du nominal historique, explicitement indiqués.
Le scénario complémentaire n'est pas une identification certifiée des autres références :
les prévisions de consommation deviennent une hypothèse de demande physique.
Les années 2 à 5 répètent ce calendrier ; seuls les inventaires 2025 permettent une
comparaison industrielle. Exécuter les qualifications CSV et navigateur sur les
fichiers exacts avant de déclarer la livraison vérifiée.

Pour comparer les révisions hebdomadaires de **001848 à Avène**, le même parcours
propose un essai limité à 2025. Il conserve la part complémentaire estimée au
5 janvier et remplace seulement les prévisions futures avec chaque plan connu.
Chaque semaine exécutée utilise le dernier plan strictement antérieur à son début :
les reports de la semaine courante ne sont pas recréés comme de nouveaux besoins.
Une ligne absente reste inconnue, sans reprise d'une ancienne prévision omise.
Les commandes déjà engagées et les retards physiques sont conservés.

```powershell
python -B -m etudecas.simulation.studies shared-components prepare-revisions --reference etudecas/artifacts/testing/shared_materials_20260929/study_v3 --workdir etudecas/artifacts/testing/mon_essai_revisions
python -B -m etudecas.simulation.studies shared-components run --workdir etudecas/artifacts/testing/mon_essai_revisions
python -B -m etudecas.simulation.studies shared-components render --workdir etudecas/artifacts/testing/mon_essai_revisions --html etudecas/resultats/mon_essai_revisions/carte.html
```

Les deux témoins (nominal et usages complémentaires figés) sont recalculés sur
1 825 jours et leurs CSV comparés aux références. La comparaison active utilise
deux calculs supplémentaires de **365 jours**, figé et révisé : une durée différente
changerait aussi l'anticipation du moteur à l'approche de la fin de simulation.
L'essai révisé dure donc 365 jours ;
il ne projette pas les révisions industrielles de 2025 sur les années suivantes.
Il ne rejoue pas les réceptions prévues H et ne réinitialise pas les stocks avec
les photos ultérieures. Les autres composants restent dans leur configuration témoin.

Le même parcours propose `prepare-sourcing` pour tester les rôles fournisseurs
confirmés de **001848 à Avène** : VD0951020A principal (1,58 EUR/kg, 56 jours,
6 000 kg standard), VD0519670A secours (4,20 EUR/kg, 21 jours, 4 000 kg standard).
Les valeurs sont relues dans `268091.xlsx/FIA` ; les autres matières restent
inchangées. Le déclenchement du secours sur rupture physique datée et le maintien
des commandes fermes tardives sont des conventions expérimentales, pas des règles
industrielles démontrées par les seuls flux MRP et stocks.

```powershell
python -B -m etudecas.simulation.studies shared-components prepare-sourcing --reference etudecas/artifacts/testing/shared_revisions_001848_20260929/study --workdir etudecas/artifacts/testing/mon_essai_fournisseurs
python -B -m etudecas.simulation.studies shared-components run --workdir etudecas/artifacts/testing/mon_essai_fournisseurs
python -B -m etudecas.simulation.studies shared-components render --workdir etudecas/artifacts/testing/mon_essai_fournisseurs --html etudecas/resultats/mon_essai_fournisseurs/carte.html
```

Le parcours recalcule le nominal sur 1 825 jours et la référence révisée sur
365 jours, exige l'identité de leurs CSV avec les témoins conservés, puis compare
l'essai fournisseur à la référence de même durée. Les commandes fermes de départ,
les consommations, les sécurités et les versions de prévision restent identiques
en entrée ; les conséquences physiques de la nouvelle décision restent à mesurer.
Une livraison en secours peut créer un surplus après arrivée d'un ferme tardif :
ce surplus doit rester visible. Les autres panneaux de la carte et les deux
suivis de lots demeurent ceux du nominal historique.

Pour **001757 à Avène**, `prepare-batching` sépare l'effet des prévisions
actualisées de celui des quantités d'achat. Le parcours conserve la même
configuration de 001848 dans tous les comparateurs, puis prépare sept calculs
de 365 jours : témoin figé, prévisions seules, arrondi à 1 000 kg, regroupement
sur 14/28 jours avec un pas de 100 kg, et les deux combinaisons avec 1 000 kg.
Un huitième calcul reproduit le nominal de 1 825 jours. Les CSV du nominal et
du témoin figé doivent être identiques aux références conservées.

```powershell
python -B -m etudecas.simulation.studies shared-components prepare-batching --reference etudecas/artifacts/testing/sourcing_rules_20260929/study --workdir etudecas/artifacts/testing/mon_essai_regroupement
python -B -m etudecas.simulation.studies shared-components run --workdir etudecas/artifacts/testing/mon_essai_regroupement
python -B -m etudecas.simulation.studies shared-components render --workdir etudecas/artifacts/testing/mon_essai_regroupement --compare-run lot_1000 --html etudecas/resultats/mon_essai_regroupement/carte.html
```

La fenêtre démarre au premier besoin non couvert ; elle ne fixe pas une cadence
de commande. Les besoins suivants sont regroupés sans déplacer leurs échéances
dans les bilans. Stocks et commandes fermes sont déduits avant regroupement.
L'arrondi à 1 000 kg est une hypothèse tirée des entrées hebdomadaires du MRP,
pas une correction de la donnée FIA de 100 kg. Les engagements, les sécurités,
le délai fournisseur et la disponibilité après réception sont conservés.
La part complémentaire estimée au 5 janvier ne varie pas avec les stocks.

Comparer les stocks, les réceptions et les quantités commandées, en séparant
l'effet des prévisions de l'effet du regroupement. Les versions successives H
ne sont jamais additionnées comme des livraisons réelles. La comparaison par
semestre renseigne la stabilité des résultats, sans constituer une validation
hors échantillon : les hypothèses ont été suggérées par les plans de toute 2025.
`--compare-run` choisit uniquement la courbe cochée au départ ; il ne sélectionne
ni ne promeut automatiquement une règle dans le nominal.

### Comparer 2025 avec un horizon MRP glissant de 52 semaines

`prepare-rolling52` sépare la durée d'exécution (365 jours) de la projection
du MRP (364 jours futurs à chaque décision). Il conserve les semaines 2026
présentes dans les versions connues des prévisions complémentaires de 001757
et 001848, avec leurs parts estimées initiales. Les 17 autres calendriers
complémentaires restent inchangés ; aucune semaine absente n'est inventée.
Le moteur garde la date de connaissance du plan pour choisir les prévisions,
sans utiliser une version industrielle future.

```powershell
python -B -m etudecas.simulation.studies shared-components prepare-rolling52 --reference etudecas/artifacts/testing/batching_001757_20260929/study --workdir etudecas/artifacts/testing/mon_essai_horizon52
python -B -m etudecas.simulation.studies shared-components run --workdir etudecas/artifacts/testing/mon_essai_horizon52
python -B -m etudecas.simulation.studies shared-components render --workdir etudecas/artifacts/testing/mon_essai_horizon52 --compare-run previsions_actualisees --html etudecas/resultats/mon_essai_horizon52/carte.html
```

La référence annuelle de cette étude utilisait déjà les prévisions actualisées,
mais les coupait au 31 décembre. Les six variantes corrigées reprennent les mêmes
politiques d'achat, du pas de 100 kg sans regroupement aux essais 14/28 jours.
Les témoins annuel et nominal sur cinq ans sont recalculés et leurs CSV doivent
être strictement identiques aux résultats conservés. La correction est activée
explicitement dans les graphes de l'étude (`mrp_planning_horizon_days: 364` et
calendrier versionné schema 3) ; les anciennes configurations sont reproductibles.

Les prévisions 2026 guident les décisions de 2025, sans créer de consommation
physique de 2026 dans les résultats 2025. Les cibles en quantité peuvent changer
avec les besoins futurs mieux renseignés, mais les jours de sécurité sources
restent identiques. Les commandes arrivant après la période d'observation restent
des engagements en cours, pas des réceptions déjà exécutées.

### Tester les conventions de 693055 puis le regroupement de 001757

`prepare-policy` part du témoin 52 semaines conservé et prépare cinq étapes
successives : prévisions complémentaires actualisées de 693055, pas de transfert
de 600 kg, réception sur 7 jours lundi–vendredi, protection datée candidate,
puis arrondi des nouvelles propositions de 001757 par multiples de 1 000 kg.
Le nominal sur 1 825 jours et le témoin annuel sont aussi recalculés, avec
comparaison exacte de leurs CSV. Aucune étape n'est promue automatiquement.

```powershell
python -B -m etudecas.simulation.studies shared-components prepare-policy --reference etudecas/artifacts/testing/rolling52_20260929/study --workdir etudecas/artifacts/testing/mon_essai_politique_mrp
python -B -m etudecas.simulation.studies shared-components run --workdir etudecas/artifacts/testing/mon_essai_politique_mrp
python -B -m etudecas.simulation.studies shared-components render --workdir etudecas/artifacts/testing/mon_essai_politique_mrp --compare-run protection_693055 --html etudecas/resultats/mon_essai_politique_mrp/carte.html
```

La protection est un niveau de stock, pas une consommation. Son interprétation
des 20 jours ouvrés sources reste candidate ; elle ne prouve pas que l'ERP utilise
un plancher plutôt qu'une anticipation des besoins. Les délais de référence de
la liaison et la frontière agrégée Gaillac sont conservés. Les pas de quantité
ne sont ni des tailles de palette ni des capacités de camion.

Les stocks initiaux, nomenclatures, jours de sécurité et parts complémentaires
estimées sont conservés. Les 16 autres calendriers complémentaires figés et les
versions de prévision de 001757/001848 restent inchangés. Comparer les étapes
adjacentes pour attribuer leurs effets, puis vérifier stocks, réceptions et
service PF ensemble. Les autres panneaux et les deux suivis de lots restent
ceux du nominal historique.
