# Production : programme connu, capacité et comparaison aux données

Cette investigation part du commit `8f7871377134cbd9d86a49d332662e70311c6496`
sur `dev_yannick`. La référence reste conservée. Les expériences utilisent les
adaptateurs de `current_reference.run_engine`, les mêmes stocks initiaux et la
même demande réelle ; les paramètres propres aux essais sont déclarés.

## Résultat et décision

Sur 135 jours, exiger un programme usine connu pour chaque nouvelle campagne,
avec une allocation de travail étalée, rapproche nettement 268967 des données.
Ce résultat soutient une séparation entre le besoin commercial et
l'autorisation de lancer une fabrication. Il ne valide pas encore le modèle
industriel ni une capacité constante de machine.

| Mesure sur les semaines renseignées | Témoin | Programme requis | Réel estimé par les étuis |
|---|---:|---:|---:|
| 268967 : volume, 11 semaines | 107 800 | 215 600 | 295 750 |
| 268967 : écart de volume au réel | −63,55 % | −27,10 % | — |
| 268967 : erreur hebdomadaire moyenne | 19 595,45 | 8 131,82 | — |
| 268091 : volume, 18 semaines | 2 351 135 | 2 351 136 | 2 140 500 |
| 268091 : erreur hebdomadaire moyenne | 81 574,72 | 81 971,67 | — |

L'erreur hebdomadaire moyenne mesure la distance entre la quantité simulée et
la quantité estimée, semaine par semaine : un excès de 100 unités et un manque
de 100 unités comptent chacun pour 100, sans se compenser.
Elle baisse de **58,50 % pour 268967**, mais augmente de **0,49 % pour 268091**.
Les semaines inconnues ne participent pas à cette mesure. Les deux campagnes
de 107 800 unités s'exécutent du 17 au 30 mars et du 14 au 27 avril ; les
quantités, budgets de composants et consommations sont rapprochés séparément.

Les départs du dépôt et les arrivées chez les clients restent identiques pour
les deux produits. Au 15 mai, le stock physique de 268967 au dépôt augmente
de 107 800 unités, entièrement sous contrôle ; son stock utilisable est encore
identique. Pour 268091, le stock physique final est identique, mais 14 400
unités supplémentaires restent sous contrôle. Le gain usine ne constitue donc
pas un gain de service client sur cette fenêtre.

La variante reste **expérimentale, sans promotion de la référence**. Le rapport
[interactif](../resultats/production_realiste_20261115.html) permet de sélectionner
une semaine et de remonter aux budgets connus, composants et campagnes.

## Ce que mesurent les courbes

La mesure principale rapproche les prélèvements d'étuis observés et les
consommations d'étuis exécutées par le simulateur : 333362 à 1430 pour 268967,
338929 à 1810 pour 268091. Le coefficient de nomenclature vaut un dans ces deux
cas. Le conditionnement des ordres initiaux est inclus dans la mesure simulée ;
les usages externes sont séparés. Les lots achevés et les encours sont des
mesures distinctes. Une sortie d'étuis estime la production, sans identifier
à elle seule un ordre de fabrication, les pertes ou sa date de libération.

Les scores portent sur les semaines complètes renseignées. Une semaine
absente reste inconnue. Le calendrier retenu associe le libellé du dimanche
à la semaine suivante, du lundi au dimanche ; le programme MRP conserve son
propre calendrier source du dimanche au samedi.

## Faits qui expliquent une partie des écarts

- Le lot de 268967 est conservé à 107 800 unités : deux fichiers donnent un
  minimum et un maximum identiques, malgré une colonne « fixe » à zéro.
  Les totaux hebdomadaires ne suffisent pas à justifier sa suppression.
- Le programme connu le 16 mars contient 110 495 étuis et 33 855,34 mètres du
  second composant. Ces budgets sont compatibles avec un lot. Ce sont des
  besoins planifiés, pas un ordre ferme identifié.
- Sur les mêmes 43 semaines futures, les prévisions commerciales passent de
  2 072 667 unités dans la version du 24 février à 3 983 833 dans celle du
  31 mars, puis 1 946 520 dans celle du 28 avril. Le saut du plan de production
  suit ces versions ; il précède le renouvellement du budget mensuel.
- Une allocation constante de 7 700 unités par jour plafonne à 53 900 par
  semaine. Elle ne peut donc reproduire toute la série estimée depuis les
  étuis, notamment les 94 000 de la semaine du 21 avril. Cette allocation
  représente une hypothèse de travail étalé, pas une capacité physique validée.
- Les stocks initiaux de Muret peuvent absorber une baisse de fabrication.
  Des livraisons simulées satisfaisantes ne valident pas le calendrier usine.

La demande réelle affectée à l'année civile 2025 représente 1 719 549 unités
pour 268967 selon le contrat actuel d'allocation journalière. Les 1 263 850
unités estimées depuis les étuis ne couvrent que 36 semaines connues : les
deux nombres ne constituent pas un bilan annuel complet de production et de
livraison.

## Corrections et essais

Les calendriers de lancement ne doivent pas être confondus avec les calendriers
de disponibilité. Une disponibilité connue strictement au-delà du dernier
besoin suffit à couvrir ce besoin, même si le dernier lancement est antérieur.
Une égalité en bout de calendrier peut tronquer un plateau et reste refusée
si les lancements ne couvrent pas eux-mêmes la date de besoin. Cette règle est
commune aux achats simples, anticipés, répartis et principal/secours.

Lorsqu'un placement sur capacité repousse réellement un besoin au-delà du
calendrier, celui-ci est prolongé depuis les paramètres déclarés de transport,
contrôle et revue. Le préfixe, les prix, les parts fournisseurs et les lots
restent identiques. La prolongation ne crée pas une observation industrielle.
Les offres sans règles connues ne sont pas extrapolées.

Dans le mode de capacité finie, une campagne engagée prévoit sa fin depuis le
travail restant puis son contrôle qualité. La marge de planification ne
redémarre pas chaque soir.

Les variantes de programme sélectionnent un lot déjà nécessaire, sous couverture
des budgets connus et de toute sa matière. Le recalcul vérifie que les
quantités proposées restent identiques après ajout du lot avancé. Le travail
réservé et le crédit de produit fini sont suivis séparément. Les arrondis des
composants entiers sont vérifiés journée par journée. La variante récurrente
conserve chaque programme et refuse une nouvelle avance tant que la précédente
n'est pas achevée.

Le couplage d'une avance en mars et d'un travail étalé réduit de 90,16 % l'erreur
sur les semaines du 17 et du 24 mars : 53 900 unités simulées chacune, contre
49 250 et 60 000 estimées. Mais il dégrade l'erreur moyenne sur les onze semaines
connues : 22 880,91 contre 19 595,45 unités. La simple répétition de la règle
n'ajoute aucun programme ; les huit CSV physiques comparés restent identiques.

La révision commerciale du 31 mars fait avancer le premier lancement planifié
de J130 à J90. La fabrication travaille effectivement du 3 au 16 avril. La
campagne suivante commence les 17 et 18 avril, puis manque de composant 344135 :
la livraison suivante est présente physiquement le 23 avril, mais disponible
après contrôle le 29. Cela explique une coupure simulée ; ce n'est pas la preuve
d'une panne industrielle. L'essai d'autorisation de tous les nouveaux lancements
vise à départager ce mécanisme de réaction aux prévisions et le programme usine.

Cet essai final autorise aussi un lot déjà dû dans le calcul MRP : imposer
seulement une autorisation aux avances laisserait les lancements normaux
contourner le programme. Il conserve le contrôle de matière pour tout le lot,
la quantité nette déjà nécessaire et la continuation des campagnes engagées.
Une source absente, un budget incomplet et un budget explicitement nul restent
des états différents. Les budgets industriels de composants sont ici une
**hypothèse d'autorisation**, pas des ordres fermes de fabrication identifiés.

Le résultat de mars confirme l'intérêt de coupler date et durée ; le résultat
global confirme que la réaction aux prévisions lointaines doit aussi être
encadrée. Les versions MRP montrent cependant des déplacements et regroupements
en avril : elles ne prouvent pas un gel strict des dates sur huit semaines.

Un défaut distinct reste démontré sur la première campagne : à J81, il reste
53 900 unités à fabriquer, soit sept journées à 7 700. Le composant de
remplacement EX-344135 est disponible pour ces 53 900 unités et permet de finir
à J88. Mais le calcul des besoins remonte vers le composant principal 344135,
dont la réception utilisable est J92 : la promesse usine est donc reportée
quatre jours trop tard. La seconde campagne dispose du composant principal
et ne subit pas ce report. Il s'agit d'une incohérence entre planification et
exécution des substitutions, pas d'un simple problème d'affichage ; son effet
sur les autres décisions n'a pas été quantifié.

Le contrôle qualité est séparé : le premier lot part de l'usine à J88, arrive
au dépôt à J90 et devient utilisable à J111. Le second part à J116, arrive à
J118 et reste sous contrôle à la fin de l'essai. Le diagnostic de substitution
est conservé dans `engaged_substitution_review.json`, sans changer les sources
après les calculs comparés.

## Preuves et limites

Les protocoles, exécutions, cas échoués et contre-validations se trouvent dans
`etudecas/artifacts/testing/production_realiste_20261115/`. Les premiers appels
directs au moteur sont exclus : ils omettaient des adaptateurs de la référence.
Les échecs de calendrier sont conservés, sans résultat physique revendiqué
lorsque les CSV n'ont pas été exportés.

Sur les **659 sources stabilisées**, 156 cas ciblés passent, ainsi que les
contre-vérifications indépendantes : 58 contrôles de calcul, 46 de programmes,
14 d'autorisation et 30 oracles en mémoire. Les deux calculs finaux terminent
avec un code retour nul, en 417,63 et 512,56 secondes. Ces réussites ciblées ne
remplacent pas la qualification globale : celle-ci reste **refusée** dans les
deux cas, pour les mêmes cinq familles : disponibilité de transfert sans
origine, contrat des budgets de consommations complémentaires, provenance des
événements externes et deux contrôles de leur base de consommation. Les
comptages sont respectivement 1, 288, 176/174, 40 et 40.

Le contrôle d'environnement final réussit. Le contrôle d'ensemble refuse
logiquement la qualification non réussie. Le contrôle documentaire automatique
signale cinq registres générés à revoir (`lot_risk`, `scenario_comparison`,
`execution_verification`, `material_traceability`, `audited_semantics`) ; leurs
empreintes métier ne sont pas réapprouvées automatiquement. Les règles et ce
bilan sont mis à jour, sans prétendre que tout le catalogue documentaire est à jour.

Preuves principales, relativement au dossier d'investigation :

- `final_manifest.json` : clôture de l'étude, état final, liens et limites.
- `protocol_authorization.json` : question, intervention, critères et budgets
  fixés avant l'essai final ; `source_freeze_stage4.json` : état des sources.
- `tests_stage4/tests-3f1b6a5aa02d454fb36deac4ef498ebb/manifest.json` : tests ciblés.
- `stage4_authorized/control/run/run_manifest.json` et
  `stage4_authorized/authorized/run/run_manifest.json` : calculs comparés.
- `validator/native_authorized_final_review.json` : chiffres et refus de
  qualification ; `validator/runtime_authorized_acceptance.json` : absence de
  mélange de versions, sans validation scientifique générale.
- `forecast_boundary_review.json` et `april_causal_review.json` : révisions
  commerciales, programme usine et disponibilité réelle des composants simulés.
- `comparison/archive_v4/comparison.json` : variante antérieure qui améliore
  mars mais dégrade l'ensemble, conservée avec son propre état de code.

Les contrôles navigateur et Node ne sont pas exécutés, conformément à la
restriction conservée. La revue du rapport est numérique et statique ; elle
ne constitue pas une vérification des clics dans un navigateur.

Pour reproduire les deux calculs depuis cette copie de travail, dans de
nouveaux dossiers de résultats, lire puis adapter le superviseur local
`run_stage4_authorized.py` et son adaptateur `native_case_v4.py`. Les graphes
exacts sont `stage4_authorized/{control,authorized}/input_graph.json` ; leurs
paramètres et commandes figurent dans les manifestes. Les entrées doivent
passer par `current_reference.run_engine` : appeler directement le moteur
omet des adaptateurs indispensables. Ces scripts et les résultats lourds
restent dans les preuves locales ; les règles et tests sont versionnés.

Les dates de publication exactes des versions ne sont pas disponibles : les
dates de connaissance suivent les conventions documentées des extractions.
Les usages complémentaires reconstruits de certains composants dépendent du
calendrier simulé ; ils ne constituent pas une validation indépendante des
stocks. La devise de certaines offres présente aussi un désaccord de
provenance ; cette étude ne valide pas une comparaison monétaire.

Le travail en cours peut être fractionnaire en équivalents de produits selon
le contrat existant ; les produits finis libérés et les mouvements physiques
en unités restent entiers. Le plafond appliqué séparément chaque jour aux
composants entiers entraîne un étui supplémentaire dans trois campagnes
examinées. Cette dépendance au découpage est conservée comme limite de
consommation, sans la confondre avec un produit fini physique fractionnaire.

Restent à départager : l'allocation de machine au cours du temps, les ordres
fermes et leur gel industriel, les consommations concurrentes des composants,
et les stocks/encours initiaux à l'usine. Aucune panne n'est déduite d'un report
MRP et aucune cible de consommation future n'est injectée dans les décisions.

Le prochain essai utile doit opposer **travail réellement irrégulier** et
**prélèvements d'étuis regroupés dans les données**. Une allocation constante
de 7 700 unités par jour est déjà réfutée comme explication de toutes les
semaines : augmenter arbitrairement la capacité le 21 avril reproduirait une
cible sans expliquer le système. Des dates d'ordres, de prise de composants
et de fin de fabrication, ou un calendrier machine, permettraient ce test.
En attendant, corriger les promesses des campagnes engagées en tenant compte
des composants substituables est la priorité technique démontrée, distincte
des données manquantes. Cette correction nécessite son propre oracle et une
nouvelle paire de calculs ; elle n'est pas incluse dans le résultat présenté.
Une simulation annuelle ne trancherait pas les inconnues de cadence.
