# Données sources : contenu, rapprochements et limites

Ce document rassemble la connaissance acquise pendant les analyses 2025. Les
liens vers `artifacts/testing` indiquent les emplacements historiques des
preuves détaillées ; les dossiers volumineux peuvent être supprimés après leur
consolidation. Ils ne constituent jamais une dépendance du moteur courant.
Les règles exécutées sont décrites séparément dans
[`REGLES_MRP.md`](REGLES_MRP.md).

**Délais Gaillac — 12 octobre 2026.** Le [croisement complet des délais,
consommations et redistributions](../artifacts/testing/gaillac_delais_sources_20261012/bilan.md)
retrouve les 104 dates prévues d'entrée d'`Extract_En_cours` en ajoutant le
temps de réception à la date de livraison, hors jour initial, week-ends,
fériés nationaux 2025 et fermeture candidate du 4 au 15 août. Lundi–vendredi
seul explique 70 dates ; avec fériés, 99 ; avec fermeture, 104. Les cinq
dernières concernent 021081/Gaillac et impliquent neuf jours supplémentaires
exclus, sans identifier seuls les dates exactes d'une fermeture propre au site.
Un oracle indépendant d'addition en avant confirme le comptage des intervalles.

Les temps MRP de réception sont stables dans les 52 versions : Gaillac
001893/002612 **5 jours**, 021081 **75**, 693055 **28**, 773474 **33** ;
693055/Avène **7**, 773474/Gien **6**. Les deux OF initiaux Gaillac portent
**21/26 jours** : la divergence n'est pas une modification datée de 2025 et
ne prouve pas sept jours de fabrication. Des différences en-cours/MRP touchent
24 des 68 ordres comparables, sur huit couples. Les échéances initiales
explicites sont déjà conservées dans la simulation.

La consommation 021081 reste compatible en volume avec le bilan reconstitué
773474 : **794 238 kg contre 743 808 kg BOM sur 35 semaines communes**
(+6,78 %, pas un rendement mesuré). Les semaines ne coïncident pas toujours,
ce qui impose de distinguer consommation, en-cours et entrée de semi-fini.
001893/002612 à Gaillac ont des sorties hors Scan3 et aucune destination
identifiée ; leur traitement à réception de 5 jours est documenté, leurs
trajets sortants ne le sont pas. Les fichiers de stock immobilisé sont des
valorisations, pas un historique des contrôles qualité.

Les essais C1/C2/C3 de la veille conservent encore les transferts 693055 par
multiples de 600 kg ; le transfert source de **1 190 kg du 20–26 janvier**
montre que cette contrainte ne découle pas du lot de fabrication. Son retrait
était dans R2 et devra être réintroduit explicitement dans un essai combiné.
Cette analyse n'a changé ni le moteur ni le nominal.

La [passe de correction du 12 octobre](../artifacts/testing/gaillac_corrections_20261012/bilan.md)
réintroduit explicitement le transfert libre de 693055 dans D1, puis teste le
calendrier de réception/libération Gaillac dans D2. Les hypothèses de durée
avant/après entrée physique restent séparées des délais documentés. Les
fériés 2026 sont déclarés pour la projection glissante ; aucune fermeture
estivale 2026 n'est inventée. Les sources et la référence précédente restent
conservées. Voir le bilan pour l'état réel des exécutions et leurs résultats.

**Complément Gaillac — 10 octobre 2026.** Les stocks de 001893 et 002612
étaient représentés mais sans route d'approvisionnement. Les sources donnent
52 versions MRP locales et 5 jours ouvrés de réception pour chaque article.
Les bilans physiques bruts ferment : `1 094 + 1 870 - 1 751,5 - 233 = 979,5 kg`
pour 001893 et `414 + 5 000 - 5 136,5 = 277,5 kg` pour 002612.
Les sorties ne sont pas attribuées à nos fabrications (Scan3 nul) et leur
destination n'est pas identifiée. Le rôle de stockage/redistribution est
donc distinct de la fabrication de 773474 et 693055 ; aucune route des deux
matières vers Avène n'est démontrée.

Le [dossier source H1](../artifacts/testing/gaillac_hub_20261010/sources/bilan_sources.md)
sépare valeurs observées et paramètres candidats d'achat. Il conserve également
la réception initiale 002612 de 1 250 kg corroborée par H158 du premier MRP,
les mouvements H204 et la photo du 13 janvier, sans la confondre avec le J
physique différé des plans suivants. La date physique du 5 janvier et la
libération du 10 janvier sont des conventions ; les disponibilités ultérieures
sont révisées dans les sources. La photo isolée du 6 janvier et les 233 kg de
Divers sur 001893 restent des écarts documentés, sans correction des sources.

Audit du **8 octobre 2026** de tous les fichiers présents dans `etudecas/data/source`.
Ce document est le point d'entrée pour reprendre une étude sans reconstruire à
chaque fois la connaissance des sources. Les détails chiffrés, lignes Excel,
empreintes et résultats par article/site sont dans le
[registre associé](reference/source_knowledge.json).

**Périmètre : 22 fichiers — 14 Excel, 7 CSV et 1 JSON — et 38 onglets Excel.**
Les deux fichiers temporaires Office `~$…` sont exclus. Tous les onglets et toutes
les lignes non vides ont été parcourus. Les quantités ont été rapprochées après
conversion explicite des unités. Les formules Excel ont été lues avec leur
résultat enregistré ; Excel n'a pas été utilisé pour les recalculer.

La référence demande/centre de distribution acceptée, commit **`d9193dff4`**,
reste conservée. Cet audit ne modifie ni les sources, ni les règles du moteur,
ni les scénarios, ni les cartes HTML. Il distingue une observation dans les
fichiers, une déduction numérique et une hypothèse métier.

## Ce qu'il faut retenir

**Carnet initial — corrections et essais du 10 octobre.** L'audit d'
`Extract_En_cours.xlsx` recoupe les 49 groupes d'achats initiaux représentés
avec le premier MRP ; seulement 7 des 50 groupes comparables ont le même
volume physique reçu dans la semaine annoncée. Les dates du carnet sont
donc des promesses, pas un historique exécuté. Les dates de création et
l'état des matières des OF restent absents. Les échéances après janvier
ne sont pas supprimées et aucune confirmation future ne filtre le carnet.

La correction fournisseur préserve les 19 800 kg de 049371/Avène et les
6 400 UN de 734545/Gien, mais signale leurs routes manquantes au lieu de
reprendre celles d'autres fournisseurs. L'essai G6 suppose les deux OF
initiaux de Gaillac non commencés ; G7 teste séparément les dates des
réceptions physiques de 021081. G7 connaît le futur et ne valide pas le MRP.
Le [bilan et ses preuves](../artifacts/testing/extract_corrections_20261010/bilan.md)
conservent résultats, contrôle des stocks et limites séparément.

L'essai G8 utilise uniquement les I futurs connus pour calculer la sécurité
locale des sorties fabriquées disposant d'une politique source. La sélection
générique retient 773474/Gaillac : 1 559 cellules I futures, dont 534 zéros
explicites. Les 20 jours ouvrés viennent de `Politique de stock MRP!E21`.
Au 24 mars, la fenêtre se termine le 21 avril : la répartition hebdomadaire
dimanche–samedi donne 6 400 kg (`I12046`) + 2/7 × 6 400 kg (`I12047`),
soit **8 229 kg** de protection, arrondis pour lecture. Cette quantité est
une cible de sécurité calculée, pas une réception ni une consommation ajoutée.
Le 693055/Gaillac n'a pas de jours de sécurité locaux documentés et reste
hors de cette variante. Ni la BOM ni les stocks réels ne sont redimensionnés.

**Diagnostic Gaillac du 10 octobre : dates promises, fabrication et disponibilité.**
Le [bilan détaillé](../artifacts/testing/gaillac_diagnostic_20261010/bilan.md)
isole trois mécanismes sans modifier le moteur ni les sources :

- Pour 021081, les 23 achats de l'en-cours (1 320 000 kg) sont correctement
  repris, mais leurs dates de réception deviennent obsolètes. Les plans
  successifs concentrent les quantités non reçues dans la semaine courante.
  Au 10 février, 580 000 des 595 980 kg d'écart de stock proviennent des
  réceptions simulées précoces ; les semaines complètes documentées de janvier
  ne montrent aucune entrée. Ce n'est pas un excès de nouvelles commandes.
- Pour 773474, les I locaux du premier plan correspondent exactement aux
  H de Gien, décalés de sept jours. Les 20 JO de besoins locaux restent
  à 9 600 kg dans les plans des 16 et 23 mars (6 400 hors semaine courante),
  alors que la sécurité simulée basée sur les nouvelles propositions nettes
  devient nulle. Les entrées physiques brutes restent doublées par rapport
  aux bilans dans 29 semaines, sans doublon de ligne expliquant ce facteur.
- Pour 693055, trois semaines imposent qu'au moins 590 kg des entrées
  repartent dans la même semaine. Sous hypothèse de couverture du physique,
  cela exclut 28 JO systématiques **après** cette entrée H, sans identifier
  le bon stade ni justifier un délai nul. Aucune sécurité de cette référence
  à Gaillac n'est documentée dans la politique actuelle ; les 20 JO concernent Avène.

Ces constats sont [contre-vérifiés indépendamment](../artifacts/testing/gaillac_diagnostic_20261010/validation/handoff.json).
Les semaines absentes et les résidus de bilan restent inconnus ; notamment
021081 présente un résidu source de −2 270 kg du 16 au 22 juin.

**Complément amont du 9 octobre : stocks, programmes et délais.**
Le [rapprochement de G2](../artifacts/testing/amont_suite_20261009/map/audit_G2.json)
couvre les 30 couples article/site amont et 1 213 semaines de mouvements.
Les semaines sans mouvement source restent inconnues. Par exemple, les
76 800 kg reçus en simulation à Gien pour 773474 comprennent 16 000 kg sur
neuf semaines sans mouvement industriel fourni. Les 60 800 kg des 43 semaines
communes se comparent à 67 200 kg documentés ; l'écart de 6 400 kg sur ces
semaines n'est donc pas un déficit annuel démontré.

Le [croisement des délais](../artifacts/testing/amont_suite_20261009/validation/source_timing_audit.json)
apporte trois précisions :

- Les 18 semaines d'expédition positives de 773474 et les 19 de 693055
  rapprochent exactement les sorties de Gaillac et les entrées de l'usine
  destinataire dans la même semaine. Cela justifie un essai de transport
  court, sans identifier sa durée exacte ni exclure des dates comptables
  communes aux deux sites.
- `268967!FIA!F9 = 10` porte l'intitulé « Délai prévisionnel de livraison
  en jours ». Ce n'est pas explicitement dix jours passés dans un camion.
- Pour 021081, les 23 en-cours regroupés sur 14 semaines correspondent
  aux 14 semaines H du premier plan par leur date de livraison, et non par
  leur date de disponibilité. Ne pas assimiler le stock projeté K à un
  registre de stock immédiatement utilisable.

La [borne de disponibilité de 773474](../artifacts/testing/amont_suite_20261009/validation/receipt_stage_feasibility.json)
laisse 3 200 kg de sorties de février inexpliqués si toutes les productions
reconstituées attendent systématiquement 33 jours ouvrés après leur entrée
physique. Ce constat reste conditionnel : des mouvements manquent et les
identités des lots ne sont pas fournies. Il ne justifie ni de réduire le délai
source ni de remplacer les jours ouvrés par des jours calendaires.

La [comparaison des prévisions et sorties](../artifacts/testing/amont_suite_20261009/planning/dated_forecast_vs_withdrawals_latest_snapshot.json),
[contre-vérifiée dans les Excel](../artifacts/testing/amont_suite_20261009/validation/forecast_review.json),
retient la dernière version connue pour chaque couple et date d'analyse.
Elle remplace l'analyse intermédiaire qui reprenait parfois une ancienne
valeur lorsque la semaine avait disparu d'un plan plus récent. Les 3 834
positions retenues sont des comparaisons de programme et d'exécution,
pas des observations indépendantes de 3 834 mouvements ni des totaux annuels.

**BOM de Gaillac : 021081 vers 773474.** Dans `773474.xlsx!BOM`,
`C1 = Qté (G)`, `C2 = 1 000` et `F2 = 8,94 KG` : il faut théoriquement
8,94 kg de matière par kilogramme de semi-fini. Sur les **35 mêmes semaines
complètes documentées pour les deux articles**, le rapprochement donne :

| Quantité, sur ces 35 semaines seulement | kg |
|---|---:|
| Sorties source de 021081 | 794 238 |
| Entrées de 773474 compatibles avec les photos et les sorties | 83 200 |
| Matière théorique associée à ces entrées, selon la BOM | 743 808 |
| Fabrication nouvelle simulée de 773474 | 57 600 |
| Matière effectivement consommée par ces fabrications simulées | 514 944 |
| Réception simulée d'un OF déjà en cours au démarrage, séparée | 3 200 |

Le simulateur respecte exactement `57 600 × 8,94 = 514 944`.
L'écart de 6,78 % entre les deux totaux source/théorie ne mesure pas un
rendement : les entrées sont reconstituées, les en-cours peuvent déplacer la
consommation et les semaines manquantes restent hors comparaison. Les essais
de décalage hebdomadaire ne déterminent pas non plus une durée unique.
Ce calcul oriente l'analyse vers les dates et les quantités de fabrication,
sans modifier la BOM. Voir le
[détail semaine par semaine](../artifacts/testing/amont_suite_20261009/planning/production_material_alignment.json)
et la [contre-vérification finale](../artifacts/testing/amont_suite_20261009/validation/production_material_review_final.json)
(elle remplace l'oracle intermédiaire qui avait interrogé la désignation B2
au lieu de l'en-tête C1 pour l'unité ; les quantités sont inchangées).

| Constat vérifié | Conséquence pour le travail suivant |
|---|---|
| Il existe bien des stocks d'usine pour les matières et semi-finis. Les photos des deux PF concernent seulement Muret. | Ne plus confondre « pas de photo du PF en sortie d'usine » avec « pas de stock d'usine ». |
| Les colonnes `Sorties` et `Sorties_article_scan3` s'ajoutent dans les bilans des composants. | Ne pas traiter scan3 comme un sous-ensemble déjà inclus dans Sorties. |
| À Gaillac, les entrées de 773474 valent systématiquement deux fois les entrées compatibles avec les stocks sur les 41 semaines rapprochables. | Examiner cette incohérence d'export avant d'ajuster le MRP pour reproduire ces volumes. La cause du facteur deux reste inconnue. |
| Les 104 dates d'entrée des en-cours sont compatibles avec lundi–vendredi, jours fériés et fermeture du 4 au 15 août. | Distinguer le jour de livraison du jour de disponibilité ; le calendrier mérite un essai ciblé ultérieur. |
| Les nomenclatures se recoupent, mais les consommations scan3 des matières et des emballages ne conduisent pas aux mêmes quantités de PF. | Le problème ne peut pas être attribué uniquement aux commandes MRP ; le périmètre des consommations doit aussi être résolu. |
| Certaines politiques de stock et tailles de lot ont changé entre fichiers, sans date d'effet. | Conserver les versions et les choix historiques pour 2025 ; ne pas prendre automatiquement la dernière valeur pour toute l'année. |
| Le nom d'une colonne ne suffit pas : à Muret, `Sorties` contient des valeurs positives et négatives. | Ce champ ne fournit pas à lui seul les départs clients bruts. La référence acceptée reste explicitement une estimation de la réponse réelle. |

## 1. À quoi sert chaque fichier ?

Les nombres ci-dessous désignent des lignes de données, hors en-tête, sauf
mention contraire. Plusieurs fichiers reprennent les mêmes informations : ils
ne constituent pas autant de mesures industrielles indépendantes.

| Fichier | Contenu utile | Place dans l'analyse |
|---|---|---|
| `268091.xlsx` | BOM : 15 composants ; FIA : 23 conditions d'achat | Nomenclature Cicalfate et conditions fournisseur : prix, base de prix, unité, délai, quantité standard. |
| `268967.xlsx` | BOM : 8 composants ; FIA : 8 conditions | Nomenclature Permixon à Gien, dont le semi-fini 773474. |
| `773474.xlsx` | BOM : 1 composant ; FIA : 4 conditions | Fabrication à Gaillac et achats de 021081. |
| `Data_poc.xlsx` | Acteurs, relations, BOM et paramètres de démonstration | Version structurelle ancienne ; certaines références et relations sont dépassées. |
| `demand_PF.xlsx` | Structure enrichie, 104 lignes de demande, trajets et machines | Ancienne demande de comparaison ; ses deux colonnes de demande sont identiques et son calendrier reste implicite. |
| `Extract_Données_Complémentaires.xlsx` | 32 stocks initiaux, 25 politiques, 3 tailles de lot | Photo de départ et ancienne version des règles ; à conserver pour comprendre 2025. |
| `Extract_En_cours.xlsx` | 104 positions du carnet : quantités, sites, dates prévues de livraison et de disponibilité ; statut ferme et prélèvement matière non renseignés | Initialisation du carnet prévu au démarrage, distinct de l'historique exécuté. |
| `Flow_Data_Inventory_and_Replenishment_rules.xlsx` | 1 646 photos, 27 politiques, 4 tailles de lot ; onglet Graph | Source détaillée de stock daté et version actualisée des paramètres. Graph est une présentation des stocks, pas une nouvelle observation. |
| `Flow_Data_Inventory_movements.xlsx` | 1 319 mouvements hebdomadaires | Rapprochement physique des stocks, entrées, sorties, consommations scan3 et ajustements. |
| `Flow_Data_MRP_results.xlsx` | 53 398 lignes, 52 versions de plan, 33 couples article/site | Ce qui était prévu à chaque calcul MRP, pour chaque semaine future. Ce ne sont pas des mouvements exécutés. |
| `Flow_Data_Customer_Demand.xlsx` | 106 lignes historiques ; 1 352 prévisions | Historique daté et 13 versions prévisionnelles de 52 semaines par PF. |
| `CA_Perdu_Réel.csv` | 522 lignes, 261 jours ouvrés par PF en 2025 | CA livré et perdu, avec corrections signées. Pas de quantité livrée ni de prix de vente explicite. |
| `Dispo_PF_Projeté.csv` | 64 lignes, 32 dates de calcul par PF | Nombres de semaines de rupture projetées ; horizons qui se recouvrent, pas service réalisé. |
| `Stock_PF_Immobilisé.csv` | 104 valorisations hebdomadaires | Valeur financière des PF, sans ventilation explicite usine/dépôt. |
| `Stock_Composants_Immobilisé_Cos.csv` | 52 valorisations | Agrégat financier cosmétique, périmètre à rapprocher des stocks détaillés. |
| `Stock_Composants_Immobilisé_Pharma.csv` | 52 valorisations | Agrégat financier pharmaceutique, même réserve de périmètre. |
| `Fournisseur.xlsx` | 31 comptes/localisations, dont 4 sites internes | Identité et géographie ; les sites internes ne sont pas tous des fournisseurs externes. |
| `Trame_Audit_Fournisseur.xlsx` | 4 onglets d'évaluation, 810 cellules avec formule | Questionnaire et calculs de maturité/résilience ; exemple lié à VD0993480A. |
| `Trame d'audit fournisseur finalisé.xlsx` | Autre version des mêmes 4 onglets, 810 cellules avec formule | Réponses et scores différents ; le mot « finalisé » ne démontre ni une date d'effet ni un audit industriel indépendant. |
| `supplier_public_evidence.csv` | 31 pièces documentaires, 20 fournisseurs | Contexte public stocké localement, avec URL, date, périmètre et confiance. |
| `supplier_context_proxies.csv` | 29 fournisseurs | Signaux dérivés de contexte, pas observations de retard ni probabilités de défaillance mesurées. |
| `supply_graph_poc.json` | 26 articles, 36 nœuds, 39 liaisons, 1 scénario | Graphe dérivé comportant de nombreuses valeurs par défaut ; ce n'est pas une source industrielle primaire. |

## 2. Quels stocks possède-t-on réellement ?

La bonne identité est **article + site + unité + date**. Une même référence à
Gaillac et à Gien désigne deux stocks distincts. Son type peut dépendre du site :
773474 est PFI à Gaillac et MP à Gien dans le fichier actualisé.

| Site | Articles avec photos de stock |
|---|---|
| **Avène — 1810** | 001757, 001848, 001893, 002612, 007923, 016332, 029313, 039668, 049371, 055703, 099439, 338928, 338929, 426331, 693055 |
| **Gaillac — 1450** | 001893, 002612, 021081, 693055, 773474 |
| **Gien — 1430** | 001848, 007923, 038005, 042342, 333362, 344135, 708073, 730384, 734545, 773474 |
| **Muret — 1920** | 268091, 268967 |

Il y a **32 couples article/site** : 31 possèdent 53 photos du 1er janvier au
29 décembre 2025 ; 344135/Gien n'a que trois photos, en fin décembre.
L'ancien fichier donne cependant un stock initial nul pour 344135/Gien.
Le MRP contient aussi **029313/Gien**, absent des photos : les huit lignes
identifiées sont nulles. Ce n'est pas une série de stock mesurée supplémentaire.

**Stock de PF en sortie d'usine :** aucune série de photos pour 268091/Avène
ou 268967/Gien n'a été trouvée dans Stocks, les mouvements ou les groupes MRP.
Les lots de fabrication et les ordres O.Proc attestent des opérations à l'usine,
mais ne fournissent pas la quantité présente chaque semaine après fabrication.
Les CSV financiers ne permettent pas non plus de l'isoler directement.

**Règle usine PF → Muret reconfirmée par l'utilisateur le 8 octobre :**
l'industriel pousse au centre de distribution les produits fabriqués, une fois
le contrôle/libération terminé à l'usine. L'expédition ne dépend donc pas d'une
nouvelle commande client ; le pilotage des quantités à fabriquer reste distinct.
Le produit reste à l'usine pendant son contrôle et l'attente du départ, puis en
transit avant son arrivée à Muret. Ce principe ne signifie pas un stock usine
constamment nul ni une arrivée instantanée au dépôt.

La **fréquence réelle des départs reste inconnue** : une fois par semaine ou
plusieurs fois. Les photos et mouvements hebdomadaires ne permettent pas de
départager ces cadences. Un total hebdomadaire de 100 000 unités pourrait provenir
d'un seul départ ou de plusieurs. La confirmation du principe vient de
l'industriel, rapportée par l'utilisateur ; l'absence de photos de PF à l'usine
n'est pas, à elle seule, sa preuve. Toute cadence simulée reste une hypothèse
logistique tant qu'un calendrier ou un journal de transferts ne la documente pas.

Gaillac cumule un rôle de fabrication et de stockage/transfert. Les flux agrégés
corroborent les liaisons : **67 200 kg** de sorties de 773474 à Gaillac et autant
d'entrées à Gien ; **13 190 kg** de sorties de 693055 à Gaillac et autant d'entrées
à Avène. Ce rapprochement de volumes ne donne pas les identifiants des transports
ni leur durée exacte. La fabrication de 693055 à Gaillac est confirmée par
l'utilisateur, mais sa BOM amont n'est pas fournie : une matière fictive resterait
une convention de simulation clairement identifiée.

## 3. Lire correctement les dates, les signes et les unités

### Stocks et mouvements physiques

Pour les matières, emballages et semi-finis, le bilan à vérifier est :

```text
variation du stock = Divers + Entrées + Sorties + Sorties_article_scan3
```

Les sorties sont déjà signées. **Il faut additionner leurs valeurs signées**,
et non retrancher une deuxième fois leur signe. Scan3 s'ajoute à Sorties dans cet
export : 36/36 bilans pour 333362/Gien et 43/43 pour 773474/Gien, contre 12/36
et 14/43 si l'on omet scan3. L'utilisateur a indiqué que scan3 concerne seulement
268091 et 268967 ; ce sens métier reste la convention, avec la contradiction BOM
décrite plus loin.

Le repère du dimanche dans **Inventory_movements** se rapproche beaucoup mieux
du stock du **lundi suivant au lundi suivant + 7 jours** : **1 161/1 298** bilans
concordent, contre 33/1 273 avec la semaine précédente. Une ligne absente n'a
pas été remplacée par zéro. Ce résultat concerne cet export ; il ne prouve pas
que tous les autres fichiers utilisent la même convention hebdomadaire.

À Muret pour les PF, Entrées et scan3 sont toujours nuls tandis que Sorties est
positif ou négatif. Ce champ se rapproche d'un **mouvement net**, sans séparation
fiable des réceptions d'usine et des départs clients. Le bilan avec les photos
ferme sur 39/52 intervalles pour Cicalfate et 47/52 pour Permixon, première
période partielle comprise. Les écarts restants doivent rester visibles.

### Plans MRP

Il faut garder simultanément la **date de calcul** et la **semaine prévue**.
Les 52 versions vont du 5 janvier au 28 décembre 2025 ; l'horizon atteint
364 jours après le calcul, jusqu'au 27 décembre 2026. Il peut donc y avoir
53 repères en incluant la semaine courante. L'export n'est pas une grille pleine.

Pour un article/site et une version donnés, après tri des semaines :

```text
K(t) = K(t précédent) + H(t) − I(t) + J(t)
H = Entrée prévue ; I = Sortie prévue ; J = Stock_physique ; K = Stock fin de semaine
Pour la première ligne de la version, K(t précédent) = 0.
```

**53 398/53 398 bilans se ferment.** C'est un contrôle arithmétique de l'export,
pas la démonstration que notre moteur reproduit ses règles de décision.

L'utilisateur a confirmé que J placé dans le futur est du stock déjà présent,
mais disponible plus tard. **800 lignes** présentent un J futur non nul.
Ce n'est pas une nouvelle réception à ajouter au physique déjà présent.
Même en sommant J dans la version, le rapprochement avec les photos ne concorde
que dans **1 131/1 615 cas**. Les 484 écarts concernent aussi des PF, des emballages
et Gaillac : ils ne s'expliquent pas tous par les matières partagées.

Ne jamais additionner les entrées de toutes les versions pour calculer les
réceptions annuelles : une même proposition peut être répétée, avancée ou reportée.
Ces données permettent d'estimer des replanifications hebdomadaires, mais pas
d'identifier sans ambiguïté chaque ordre individuel.

### En-cours et calendrier

`Extract_En_cours` contient **53 AVICDE, 29 ECHCDE et 22 O.Proc**. Les dates de
livraison vont du 3 janvier au 21 mai, les dates d'entrée du 6 janvier au
19 septembre 2025. L'état exact de prélèvement des composants des O.Proc n'est
pas documenté par un identifiant/statut matière.

**Audit du 10 octobre 2026 : usage au démarrage.** Les 104 lignes concernent
21 articles et 24 couples article/site. Le fichier ne donne ni numéro d'ordre,
ni date de création, ni statut de lancement, ni date métier d'extraction.
Le rapprochement avec le premier plan MRP du 5 janvier soutient son usage
comme carnet d'ouverture : **49/49 groupes d'achats comparables** retrouvent
exactement H dans la semaine de livraison prévue. Tous types confondus,
50/51 groupes concordent ; les 3 200 kg de fabrication de 773474 sont
compatibles avec les 9 600 kg agrégés prévus, sans identification de cet OF.
Ce rapprochement ne prouve pas l'exécution.
Seuls 7/50 groupes ayant des mouvements physiques documentés retrouvent la
même quantité dans la semaine prévue, sans identification individuelle des
commandes.

G2/G3 importent **88 lignes Extract** ; les 16 lignes de la division 1820,
non représentée, sont exclues sans les réaffecter à Avène. Deux compléments
de 7 000 kg de 001848/Gien portent le carnet simulé à **90 lignes** : ils
proviennent du premier MRP, avec une hypothèse de reprise au 1er janvier
explicitement déclarée, et non d'Extract. Une échéance après janvier
n'exclut pas une commande du carnet initial. Couper les livraisons au
31 janvier supprimerait **53 des 88 lignes**, dont **880 000 kg de 021081**
déjà présents dans le premier plan.

La limite principale est le classement de **tous les 22 O.Proc en fabrication
déjà engagée avec matières incorporées avant J0**. Cela représente 1 945 715 UN
de 268091, 600 kg de 693055 et 3 200 kg de 773474. L'extrait ne démontre pas
ce statut matière ; les emballages d'Avène sont, eux, consommés séparément
pendant la simulation. Conserver un ordre initial et considérer ses matières
comme déjà consommées sont deux décisions différentes. Ne pas appliquer
non plus une consommation supplémentaire sans vérifier le risque de double
prélèvement. Les réceptions réelles futures servent à vérifier le carnet,
pas à sélectionner rétrospectivement les ordres qu'on aurait connus à J0.

Le [bilan détaillé](../artifacts/testing/extract_en_cours_audit_20261010/bilan.md)
donne la règle proposée, les lignes sources, les limites et un défaut de
correspondance fournisseur sur 12 achats initiaux. Les dates calculées par
soustraction du délai ne constituent pas des dates réelles de création.
Cet audit ne modifie ni le moteur ni la référence G2.

Le calcul `date de livraison + temps de réception`, sans compter le jour de
livraison lui-même, reproduit :

| Calendrier testé | Dates d'entrée exactes |
|---|---:|
| Lundi–vendredi | 70/104 |
| Lundi–vendredi hors jours fériés français | 99/104 |
| Idem, hors fermeture du 4 au 15 août 2025 inclus | **104/104** |

Deux agents l'ont recalculé indépendamment, avec des méthodes différentes.
Les cinq lignes qui nécessitent la fermeture sont **23, 25, 30, 39 et 42**.
La liste des jours exclus et les 104 dates sont conservées dans la preuve locale.
Cela appuie fortement ce calendrier pour **ces en-cours**, sans démontrer qu'il
faut l'appliquer à tous les transports, achats et sites. Les dates explicites
des engagements initiaux doivent être conservées avant toute recomputation.

Les durées diffèrent aussi entre les en-cours et le Flow MRP : par exemple
001848/Gien **14 → 26**, 338929/Avène **4 → 6**, 693055/Gaillac **21 → 28**,
773474/Gaillac **26 → 33** jours. Ce sont des divergences de paramètres entre
sources, pas des retards de livraison mesurés.

### Unités et montants

Les conversions utilisées sont `G / 1 000 = KG`, `ZUN = UN`, et `M` reste un
mètre. Aucun stock ni mouvement physique source en UN n'est fractionnaire.
Une base de prix de 1 000 porte sur le **prix**, pas automatiquement sur la
quantité commandée. Ainsi, 338929 a une quantité standard FIA de **5 000 ZUN**,
soit 5 000 unités, pas 5 000 kg ni 5 millions d'unités.

Les onglets de taille de lot ne portent pas eux-mêmes de colonne d'unité.
Les valeurs brutes 3 200 000 pour 773474 et 600 000 pour 693055 sont interprétées
en grammes par rapprochement avec les quantités et les autres tables, soit
**3 200 et 600 kg**. Cette conversion est une déduction documentée.

## 4. Actualisations, redondances et versions à conserver

| Comparaison | Résultat | Usage retenu |
|---|---|---|
| Stocks initiaux ancien/nouveau au 1er janvier 2025 | 31 des 32 couples anciens retrouvés ; 27 quantités strictement identiques et quatre petits écarts de précision/quantité (002612, 038005, 042342, 055703). 344135/Gien, ancien stock nul, n'a pas de photo au 1er janvier dans Flow. | Continuité initiale très forte ; conserver les valeurs brutes et leur précision. |
| Politique PF 268091/Muret | 20 → 0 jours | Nouvelle valeur présente, date d'effet absente ; ne pas annuler silencieusement une décision de scénario. |
| Politique PF 268967/Muret | 25 → 60 jours | Même réserve ; l'utilisateur a demandé de revenir au régime 2025 pour ses essais historiques. |
| Politique 426331/Avène | 7 → 10 jours | Actualisation identifiée, date d'effet inconnue. |
| Politiques Gaillac ajoutées | 773474 : 20 jours ; 021081 : 900 000 kg de sécurité fixe | Données nouvelles à considérer pour les essais, sans inventer leur date d'application. |
| Fabrication 268091 | Minimum 14 400 → 28 800 UN ; maximum 142 485 inchangé | Distinguer minimum de production, palette et multiple imposé. |
| Fabrication 693055 | Lot fixe ajouté, 600 kg après conversion | Complète le rôle fabricant de Gaillac. |
| BOM primaires contre demand_PF | 24 coefficients concordants après normalisation | Les fichiers primaires et la copie structurelle se corroborent. |
| Prix FIA contre copies structurelles | 29 correspondances Data_poc + 35 demand_PF concordantes | Une même information répétée, pas 64 observations nouvelles. |
| Data_poc contre demand_PF | Ancien 693710 remplacé par 007923 ; fabrication de 773474 à Gaillac ajoutée | Data_poc n'est plus une description complète de la structure courante. |
| Flow Customer actuel contre `8ac4831d4` | 106 historiques et 1 352 prévisions inchangés ; suppression de `SKU Label` | Actualisation de structure, pas nouvelle demande chiffrée. |
| demand_PF, colonnes prévision/réel | Égalité exacte sur les 104 lignes | Ne pas utiliser ces deux colonnes comme prévision et réalisation indépendantes. |
| Overview Data_poc / demand_PF | Onglets identiques ; 11 juin 2025, 11 pas | Métadonnées de démonstration impropres à dater seules les 52 semaines de demande. |
| Les deux audits fournisseurs | 337 cellules non vides différentes ; Mode d'emploi identique | Versions différentes, pas fichiers identiques ; ni date ni auditeur renseignés. |
| CSV de valorisation / Excel de stock | Aucun des 104 montants PF identique au centime | Périmètre ou valorisation différente ; ne pas supprimer comme doublon. |

Le nom « dernier fichier » ne suffit donc pas à décider qu'un ancien fichier
est inutile. Les anciennes politiques, les en-cours et les valorisations
conservent une information distincte. Cette passe ne supprime aucun original.

**Raccordement historique vérifié pour le facteur 4,55 (9 octobre).** Au
1er janvier, l'ancien `Extract_Données_Complémentaires/Stocks` et la photo de
même date du fichier Flow donnent tous deux **1 010 kg de 693055 à Avène**,
**354 000 étuis 338929**, **404 065 tubes 338928** et **430 538 PF 268091 à
Muret**. Les 950 kg de 693055 cités dans les bilans annuels sont ceux du
**6 janvier** : la diminution de 60 kg correspond au mouvement
`Inventory_movements!J1064 = −60 000 G`, repéré au 29 décembre 2024. Le bilan
ferme entre les deux photos, sans que cette égalité documente une date de
prélèvement journalier ni l'heure de coupe de l'export.

La BOM historique `Data_poc/BOM!G43:L43` donne déjà **406 G de 693055 pour
1 000 PF** ; les lignes 45–46 donnent un tube et un étui par PF. Les 57 600
étuis et 365 033 tubes des anciens en-cours (`Extract_En_cours!E101` et
`E98:E100`) se retrouvent dans les entrées prévues du premier plan MRP
(`Flow_Data_MRP_results!H705/H664`, version et horizon du 5 janvier).
Il s'agit d'engagements/plans, pas de réceptions exécutées démontrées. Les
sources anciennes ne montrent donc ni changement de base BOM ni multiplication
des stocks par 4,55 ; elles ne permettent pas, à elles seules, d'attribuer les
consommations annuelles aux ordres de conditionnement.

L'ancienne anomalie **002612/Gaillac = 1 250 414 kg** n'est **plus présente** :
la source actuelle donne **1 250 kg**, valeur **1 575**, le 6 janvier, ligne 946
de Stocks. Les photos voisines donnent 414 kg au 1er janvier et 1 664 kg au
13 janvier. Il subsiste donc une question de raccordement au démarrage, mais
il ne faut plus répéter le facteur 1 000 comme anomalie actuelle.

## 5. Anomalies et déductions qui comptent pour la suite

### 773474 à Gaillac : un facteur deux dans les entrées exportées

Sur les semaines rapprochables, le bilan avec Entrées intégral ferme **12/41**
fois ; avec Entrées divisées par deux, **41/41** fois. Les 29 entrées positives
du fichier sont toutes de **6 400 kg**, alors que les variations de stock et
les sorties correspondent à **3 200 kg**.

```text
Stock initial                    9 600 kg
Stock final                     35 200 kg
Sorties exportées               67 200 kg
Entrées impliquées par le bilan 35 200 − 9 600 + 67 200 = 92 800 kg
Somme Entrées dans le fichier   185 600 kg
```

Exemple contrôlable : ligne mouvement **1282**, repère du 19 janvier ; photos
Stocks **1240 et 433**, 20 et 27 janvier : le stock passe de 6 400 à 9 600 kg,
sans sortie, mais la colonne Entrées indique 6 400 kg.

**Le facteur est constaté ; sa cause n'est pas démontrée.** Double comptage
d'export, périmètre ou type de mouvement restent des explications possibles.
Ce n'est surtout pas une règle MRP à généraliser : pour 693055/Gaillac, les
entrées normales ferment 34/36 bilans ; leur moitié seulement 16/36.
Aucune correction `/2` n'a été appliquée aux sources ni à la simulation.

### Les consommations scan3 et la BOM ne décrivent pas encore le même volume

En divisant la consommation scan3 par la quantité de composant nécessaire à
un PF selon les BOM sources, sur les semaines exportées du 5 janvier au
28 décembre :

| Chaîne | Quantité de PF équivalente d'après les matières | D'après les emballages |
|---|---:|---:|
| Cicalfate | Environ **24,23 millions**, de façon très cohérente entre les 12 matières | Environ **5,02 millions** pour les étuis, **5,04 millions** pour les tubes |
| Permixon | Environ **5,80 à 6,08 millions** selon les matières | Environ **1,26 à 1,31 million** pour les emballages avec consommation documentée, hors 344135 |

Exemple : **049371**, environ 36 408 kg consommés, pour 0,0015022 kg par PF dans
la BOM, représente environ 24,24 millions de PF équivalents. Le même ordre de
grandeur ressort pour 001848.

Cette cohérence par groupe indique une différence systématique de périmètre,
d'unité de production ou d'affectation entre matières et conditionnement.
Elle **ne prouve pas** que toutes ces matières sont partagées, ni qu'il suffit de
multiplier une BOM par cinq. La BOM source et la confirmation utilisateur sur
scan3 sont conservées ; leur incompatibilité apparente reste explicitée.
Les matières confirmées partagées par l'utilisateur sont notamment 002612,
007923, 042342, 693055, 730384 et 708073. Cette confirmation ne permet pas de
choisir automatiquement un pourcentage d'affectation aux deux PF.

### Les prévisions sont réellement différentes des historiques

Flow Customer contient 13 versions de 52 semaines par PF, avec des horizons
jusqu'au **28 décembre 2026**. La première version est datée du 30 décembre 2024 ;
les suivantes sont datées de 2025. Ce sont des prévisions, pas des ventes 2026.

Sur les **51 semaines complètes de 2025**, en choisissant pour chaque lundi la
dernière version déjà connue qui contient cette semaine :

| Produit | Prévision source cumulée | Historique Flow cumulé |
|---|---:|---:|
| 268091 | 9 404 597 | 4 145 843 |
| 268967 | 2 965 870 | 1 691 923 |

L'écart est dans les cellules sources. Il peut combiner erreur de prévision et
différence de périmètre ; on ne peut pas le faire disparaître en renommant une
courbe. Les prévisions doivent être sélectionnées **à la date où elles étaient
connues**, sans utiliser rétrospectivement une version future.

### Demande, réponse et finance : conserver les définitions

La référence nominale emploie désormais deux rôles distincts du classeur
`Flow_Data_Customer_Demand.xlsx` : `Historique / Actual Demand` pour la demande
client exécutée en 2025 et `Projection / Forecasted Demand` pour la prévision
MRP datée, en retenant seulement la dernière version connue à la date de
décision. `demand_PF` reste une ancienne référence de comparaison ; ses colonnes
`forecast_demand` et `real demand` sont identiques sur les 104 lignes et ne
constituent donc pas deux signaux indépendants. Aucune réponse en unités n'est
estimée à partir du CA livré.

L'audit confirme les limites de ces rapprochements :

- `demand_PF` ne date pas ses lignes ; l'ancrage hebdomadaire est une convention
  du scénario, pas une date écrite dans chaque cellule.
- Sur les 52 semaines rapprochées, demand_PF corrigé et Flow Historique sont
  égaux seulement 16 fois pour Cicalfate, 49 fois pour Permixon.
- Les semaines Flow Permixon du 21 avril, 28 avril et 26 mai valent zéro, alors
  que le CA livré est positif. Les quatre semaines demand_PF négatives ont
  également du CA livré positif.
- `CA_Perdu_Réel` donne des montants signés, sans prix de vente ni devise
  explicite. Sur l'année, `somme(CA livré) / somme(CA livré + CA perdu)` vaut
  **92,87 % pour Cicalfate et 95,40 % pour Permixon**. Ce n'est ni un comptage des
  unités livrées ni un taux de livraison à l'heure.
- La correction de CA perdu **−45,86** de Cicalfate, le 9 octobre, reste signée.
  `Nb_Rep_CA_Perdu = 0` n'implique pas partout une perte financière nulle.

Sous l'hypothèse « Flow Historique = sorties clients », on peut calculer
`réceptions Muret = variation stock + sorties clients − autres ajustements`.
Les réceptions ainsi déduites sont non négatives dans **50/51** semaines pour
chaque PF, dont 20 valeurs nulles pour Permixon. C'est un indice favorable,
**pas une identification certaine** : une semaine négative subsiste par PF et
les contradictions avec le CA restent présentes.

### Les valorisations ne permettent pas d'inventer un stock usine

L'Excel valorise les PF à un taux fixe de **0,50035** pour Cicalfate et **2,43404**
pour Permixon par unité. Le quotient entre la valeur CSV et la quantité Muret
varie respectivement de 0,47522 à 0,60673 et de 2,26334 à 2,36986.
Les agrégats de composants ne correspondent pas non plus exactement aux sommes
détaillées des sites candidats.

Un résidu financier peut venir du coût utilisé, du périmètre, de la date ou
d'un autre stock. **Il ne suffit pas à calculer un stock de PF à Avène ou Gien.**
Il faudrait le stock initial usine, la production effectivement terminée et les
départs physiques, ou une ventilation financière et un coût unitaire confirmés.

### Autres points à garder visibles

- Sur les intervalles **16→23 juin et 23→30 juin**, **18 couples article/site**
  ont des écarts opposés qui se compensent. 773474/Gaillac présente séparément
  deux écarts de −3 200 kg avec ses entrées brutes. Un décalage de comptabilisation
  ou de photo est plausible pour les écarts opposés ; aucune cause industrielle
  commune n'est prouvée.
- Les lignes **63 et 66** des en-cours sont identiques : 049371/Avène, 1 800 kg,
  livraison 17 janvier, entrée 29 janvier. Sans numéro d'ordre, ce peut être deux
  commandes égales ou un doublon d'export. Ne pas en supprimer une automatiquement.
- Le site **1820** figure dans les en-cours : ne pas le fusionner avec 1810 sans
  correspondance documentée.
- Les acteurs utilisent D1920 pour Muret, certaines relations DC-D1910/DC-1910.
  Ce sont des incohérences d'identifiant à résoudre dans la normalisation.
- Les trajets de demand_PF concernent des exemples internationaux ; ils ne
  documentent pas les délais réels Gaillac–Gien ou usine–Muret.

## 6. Achats et contexte fournisseur

Les FIA donnent **35 conditions article/fournisseur**. Elles permettent de
comparer prix ramenés à une même unité, délai annoncé et quantité standard.
Une quantité standard ne démontre pas, à elle seule, un minimum obligatoire ou
un multiple imposé. Le calendrier des délais FIA n'est pas explicité dans la
colonne « jours », contrairement aux jours ouvrés de sécurité.

Pour 001848, les deux conditions confirment : **1,58 EUR/kg, 56 jours, 6 000 kg**
chez VD0951020A, et **4,20 EUR/kg, 21 jours, 4 000 kg** chez VD0519670A.
L'utilisateur a confirmé principal économique/secours rapide pour ce cas.
Les conditions de prix/délai peuvent guider une règle commune candidate ; elles
ne prouvent pas une préférence automatique identique pour tous les achats.

Les audits fournisseurs partagent un même identifiant VD0993480A marqué
« Simulation », mais des en-têtes RAJA/FABRE et des réponses différents. Les
337 différences de cellules incluent des réponses et scores. Les dates et
l'auditeur sont vides ; leurs scores ne sont donc pas des probabilités de panne
mesurées pour les 29 fournisseurs du modèle.

Les 31 pièces publiques stockées couvrent 20 fournisseurs et plusieurs types
de faits, souvent à l'échelle d'un groupe plutôt que du site fournisseur exact.
Quatre lignes de proxies ont `source_count = 0`. Des pièces sont datées de
fin 2025 ou 2026 : elles ne peuvent pas être utilisées comme une connaissance
disponible en janvier 2025. Cette passe a vérifié **le contenu local et ses
liaisons**, pas l'actualité des pages Internet ni la véracité externe de chaque
affirmation. Les scores de confiance sont des appréciations, pas des intervalles
statistiques estimés sur des retards industriels.

Le graphe `supply_graph_poc.json` contient **203 indicateurs de valeur par défaut**,
des délais de transport de cinq jours et des stocks PF usine nuls par défaut.
Il conserve aussi des mentions de fichiers anciens. Il faut remonter aux Excel
pour attribuer une valeur à l'industriel. Ce graphe historique ne représente pas
nécessairement l'état de la référence demande/DC actuellement figée.

## 7. Quelle source utiliser pour quelle question ?

| Question | Source prioritaire et règle de lecture |
|---|---|
| Combien de matière est physiquement présente ? | Photos Stocks, article/site/date/unité ; ne pas remplacer une absence par zéro. |
| Qu'est-ce qui a fait varier le stock ? | Mouvements signés rapprochés des photos ; conserver les exceptions identifiées. |
| Qu'était-il prévu de recevoir ou consommer ? | Une version datée du Flow MRP ; distinguer J existant de H entrant. |
| Quels engagements existaient au démarrage ? | En-cours avec leurs dates explicites ; éviter de les commander une seconde fois. |
| Quelle demande prévoir à une date donnée ? | Dernière version Flow Customer connue à cette date et couvrant la semaine. |
| Quelle demande est injectée dans la référence nominale ? | En 2025, `Flow_Data_Customer_Demand / Historique / Actual Demand`, convertie en quantité positive entière. Après l'historique, scénario explicite de répétition saisonnière avec croissance ; `demand_PF` reste un comparateur antérieur. |
| Quelle consommation théorique pour produire ? | BOM primaires, coefficient et unité ; registre physique séparé pour la consommation exécutée. |
| Quel fournisseur, prix et lot standard ? | FIA primaires ; copies Data_poc/demand_PF comme contrôle, pas nouvelle preuve. |
| Quelle sécurité et quelle taille de fabrication ? | Ancienne et nouvelle politique conservées avec la version choisie ; date d'effet industrielle inconnue. |
| Quel service financier a été réalisé ? | CA livré/perdu signé sur le même intervalle ; aucun mélange avec un taux physique ou projeté. |
| Quel risque fournisseur ? | Audit/contexte et dates propres ; ne pas confondre proxy et fréquence mesurée. |

Les conventions confirmées restent séparées des données : quantités physiques
UN entières ; sécurité et réception en jours ouvrés lundi–vendredi ; contrôle
des PF à l'usine avant expédition ; fermeture Avène du 4 au 15 août ; Gaillac
fabricant de 693055 sans BOM amont fournie ; `tau_process` reste une convention
de planification. L'indication d'environ un an de stock sur la chaîne Permixon
est un objectif de chaîne, pas un an à imposer séparément à chaque nœud.

## 8. Ordre de travail recommandé après cet audit

### Comparaison ajoutée : flux usine et production estimée

Le [nouvel HTML](../resultats/factory_activity_20261008/comparaison.html) réutilise
les simulations courante et précédente. Il ne modifie aucune règle MRP.

- **Flux usine :** entrées `H` contre entrées physiques simulées ; prélèvements
  `−J Sorties_article_scan3` contre prélèvements BOM exécutés. Les autres sorties
  `I` restent séparées : ce champ peut contenir des transferts ou des corrections,
  et n'est pas automatiquement une consommation pour les deux produits étudiés.
  Un `I` positif ne supprime pas la comparaison de `J`.
- **Conditionnement estimé :** consommation Scan3 de l'emballage divisée par
  son coefficient BOM. Pour Cicalfate, les étuis 338929 constituent un indicateur,
  les tubes 338928 un recoupement indépendant ; pour Permixon, les étuis 333362
  donnent le repère principal. Les autres composants restent des diagnostics
  d'équivalence BOM, sans moyenne ni correction arbitraire des coefficients.
- **Gaillac :** `entrées impliquées = variation stock − Divers − Sorties − Scan3`,
  en conservant les signes sources. Leur attribution à la fabrication repose
  sur le rôle fabricant du site ; le bilan ne date pas chaque achèvement.
  Les entrées `H` brutes restent accessibles, notamment leur incohérence pour 773474.
- **Simulation :** production physique, fabrication issue des en-cours initiaux,
  disponibilité après contrôle et éventuels apports amont simplifiés sont séparés.
  Une libération n'est pas une seconde fabrication. Un ordre initial prévu dans
  l'Excel n'est pas une preuve d'exécution industrielle.

Les comparaisons utilisent les mêmes semaines lundi–dimanche, correspondant
au lundi suivant le repère des mouvements. Aucune semaine absente n'est remplacée
par zéro, aucune quantité industrielle n'est ventilée artificiellement par jour.
Le prélèvement des emballages peut précéder l'achèvement, et les rebuts ou corrections
peuvent affecter son volume : l'estimation reste un indicateur de conditionnement,
pas une déclaration de production. Aucun décalage de fabrication n'est déduit de
`tau_process`. Les quantités équivalentes calculées peuvent être fractionnaires ;
elles ne constituent pas des stocks physiques UN.

1. **Fiabiliser les comparaisons physiques** : mêmes intervalles, mêmes unités,
   sorties additives, traitement séparé de l'anomalie 773474/Gaillac et des
   décalages de juin. Cela évite de calibrer le moteur contre un total incohérent.
2. **Tester le calendrier des en-cours**, sans perdre les dates explicites des
   engagements, puis comparer les effets aux autres références.
3. **Résoudre le rapprochement BOM/scan3** par groupes matières/conditionnement,
   sans coefficient arbitraire ni déclaration de partage non démontrée.
4. **Versionner les politiques et la prévision** : dire quelle règle était
   disponible à quelle date, au lieu de mélanger paramètres actuels et année 2025.
5. **Reprendre ensuite les essais MRP annuels**, avec comparaison de toutes les
   références et conservation de la référence demande/DC. Aucun de ces essais
   n'a été lancé dans cette passe de connaissance.

### Diagnostic Gaillac du 8 octobre : besoins aval, planification et exécution

L'analyse du calcul `demand_pf_20261008/run_pf_zero_362` conserve la référence
demande/client et ne modifie ni le moteur ni les sources. Le
[rapport chiffré](../artifacts/testing/gaillac_diagnostic_20261008/analysis.json)
conserve les semaines, lignes Excel, événements exécutés et empreintes relus.

**Le déficit de fabrication commence par les consommations aval.** Sur les
mêmes semaines documentées, les autres usages `I` sont bien exécutés ; ce sont
les prélèvements BOM des fabrications propres qui restent très inférieurs à
`Scan3`. Les valeurs ci-dessous sont arrondies au kg, pas les calculs conservés.

| Matière à l'usine aval | Semaines communes | Scan3 source | Prélèvement BOM simulé | Autres usages : source = simulation |
|---|---:|---:|---:|---:|
| 773474 — Gien | 43 | 56 027 kg | 10 106 kg | 10 641 kg |
| 693055 — Avène | 47 | 9 840 kg | 848 kg | 2 160 kg |

Les semaines sans mouvements sources restent exclues de ces totaux. Le moteur
ajoute sur ces semaines des usages estimés : ils ne constituent pas de nouvelles
observations industrielles. Aucune consommation Scan3 n'est reclassée ici comme
usage d'un autre produit.

**Le total des besoins industriels internes est actuellement comparatif.**
La politique `industrial_requirement_reconciliation_policy = separate_own_and_other_v1`
conserve les besoins issus des fabrications simulées et des autres usages
identifiés. `_audit_separate_own_and_other` dans `mrp_planning.py` calcule
`planning_qty = own + other`, puis restitue les besoins d'origine. Le total `I`
des plans MRP ne les remplace pas, même sur une semaine renseignée. L'autorité
du besoin industriel sur les achats d'étuis 338929/333362 est une autre règle ;
elle n'est pas activée pour ces deux semi-finis internes.
Les versions MRP restent utilisées pour les prévisions des autres usages :
c'est leur total industriel qui ne remplace pas les besoins propres BOM + autres,
et non l'ensemble des données MRP qui serait ignoré.

Le moteur planifie les transferts puis les fabrications de Gaillac sur leurs
dates de lancement. Une proposition future ne déclenche pas une fabrication
immédiate. Il n'exécute aucun nouveau lot de 773474 avant le **17 juin**, et
aucun nouveau lot de 693055 avant le **30 septembre**, en dehors des OF initiaux.
Les onze décisions de fabrication exécutées à Gaillac ne présentent aucun
blocage matière ou capacité dans les CSV ; la capacité usine reste non modélisée.
Ce constat ne certifie donc pas la capacité industrielle disponible.

**Les faibles volumes se décomposent par conservation de matière.** Sur les
41 semaines communes de 773474, l'écart d'entrées vaut :

```text
92 800 − 25 600 = 67 200 kg
               = (67 200 − 19 200) de départs
               + (25 600 − 6 400) de variation de stock.
```

Pour 693055, sur 36 semaines communes :

```text
11 400 − 1 200 = 10 200 kg
              = (13 190 − 3 000) de départs
              + (−1 790 − (−1 800)) de variation de stock.
```

Ces périodes sont discontinues : leurs variations cumulées ne sont pas
nécessairement la différence entre le premier et le dernier stock simulé. Sur
les 362 jours complets du calcul, Gaillac fabrique 28 800 kg de 773474 et
2 400 kg de 693055, OF initiaux compris. Ne pas les substituer aux totaux sur
semaines appariées. Une libération de stock n'est pas une nouvelle fabrication.

**La discordance BOM/Scan3 persiste après alignement des semaines.** Sur
33 semaines communes à Gien, 47 794 kg de 773474 représentent 4 950 305 PF
équivalents selon la BOM, contre 1 109 680 étuis : facteur 4,46. Sur 45 semaines
à Avène, 9 540 kg de 693055 représentent 23 497 537 PF équivalents, contre
4 942 300 étuis : facteur 4,75. Ces rapports n'autorisent pas à multiplier la
BOM ni à déclarer un partage industriel non établi.

Un décalage fabrication/conditionnement est possible : la semaine du 13 janvier,
Gien prélève 3 166 kg de 773474 et Avène 360 kg de 693055, sans prélèvement d'étuis
dans ces deux usines. Les photos confirment les mouvements matière. Aucun
registre de vrac transformé ou d'en-cours ne permet ici de mesurer le stock
intermédiaire correspondant. Pour Cicalfate, la convention de matières déjà
engagées dans les OF initiaux représente seulement 790 kg de 693055 : elle
explique une partie du démarrage, pas les plusieurs tonnes d'écart.

À l'amont, sur 35 semaines communes, les prélèvements de 021081 impliquent
`794 238 / 8,94 = 88 841 kg` théoriques de 773474 ; les bilans de stock donnent
83 200 kg d'entrées. Ce rapprochement indépendant conforte l'ordre de grandeur
des entrées reconstituées, sans certifier rendement ni dates d'achèvement. Les
185 600 kg de la colonne H annuelle restent incohérents avec les stocks.

**Les délais ne sont pas absents.** Les politiques du graphe incluent 33 jours
ouvrés de disponibilité à Gaillac pour 773474, puis 10 jours de trajet et
6 jours ouvrés à Gien ; pour 693055, 28 jours ouvrés à Gaillac, une hypothèse de
trajet de 7 jours et 7 jours ouvrés à Avène. Le trajet de 7 jours n'est pas une
mesure industrielle. Modifier ces délais peut déplacer des dates mais ne résout
pas, à lui seul, l'incohérence entre consommations et quantités produites.

La sécurité locale de 773474 reste de 20 jours ouvrés ; celle de 693055 est nulle
dans ce graphe. La consigne industrielle d'environ un an de stock sur toute la
chaîne Permixon n'est pas une contrainte explicitement contrôlée par le moteur.
L'horizon de projection de 52 semaines ne constitue pas une année de couverture.
Il ne faut pas ajouter une année de sécurité à chaque site.

**Prochain essai utile :** isoler un rejeu Gaillac avec les besoins aval sources
comme référence physique documentée, sans rejouer les fabrications de PF en
double et sans injecter les réceptions industrielles comme décisions simulées.
Comparer ensuite transferts, nouvelles fabrications et stocks aux mêmes semaines.
Ce diagnostic permettrait de départager les règles propres à Gaillac et le
raccordement aval BOM/Scan3. Les semaines manquantes et les besoins futurs connus
doivent rester distingués ; aucune réalisation future ne doit être utilisée
comme prévision. Les résultats du rejeu autorisé ensuite sont consignés ci-dessous.

### Résultat du rejeu isolé Gaillac — 8 octobre 2026

La [comparaison interactive](../resultats/gaillac_replay_20261008/comparaison.html)
affiche quatre stocks et leurs entrées/sorties, avec les sources et trois calculs :
la référence de chaîne complète, **A : consommations documentées**, et **B : mêmes
consommations, trous complétés depuis le dernier plan MRP admissible**.

Le moteur n'a pas changé. Les deux graphes ne gardent que sept nœuds et six
relations : Gaillac, les deux usines aval et les quatre fournisseurs de 021081.
Les processus PF authentiques restent des définitions inactives requises par le
moteur pour reconnaître les composants ; aucune fabrication de PF, consommation
BOM de ces PF, demande client ou expédition vers Muret n'est exécutée. Les stocks,
lots, délais, sécurités, matière virtuelle de 693055 et 25 engagements initiaux
de Gaillac sont conservés. Une prévision MRP ne devient pas une réception imposée.

La prévision aval utilise **100 % de I MRP**, avec la version déjà connue ; les
besoins propres PF sont nuls dans ce sous-modèle. L'exécution aval sert `−I−J`
des mouvements documentés, dans la limite du stock disponible. La ventilation
quotidienne uniforme est une convention du rejeu. Le 29 décembre 2024 documente
une semaine de 693055 : ses cinq jours en 2025 apportent 43 kg supplémentaires
au calcul, exclus des comparaisons sur semaines complètes. La disponibilité
initiale de 1 200 kg à Gaillac conserve l'hypothèse antérieure de reprise du
premier snapshot ; elle n'est pas une observation publiée le 1er janvier.

Sur 362 jours, A impose 66 667 kg de 773474 et 12 043 kg de 693055 ; B ajoute
9 589 kg et 334 kg estimés dans les trous. Les jours restés inconnus sont suivis
dans `prepared/manifest.json`, pas présentés comme des zéros industriels.
Les retraits aval demandés sont entièrement servis à fin d'horizon ; cela ne
prouve pas l'absence de retard pendant l'année.

**Entrées de stock impliquées par les sources et fabrication simulée, mêmes
semaines documentées, OF initiaux compris :**

| Gaillac | Semaines communes | Sources par bilan de stock | Référence | Rejeu A | Rejeu B |
|---|---:|---:|---:|---:|---:|
| 773474 | 41 | 92 800 kg | 25 600 kg | 67 200 kg | 73 600 kg |
| 693055 | 36 | 11 400 kg | 1 200 kg | 10 200 kg | 10 200 kg |

Les volumes complets de fabrication A/B sont respectivement 80 000/89 600 kg
de 773474 et 13 800/13 800 kg de 693055. Ils incluent des fabrications sur des
semaines où les mouvements sources manquent : ne pas les comparer directement
aux 92 800/11 400 kg documentés. La BOM de 021081 est effectivement consommée
pour les nouveaux lots de 773474 ; aucun Scan3 amont supplémentaire n'est injecté.

**Écart absolu moyen de stock sur 52 photos identiques, en kg :**

| Article / site | Référence | Rejeu A | Rejeu B |
|---|---:|---:|---:|
| 773474 / Gaillac | 12 000 | 5 969 | 6 154 |
| 773474 / Gien | 7 520 | 6 146 | 6 411 |
| 693055 / Gaillac | 497 | 944 | 921 |
| 693055 / Avène | 451 | 546 | 551 |

Le stock de 773474 à Gaillac s'améliore dans les deux conventions de trous.
Pour 693055, les volumes se rapprochent mais la trajectoire de stock se dégrade :
le rejeu ne constitue donc pas une nouvelle référence calibrée. L'intervention
change à la fois la consommation physique aval et son périmètre prévisionnel ;
elle ne sépare pas quantitativement les contributions de ces deux changements.

À fin d'horizon, A détient à Gaillac 2 400 kg de 693055, dont 1 800 indisponibles ;
B y détient 1 800 kg, tous indisponibles, plus 600 kg en transit vers Avène.
Dans A, les lots de 600 kg fabriqués les 4, 11 et 25 décembre deviennent
disponibles les 13 janvier, 20 janvier et 3 février 2026 selon les 28 jours
ouvrés retenus. Il s'agit d'une convention de disponibilité après production,
pas d'une durée de contrôle qualité industriel démontrée. Aucune exécution 2026
n'est simulée. Les hypothèses de date d'achèvement, de libération et le pilotage
des propositions futures doivent être examinés avant d'ajouter une sécurité.

Le recoupement de décembre précise ce point : les photos de 693055 à Gaillac
donnent **10 kg** les 8, 15, 22 et 29 décembre (`Stocks!E1452`, `E1534`, `E651`,
`E1474`, valeurs brutes en grammes). Les versions MRP des 14, 21 et 28 décembre ont toutes **J total = 0 kg**,
y compris leurs lignes futures (`Feuille1!J51025:J51057`, `J52075:J52106`,
`J53133:J53165`), tout en portant E = 28 jours. Elles ne corroborent donc pas les
1 800 kg de produits achevés mais indisponibles du rejeu. Cela cible l'interprétation
de ces 28 jours et le moment de l'entrée en stock ; cela ne prouve ni que le délai
réel est nul, ni l'absence d'en-cours hors stock d'inventaire. Le décalage de 10 kg
entre J et les photos est conservé.

Les deux simulations normales ont terminé avec un code retour nul et des
sources inchangées. Les vérifications indépendantes couvrent les calendriers,
quantités, stocks, lots, transferts et libérations. La qualification générique
de chaîne complète a été exécutée et **a échoué** sur une attente de demande
client (`KeyError: demand`) : ce sous-modèle n'a ni clients ni dépôt. Ce résultat
est conservé et n'est pas compté comme réussi ; l'audit ciblé ne certifie pas
le service client ni une calibration industrielle. Les contrôles JavaScript
en mémoire ne remplacent pas une revue visuelle dans un navigateur.

Les graphes, commandes, audits et empreintes se trouvent dans le
[dossier du rejeu](../artifacts/testing/gaillac_replay_20261008/).
Le [manifeste de synthèse](../artifacts/testing/gaillac_replay_20261008/manifest.json)
rassemble les deux exécutions, les contrôles ciblés et les limites conservées.
L'oracle indépendant sur Excel, graphes et CSV a passé 74 188 contrôles sans
erreur ; huit cas de calcul en mémoire ont également réussi. Le gate générique
reste refusé à cause de la qualification clients/DC en échec ; aucune revue
visuelle dans un navigateur n'est certifiée.

### Suite du diagnostic Gaillac : disponibilité, transferts et portée des délais

La passe complémentaire examine les mêmes fichiers et le même rejeu A, sans
nouvelle simulation ni modification du moteur. Les rapprochements sont dans
[analysis.json](../artifacts/testing/gaillac_replay_20261008/followup/analysis.json) ;
le script voisin ne lit que les sources et les résultats existants, puis écrit
ce rapport une seule fois. Deux analyses distinctes ont relu les sources et le
chemin de calcul dans le moteur.

**Le stock indisponible existe dans les sources ; sa chronologie est mal
reproduite.** Sur 52 versions MRP, le total J de 773474/Gaillac égale la photo
du lundi suivant dans 51 cas. Pour 693055, J vaut la photo moins 10 kg dans
51 cas. Les deux exceptions sont la version du 2 mars, rapprochée de la photo
du 3 mars. Le J futur est positif dans 51 versions pour 773474 et 30 pour
693055. Ces quantités sont déjà physiquement présentes, selon la convention
confirmée par l'utilisateur : ne pas les ajouter comme de nouvelles réceptions.

| Photo du lundi | Article | Physique source | J courant | J futur | Physique rejeu A | Indisponible rejeu A |
|---|---|---:|---:|---:|---:|---:|
| 6 janvier | 773474 | 9 600 | 6 400 | 3 200 | 9 600 | 0 |
| 6 janvier | 693055 | 1 800 | 590 | 1 200 | 1 800 | 1 200 |
| 3 mars | 773474 | 9 600 | 0 | 12 800 | 22 400 | 22 400 |
| 3 mars | 693055 | 1 810 | 0 | 1 200 | 2 400 | 2 400 |
| 2 juin | 773474 | 28 800 | 6 400 | 22 400 | 22 400 | 16 000 |
| 2 juin | 693055 | 1 810 | 1 200 | 600 | 1 200 | 600 |
| 29 décembre | 773474 | 35 200 | 16 000 | 19 200 | 25 600 | 3 200 |
| 29 décembre | 693055 | 10 | 0 | 0 | 2 400 | 1 800 |

Valeurs en kg ; clôture simulée du dimanche, sans décaler la photo source.
Les écarts de 10 kg et les exceptions du 3 mars restent visibles.
Supprimer simplement l'indisponible de la courbe ferait passer l'écart moyen
de 773474 de 5 969 à 12 677 kg, et celui de 693055 de 944 à 1 068 kg : ce n'est
ni une correction valide du stock total, ni une amélioration sur l'année.

**Une omission initiale est identifiée.** Le premier plan affecte 3 200 kg de
773474 à une disponibilité future (`MRP!J970`, version du 5 janvier, semaine
du 26 janvier). La référence ne reprend aucune indisponibilité initiale pour
773474, alors qu'elle reprend les 1 200 kg de 693055. Le rejeu hérite de cette
omission ; il ne l'a pas créée. La lecture doit devenir uniforme pour toutes
les paires article/site. Utiliser un plan du 5 janvier pour initialiser le
1er janvier reste une rétroprojection explicite, pas une information connue
le 1er janvier ; un essai à partir du premier plan connu évite cette ambiguïté.

**Le premier transfert de 773474 diverge avant l'accumulation de mars.** Les
6 400 kg attendus à Gien sont déjà prévus le 5 janvier (`MRP!H942`, semaine
du 12 janvier). Les mouvements documentent ensuite 6 400 kg la semaine du
13 janvier. Le 15 janvier, le modèle dispose de 12 210 kg utilisables à Gien
et n'y a aucun autre approvisionnement engagé. Pour le 6 février, il calcule
6 143 kg de besoins et 6 442 kg de protection, soit environ 375 kg manquants.
La protection du 7 février porte le manque cumulé à 825 kg ; un lot de
3 200 kg suffit selon cette règle. Il n'en expédie donc pas deux.
Ce calcul est traçable dans `mrp_dated_plan_daily.csv:412`,
`mrp_dated_plan_weekly.csv:2556–2557` et `mrp_orders_daily.csv:28` du rejeu A.
L'extrait des en-cours ne contient **aucun** ordre 773474/Gien ou
693055/Avène : une commande ferme perdue n'est pas démontrée. H proche peut
représenter un engagement antérieur ou une proposition ; tester son maintien
doit rester une hypothèse de carnet initial, distincte d'une règle de couverture.

**Les paramètres de délai ne désignent pas tous le même événement.** E du
MRP s'intitule « Temps de réception en jours », sans date de début/fin de
fabrication. Dans le moteur, les nouveaux lots fixes sont fabriqués et comptés
physiques immédiatement, puis indisponibles 28/33 jours ouvrés à Gaillac.
`tau_process = 3` intervient dans la planification, pas comme une durée physique
de fabrication. Il n'y a pas de double ajout des 28/33 jours dans le parcours
physique vérifié, mais leur position après fabrication est une interprétation.

Exemple vérifié : le lot 773474 de 3 200 kg créé le 16 janvier devient disponible
le 4 mars, part le 5 mars, arrive à Gien le 15 mars et y devient utilisable le
24 mars. Le lot 693055 de 600 kg créé le 23 janvier devient disponible le
4 mars, part le 5 mars, arrive le 12 mars et devient utilisable le 21 mars.
La source sait dater la disponibilité de stocks présents au-delà d'une simple
durée fixe : version du 6 juillet, `J27048` reporte 3 200 kg de 773474 au
5 octobre (+91 jours calendaires). Cela ne mesure pas une durée de fabrication.

Les 10 jours de 773474 sont bien renseignés dans `268967.xlsx/FIA!F9`, sous
« Délai prévisionnel de livraison en jours ». Les utiliser comme transport
physique est une interprétation, non une durée mesurée. Pour 693055,
`268091.xlsx/FIA!F22` donne 70 jours ; le modèle remplace opérationnellement
ce paramètre par 7 jours hypothétiques de transport, et décompose séparément
la disponibilité à Gaillac et la réception à Avène. Cette décomposition n'a
pas encore été rapprochée des 70 jours source. Les 18 semaines de transferts
positifs de 773474 et les 19 de 693055 présentent des totaux hebdomadaires
exactement miroirs entre départ et réception ; ils ne permettent ni de compter
les expéditions physiques individuelles, ni de mesurer le trajet.
Enfin, le transfert industriel de 1 190 kg de 693055 montre que lot fabriqué
de 600 kg et quantité transférée ne sont pas nécessairement le même multiple.

**Ordre des prochains essais, en gardant la référence :**

1. Uniformiser la reprise du stock disponible et des disponibilités futures,
   sans changer le stock physique total, à une date de connaissance explicite.
2. Expliquer le premier transfert de 6 400 kg : comparer séparément maintien
   du plan initial proche et règle de couverture/regroupement, sans déclarer
   toutes les entrées H futures fermes ni imposer les réceptions réalisées.
3. Tester une représentation des jalons de fabrication/disponibilité seulement
   après avoir précisé ce que mesure chaque délai ; ne pas supprimer les
   28/33 jours, les ajouter aux 70 jours, ou convertir tau_process arbitrairement.
4. Revenir ensuite à la chaîne complète : résoudre la discordance des besoins
   BOM/Scan3 avant de remplacer les fabrications autonomes par des consommations
   observées. Le rejeu aval documenté reste un diagnostic, pas une prévision.

### Essais séquentiels Gaillac des 8–9 octobre : résultats mesurés

Les essais restent séparés de la référence acceptée demande/client. Ils couvrent
le 1er janvier au 28 décembre 2025 ; aucune simulation de cinq ans n'est lancée.
Les graphes, commandes, résultats et contrôles indépendants sont conservés dans
`artifacts/testing/gaillac_sequence_20261008`. Les classeurs et le moteur actif
restent inchangés ; les adaptations expérimentales s'appliquent en mémoire dans
des lanceurs locaux, sur des dossiers de résultats distincts.

**E1 — disponibilité initiale uniforme.** Les 3 200 kg de 773474 décrits par
`MRP!J970` restent physiquement présents à Gaillac mais indisponibles jusqu'au
repère du 26 janvier. Cette initialisation rétroprojette explicitement le plan
du 5 janvier ; elle ne prétend pas connaître ce plan le 1er janvier. Le contrôle
retrouve exactement les mêmes fabrications, transferts et stocks physiques
que dans le rejeu A. Les 6 400 kg encore disponibles suffisent au premier
départ, et la libération précède le suivant. L'omission était réelle, mais elle
n'explique pas les écarts de volumes ou de stocks dans cet essai.

**E2 — maintenir l'approvisionnement initial proche.** Les 6 400 kg prévus
pour Gien dans `MRP!H942` deviennent une promesse le 5 janvier, sans être ajoutés
au stock. Ils sont réellement prélevés à Gaillac le 8 janvier, reçus à Gien le
18 et disponibles le 27, avec les délais inchangés. Cette promesse remplace
les deux départs de 3 200 kg des 15 et 29 janvier ; elle ne s'y ajoute pas.
Son caractère ferme est une hypothèse, pas un statut présent dans le classeur.

Sur 52 photos communes, l'écart moyen à Gien passe de **6 146 à 5 904 kg**
(−3,9 %). À Gaillac, la courbe diffère sur 21 jours mais l'écart annuel reste
**5 969 kg**. Les dates et quantités fabriquées restent exactement identiques
à E1. Les deux sites de 693055 sont inchangés. Le maintien initial améliore
donc le calendrier de début d'année, sans résoudre le déficit annuel.

**E3 — diagnostic de classement en en-cours, sans nouvelle simulation.**
Seules les nouvelles fabrications de Gaillac sont retirées du stock article
jusqu'à leur disponibilité d'origine et placées dans un en-cours distinct.
Les OF et stocks initiaux restent inchangés. Chaque jour, stock article plus
en-cours égale le stock physique E2 ; les départs et l'aval ne changent pas.
Cette hypothèse éloigne les photos sources : l'écart passe de **5 969 à
12 554 kg** pour 773474/Gaillac, et de **944 à 998 kg** pour 693055/Gaillac.
Elle n'est pas retenue comme correction du stock total. Aucun délai de contrôle
n'est supprimé et aucune durée physique n'est attribuée à `tau_process`.

**Contrôle complet E4C, affiché F1.** Le moteur rejoue la chaîne complète avec
la seule initialisation E1. Les quatre stocks suivis, les fabrications de Gaillac,
ainsi que la demande, le service, la production des PF et le stock final de Muret
retrouvent la référence. La qualification CSV indépendante est réussie dans
`toolbox/qualify-347000da119e404386fc5c6eeba5f7a4/manifest.json`, sous le dossier
de preuves de cette série. Elle vérifie les bilans programmés, pas la calibration.

**Règle expérimentale E4, aux seules entrées 773474/Gien et 693055/Avène.**
Sur une semaine future documentée par un plan déjà connu :

```text
complément prévu = max(0, besoin MRP industriel − besoin propre simulé)
besoin prévu = besoin propre simulé + complément prévu
             = max(besoin propre simulé, besoin MRP industriel)
```

Le complément remplace les autres prévisions de cette semaine. Les réserves
restent distinctes et conservées, ainsi que les besoins hors semaines
documentées. La protection est recalculée avec les mêmes jours de sécurité.
Cela modifie un signal de planification, pas les consommations exécutées :
aucun prélèvement Scan3 n'est injecté, aucun coefficient BOM n'est multiplié.
Les règles des autres articles sont déléguées sans modification au moteur.
Le journal `E4_reconciliation_windows.csv` distingue la politique réellement
appliquée de l'étiquette globale historique des exports natifs.

**Résultat E4 : amélioration de 773474, dégradation de 693055.**
Écart absolu moyen de stock, aux mêmes 52 photos, arrondi au kg :

| Article / site | Contrôle complet E4C | E4 |
|---|---:|---:|
| 773474 — Gaillac | 12 000 | 3 877 |
| 773474 — Gien | 7 520 | 5 733 |
| 693055 — Gaillac | 497 | 784 |
| 693055 — Avène | 451 | 1 021 |

Les entrées issues des fabrications de Gaillac sur toute la période, OF
initiaux compris, passent de 28 800 à 57 600 kg pour 773474 et de 2 400 à
4 800 kg pour 693055. Les nouvelles fabrications seules passent respectivement
de 25 600 à 54 400 kg et de 1 800 à 4 200 kg ; les OF initiaux restent identiques.

**Une courbe de stock plus proche ne suffit pas.** Sur les 41 semaines
documentées communes de 773474/Gaillac :

```text
Sources : 92 800 kg d'entrées reconstituées − 67 200 kg de sorties = +25 600 kg
E4      : 48 000 kg d'entrées simulées       − 19 200 kg de sorties = +28 800 kg
```

Les variations cumulées deviennent proches parce que les entrées et les sorties
restent toutes deux trop faibles. Ces sommes portent sur des semaines
discontinues, pas sur la différence entre les seuls stocks initial et final.
Les prélèvements propres exécutés à Gien et Avène restent exactement ceux du
contrôle : 13 530 kg de 773474 et 941 kg de 693055 sur tout le calcul. Les
prévisions plus élevées ne réparent donc pas le rapprochement physique BOM/Scan3.

**Un lot de Permixon est néanmoins disponible dix jours plus tôt.** Pour
`PORD-M-1430-item:268967-000003`, les 107 800 UN sont achevées à J179 dans
E4 contre J187 dans le contrôle, libérées à J198 contre J208, puis reçues à
Muret à J200 contre J210. Le candidat supprime une attente de 773474 ; ce n'est
pas une augmentation de la quantité annuelle fabriquée. Au 21 juillet,
le stock source de Muret vaut 541 256 UN (`Stocks!E9`) : le contrôle affiche
401 907 UN et E4 509 707 UN. Au 28 juillet (`Stocks!E25`), la source vaut
498 329 UN, contre 327 228 et 435 028 UN. L'écart moyen annuel de Muret/268967
passe de 177 680 à 173 533 UN. Les quantités servies aux clients sont identiques
chaque jour ; les stocks finaux sont identiques. Les totaux de PF produits sont
inchangés, mais leur calendrier ne l'est donc pas entièrement.

**Décision :** conserver E4 comme candidat documenté, sans adoption globale.
Le prochain point à résoudre est la cohérence des consommations matière avec
les productions et le conditionnement, avant d'augmenter encore les couvertures.
La [comparaison interactive des quatre étapes](../resultats/gaillac_sequence_20261008/comparaison.html)
conserve les gains et les dégradations. Le
[manifeste de synthèse](../artifacts/testing/gaillac_sequence_20261008/manifest.json)
rassemble les commandes, empreintes, qualifications CSV et contre-vérifications.
La vérification JavaScript utilise un DOM minimal en mémoire ; aucune revue
visuelle dans un navigateur n'est certifiée.

**Vérification complémentaire des unités.** Dans les deux classeurs BOM, les
bases restent explicitement 1 000 UN (`268091/BOM!B2:B16`,
`268967/BOM!B2:B9`) et la copie dans `demand_PF/BOM` concorde. La somme des
matières représente 20,4218 g par UN pour 268091 et 27,153894 g pour 268967,
hors emballages. Les deux BOM, `demand_PF.xlsx` et
`Flow_Data_Customer_Demand.xlsx` ne documentent ni contenance commerciale ni
conversion boîte/plaquette permettant d'expliquer le facteur matières/emballages.
Ces sommes constituent des indices à confronter à une fiche article ; elles
n'autorisent aucun multiplicateur appliqué à la BOM.

### Consommations trop faibles : BOM, production et en-cours — 9 octobre 2026

**Le calcul applique les deux coefficients BOM fournis. Le rapprochement avec
les consommations industrielles reste incohérent.** Audit du contrôle E4C,
du 1er janvier au 28 décembre 2025, sans nouvelle simulation ni modification
du moteur ou des données. Les consommations propres totales sont identiques
dans E4 ; le calendrier de certaines fabrications diffère.

```text
773474 pour 268967 : 9 654,718 g / 1 000 PF = 0,009654718 kg/PF
693055 pour 268091 :       406 g / 1 000 PF = 0,000406 kg/PF

Gien  : 1 401 400 PF nouvellement exécutés × 0,009654718 = 13 530,122 kg
Avène : 2 318 400 PF nouvellement exécutés × 0,000406    =    941,270 kg
```

Sources : `268967.xlsx/BOM!B4:F4`, `268091.xlsx/BOM!B12:F12`.
Les registres journaliers et les événements de prélèvement concordent avec ces
formules. Les conversions G/KG et la division par la base de 1 000 UN sont
correctes pour ces deux composants ; aucun facteur de perte supplémentaire
n'est appliqué à cette transformation PF.

**Comparer des volumes fabriqués différents n'explique qu'une petite partie
du décalage.** Sur les mêmes semaines présentes dans les lignes matière ET
étui, quantités arrondies au kg :

| Même périmètre de semaines | 773474 / Gien, 33 semaines | 693055 / Avène, 45 semaines |
|---|---:|---:|
| Matière sortie dans `Sorties_article_scan3` | 47 794 kg | 9 540 kg |
| Matière prélevée dans la simulation pour nos PF | 8 326 kg | 848 kg |
| Étuis consommés dans les sources | 1 109 680 UN | 4 942 300 UN |
| Matière théorique selon la BOM pour ces étuis sources | 10 714 kg | 2 007 kg |
| Rapport matière source / matière théorique pour ces étuis | 4,46 | 4,75 |

Un étui par PF est la convention des BOM fournies. Les étuis constituent ici
un équivalent de conditionnement, pas une preuve de fabrication simultanée du
vrac. Les semaines absentes sont exclues, jamais assimilées à des zéros.
Les sorties des autres usages restent distinctes : la colonne Scan3 est bien
celle déclarée par l'utilisateur comme dédiée aux deux produits étudiés.

Décomposition arithmétique du décalage matière sur ces mêmes semaines :

| Terme de l'écart source moins simulation, kg arrondis | Gien | Avène |
|---|---:|---:|
| Écart interne aux sources : matière sortie moins BOM des étuis sortis | 37 080 | 7 533 |
| Différence de volumes d'étuis source/simulation, convertie avec la BOM | 2 387 | 369 |
| BOM des étuis simulés moins matière prélevée : ouverture et arrondis | 0 | 790 |

Ces termes s'additionnent avant arrondi. Cette identité localise l'écart ;
elle ne prouve pas sa cause industrielle. Le résultat est renforcé par les
42 semaines communes aux **12 matières de Cicalfate et aux deux emballages** :
chaque matière donne entre 22,310 et 22,318 millions d'équivalents PF, contre
4 901 500 étuis et 4 919 050 tubes. Les rapports matière/étui se situent tous
entre 4,55166 et 4,55321. Ce n'est donc pas une anomalie isolée de 693055.
Les trois matières de Permixon présentent aussi un écart groupé sur leurs
30 semaines communes : rapports 4,83 à 4,95, contre 1,03 pour l'emballage 708073.

**L'ouverture d'Avène suppose des matières déjà consommées.** Les 20 OF de
`Extract_En_cours.xlsx!Sheet1`, lignes 72 à 91, représentent 1 945 715 PF,
soit 789,960 kg de 693055 à la BOM. Le mode `wip_non_pack` les classe en
matière déjà incorporée avant J0 : aucun prélèvement 2025 de cette matière,
mais les emballages sont prélevés au conditionnement. Le fichier donne une
date de livraison G et une date d'entrée I ; **aucune de ces deux dates ne
prouve une sortie matière avant le 1er janvier**. Cette exclusion est donc
une hypothèse du scénario. L'annuler pourrait déplacer au maximum ces 790 kg
vers 2025, à ordres inchangés, si aucune matière n'avait été consommée avant.
Cela reste très insuffisant pour combler l'écart et pourrait doubler un
prélèvement déjà réalisé ; aucune correction automatique n'est appliquée.

Les 288 000 PF d'Avène encore retenus qualité en fin de calcul ont déjà consommé
leurs 116,928 kg de 693055. Ils n'expliquent pas une consommation manquante.
La colonne quotidienne `produced_qty` suit ici les quantités rendues disponibles :
ne pas la confondre avec `executed_qty` ou les créations physiques des lots.

**Conclusion de cette passe :** vérifier le lien industriel entre recette du
vrac, quantité de vrac par PF conditionné et périmètre exact de l'extraction
Scan3 est prioritaire. Les hypothèses restent une base/version de BOM différente,
un périmètre d'extraction plus large ou des en-cours entre vrac et conditionnement.
Les sources actuelles ne permettent pas de choisir entre elles. Ne pas
reclasser arbitrairement l'excédent en « partagé », ni multiplier les BOM par
cinq pour rapprocher les stocks. Modifier encore uniquement la sécurité ou
les dates du MRP ne répare pas cette incohérence physique.

Preuve reproductible : [diagnostic chiffré et empreintes](../artifacts/testing/gaillac_sequence_20261008/diagnostics/consumption_20261009.json),
calculé depuis les Excel et CSV, avec 3 527 assertions arithmétiques et de
cohérence réussies. Le [script associé](../artifacts/testing/gaillac_sequence_20261008/diagnostics/consumption_20261009.py)
lit les sources et écrit uniquement un nouveau rapport ; il n'altère aucun
fichier testé. Cette preuve ne certifie pas le périmètre industriel de Scan3.
Une [contre-vérification indépendante](../artifacts/testing/gaillac_sequence_20261008/diagnostics/consumption_20261009_validation.json)
reprend directement les Excel et CSV, sans importer le script de diagnostic :
94 contrôles ciblés réussis, neuf empreintes stables. Elle confirme aussi le
rapprochement des 12 matières avec les deux emballages sur 42 semaines.

### Correction de périmètre Scan3 — 16 octobre 2026

L'industriel confirme désormais le sens métier suivant pour
`Flow_Data_Inventory_movements.xlsx` :

- pour les matières premières et les emballages, `J = Sorties_article_scan3`
  correspond aux consommations de **268091 ou 268967**, tandis que
  `I = Sorties` correspond aux consommations des **autres références** ;
- pour les produits finis, `I = Sorties` est présenté comme le flux vers les
  clients, mais ses valeurs ferment numériquement le bilan comme un **mouvement
  net de stock**. Elles ne constituent donc pas une liste de livraisons brutes.
  Exemple 268091 : du 6 au 13 janvier, le stock augmente de 177 592 UN et
  `I745 + G745 = 177 610 - 18 = 177 592 UN`. Prendre `abs(I)` inventerait ici
  une livraison pendant une hausse de stock.

La [contre-vérification directe du 16 octobre](../artifacts/testing/pf_movements_oracle_20261016/rapport.md)
confirme cette distinction et reconstruit séparément le rapport 4,552493.

Le [rapprochement approfondi du 19 octobre](../artifacts/testing/sorties_factory_reconciliation_20261019/rapport.md)
montre comment utiliser ce vecteur sans le confondre avec les livraisons brutes.
Sur les 51 semaines bornées par deux photos de stock, la relation candidate est :

```text
variation du stock = Divers G + Sorties I
I = apports PF à Muret − mouvements clients signés
apports PF implicites = I + demande_PF signée
```

Le cumul annuel est très proche des lots standards : **4 146 191 UN** pour
268091, contre `144 × 28 800 = 4 147 200` (écart −1 009 UN, −0,024 %), et
**972 096 UN** pour 268967, contre `9 × 107 800 = 970 200` (écart +1 896 UN,
+0,195 %). Pour 268967, `I = −demande_PF signée` exactement pendant 24
semaines, y compris trois corrections de demande négatives. Ces valeurs
négatives doivent rester signées dans le rapprochement physique ; leur mise à
zéro reste la convention distincte de la demande prospective simulée.

Cette concordance est annuelle. `Divers G` porte séparément les corrections et
reclassements enregistrés dans la source ; ils ne doivent pas être réattribués
au résidu `I + demande_PF signée`. Les résidus hebdomadaires ne donnent pas des
réceptions mesurées et ne suivent généralement pas les multiples de lots. Ils
montrent surtout que la demande signée et I ne sont pas deux journaux parfaitement
synchronisés ou de périmètre hebdomadaire strictement identique. Aucune fenêtre
plus courte n'est démontrée comme règle de regroupement. Le moteur doit donc
comparer `réceptions Muret − mouvements clients signés` à I et ses corrections
explicites à G, tandis que la demande, le service estimé par le CA et les
prévisions restent des séries commerciales séparées.

**Décision nominale du 19 octobre 2026 :** la comparaison principale de la
réponse à la demande n'utilise aucune quantité estimée depuis le CA. Elle
affiche la demande positive de
`Flow_Data_Customer_Demand.xlsx / Historique / Actual Demand`, les sorties
réelles Muret vers clients selon l'interprétation métier fournie de
`abs(Sorties I)` dans `Flow_Data_Inventory_movements.xlsx`, et les livraisons
issues du registre simulé alimenté par cette même demande Flow. `demand_PF`
reste affiché comme **ancienne référence secondaire**. La valeur I signée et
Divers G restent visibles séparément dans le rapprochement physique. Sorties I
est un mouvement hebdomadaire agrégé et non un journal d'expéditions unitaires ;
ses cumuls ne prouvent pas un appariement commande–livraison semaine par semaine.

Cette confirmation ne supprime pas le rapport arithmétique 4,552493 ci-dessous.
Elle invalide en revanche son ancienne interprétation comme consommation
« d'autres formats » ou « d'autres références ». Ces autres consommations sont
déjà enregistrées séparément en colonne I. Le résiduel
`max(0, Scan3 J - consommation BOM simulée)` ne doit donc ni être ajouté à I,
ni être publié comme `external_component_consume`, ni être prolongé après 2025.
Il reste un **écart de raccordement de nos références** entre prélèvement
matière, OF/en-cours, nomenclature et conditionnement.

Le « facteur cinq » parfois cité venait d'un calcul moins rigoureux sur toutes
les lignes disponibles : 497 943,443 kg de matières contre 102 450,044 kg de
BOM pour 5 016 700 étuis, soit **4,860354**. Les articles n'ayant pas tous la
même couverture hebdomadaire, ce chiffre mélange des fenêtres différentes et
ne doit plus être utilisé. Le chiffre comparable reste **4,552493 sur les
mêmes 42 semaines**.

### Origine du rapport 4,55 : recette et volume de conditionnement — 9 octobre 2026

**Décision utilisateur : conserver la BOM et expliquer le rapport, sans en faire
un coefficient correctif.** Trois lectures indépendantes des classeurs ont
séparé la composition des matières, leur calendrier et le volume conditionné.

**Définition et sources du rapport :** le numérateur est `−somme(J)` pour les
douze matières dans `Flow_Data_Inventory_movements.xlsx/Feuille1`, où J est
`Sorties_article_scan3`. Le dénominateur est la quantité d'étuis de cette même
colonne, multipliée par les douze coefficients de `268091.xlsx/BOM`.
Toutes ces quantités portent sur les mêmes 42 semaines présentes, discontinues,
du 6 janvier au 15 décembre 2025. Aucun résultat simulé n'entre dans ce rapport.
Dans le fichier de mouvements, I est `Sorties`, un mouvement signé distinct.
Dans `Flow_Data_MRP_results.xlsx`, I est au contraire `Sortie`, un besoin prévu
positif. Ces deux colonnes I ne sont pas interchangeables.

La BOM de `268091.xlsx/BOM!B2:F16` et sa copie dans `demand_PF.xlsx` portent les
mêmes 15 coefficients, tous pour **1 000 UN**. La copie antérieure `Data_poc`
emploie 693710 à la place de 007923, avec la même quantité : cette différence
d'identifiant ne produit aucun multiplicateur. Les emballages se nomment
explicitement **Cicalfate 40 ml** (`Inventory_movements!B886/B931`). La somme
**20,4218 kg / 1 000 PF** désigne les douze matières répertoriées ; ce n'est pas
une mesure du poids net complet du PF, ni une conversion documentée g/ml.

Sur les **45 semaines communes aux douze matières**, 40 présentent des sorties
et cinq sont toutes nulles. Chaque matière, ramenée en équivalents PF par sa
propre BOM, s'écarte de l'équivalent obtenu avec 693055 de **−0,139 % à
+0,167 %**. La composition des sorties suit donc très étroitement la recette.
693055 est toujours sorti par multiples de **60 kg** ; les incréments déduits
pour les autres matières suivent le même nombre entier, avec de petits écarts
numériques dont l'origine n'est pas identifiée. Leur somme
théorique vaut **3 018 kg des matières répertoriées**, sans démontrer le poids
d'un lot de vrac ni une taille de cuve.

Sur les **42 semaines communes aux douze matières et aux deux emballages** :

```text
Matières enregistrées Scan3                      = 455 692,961 kg
Matières BOM pour 4 901 500 étuis                 = 100 097,453 kg
Rapport des deux totaux                          = 4,552493
Différence, exprimée en matières répertoriées     = 355 595,508 kg
```

Calculé séparément pour chacune des douze matières, le rapport cumulé à la BOM
des étuis va de **4,55166 à 4,55321** : il est donc presque identique entre
matières sur cette sélection. Cette stabilité entre composants ne signifie
pas une stabilité dans le temps.

**Ce rapport n'est pas constant par semaine.** Parmi les 30 semaines de cette
sélection avec étuis positifs, le rapport équivalent PF de 693055 / étuis varie
de **0 à 21,026**. Par exemple, le 17 février, 60 kg et 285 600 étuis donnent
0,517 (`Inventory_movements!J1071/J937`) ; le 30 juin, 420 kg et 49 200 étuis
donnent 21,026 (`J1090/J955`). Il existe aussi des semaines avec matières sans
étuis et des semaines avec étuis sans matières. Fabrication de vrac et
conditionnement ne doivent donc pas être assimilés à un événement simultané.
Un décalage fixe testé de −6 à +6 semaines entre 693055 et les étuis conserve
un rapport cumulé de 4,1 à 5,3 sur les paires documentées ; il ne ferme pas
l'écart. Les fenêtres comparées diffèrent selon le décalage : ce contrôle
n'exclut pas tout scénario d'en-cours, mais exclut cette explication simple.

L'écart existe également **à l'intérieur du MRP source**, sans intervention du
simulateur. Dans le plan du 5 janvier, sur 26 horizons 2025 communs à trois
matières (001757, 016332, 049371) et aux deux emballages, chaque matière donne
**13 300 493 équivalents PF**, contre **2 791 601 étuis** et **3 862 276 tubes**.
Les versions de plan sont examinées séparément, jamais additionnées.
Exemple vérifiable dans ce même plan, horizon du 5 janvier :
`Flow_Data_MRP_results/Feuille1!I2/I241/I444` donnent respectivement
1 200 000 G de 001757, 360 000 G de 016332 et 1 110 000 G de 049371, soit
**738 916 équivalents PF** pour chacune des trois matières. Les étuis et tubes
`I705/I664` valent chacun **142 454 UN**. Une avance du vrac peut expliquer une
différence hebdomadaire ; elle ne suffit pas à elle seule à fermer le cumul.

Dans le plan figé du **29 juin**, les 18 horizons 2025 communs aux mêmes trois
matières et aux deux emballages donnent **11 231 549 équivalents PF** pour
**2 137 659 étuis** et **2 821 204 tubes**. Les rapports matières/étuis des deux
plans sont donc **4,76447** et **5,25414**, pas une constante 4,55. Ils décrivent
deux plans distincts et deux ensembles d'horizons, pas des quantités exécutées.
Le MRP ne ventile pas ces besoins entre Scan3 et autres usages.

Vérification de provenance en mémoire, sans extraction sur disque : le fichier
MRP actuel est identique octet pour octet à celui du commit `9f5e8535e` du
30 septembre 2026. Le fichier de mouvements actuel est identique à celui du
commit `8ac4831d4` du 8 octobre 2026, qui possède déjà I et J. Ce sont des dates
de conservation Git, pas des dates d'événements industriels. La discordance
des plans est donc retrouvée dans une version conservée avant le nouvel
export de mouvements ; le rapport exact 4,552493 est calculé avec ce dernier.

Le contrôle E4C existant a été relu pour les **12 matières × 362 jours**, soit
**4 344 rapprochements** entre prélèvement et `production exécutée × BOM`.
L'écart journalier maximal est de **0,0000004 kg**, compatible avec l'arrondi
des CSV ; aucun facteur 4,55 n'est appliqué aux prélèvements de cette référence.
Fichiers : `gaillac_sequence_20261008/run_E4C_362/data/`
`production_input_consumption_daily.csv` et `production_output_products_daily.csv`.

Le surplus arithmétique des 42 semaines représente environ **17,4 millions
d'équivalents PF** à la BOM. L'expliquer entièrement par du vrac en attente
demanderait un registre d'en-cours de cet ordre de grandeur, absent des sources.
Les 20 OF initiaux connus représentent 1 945 715 PF, pas un stock de vrac final.
La cause industrielle reste à établir au raccordement **sortie matière → OF
vrac → OF de conditionnement → article fini** : décalage/en-cours, affectation
ou conversion non documentée. L'affirmation utilisateur « Scan3 concerne les
deux PF » reste conservée ; aucun excédent n'est réaffecté à d'autres produits.
Ni une base matières de 220 PF, ni une multiplication de la BOM par 4,55, ni
une modification de sécurité MRP n'est justifiée par cet audit.

Contrôles en lecture seule des données et des résultats existants ; aucune
nouvelle simulation, modification du moteur, des classeurs ou des cartes.
Les lignes/cellules citées et le diagnostic des 42 semaines ci-dessus permettent
de distinguer ces calculs d'une validation industrielle de leur périmètre.

### Recoupement Scan3, matières partagées, stocks et MRP — 9 octobre 2026

Les **455 692,961 kg** correspondent exactement à la somme des sorties
enregistrées dans `Sorties_article_scan3` pour les 12 matières de Cicalfate,
sur les 42 semaines communes utilisées ci-dessus. L'industriel confirme leur
attribution au périmètre de nos références. Les exports ne contiennent toutefois
ni identifiant d'OF ni étape de prélèvement permettant de raccorder chaque ligne
à la production et au conditionnement correspondants.

**Les consommations des autres références sont visibles séparément.**
À Avène, sur les mêmes 42 semaines, en kg arrondis :

| Matière | Sorties Scan3 | Autres sorties (colonne I) | Total des deux | Part Scan3 | Besoins MRP prévus |
|---|---:|---:|---:|---:|---:|
| 002612 | 45 298 | 505 869 | 551 167 | 8,22 % | 858 355 |
| 007923 | 72 465 | 190 073 | 262 537 | 27,60 % | 405 953 |
| 693055 | 9 060 | 2 030 | 11 090 | 81,70 % | 19 600 |

Pour ces trois matières seulement, I et J mouvements restent négatifs ou nuls
sur toute la sélection : les parts de sorties sont donc interprétables.
Les autres sorties ne sont pas déjà incluses dans Scan3. Elles ne sont pas
ventilées par autre produit fini dans le fichier.

**Ne garder que la colonne I ne résout pas le rapprochement.** Les quantités
ci-dessous sont en kg, arrondies, sur les mêmes 42 semaines. Les deux colonnes
de mouvements conservent ici leurs signes source : négatif = diminution du
stock, positif = augmentation. La colonne théorique correspond uniquement à
la BOM des **4 901 500 étuis**, pas aux besoins de tous les produits du site.

| Matière | Théorie BOM des étuis | Mouvements I : Sorties signé | Mouvements J : Scan3 signé | MRP I : besoin prévu |
|---|---:|---:|---:|---:|
| 001757 | 7 960 | −480 | −36 240 | 67 920 |
| 001848 | 5 970 | −672 | −27 177 | 51 422 |
| 001893 | 37 810 | +1 575 | −172 136 | 513 854 |
| 002612 | 9 950 | −505 869 | −45 298 | 858 355 |
| 007923 | 15 920 | −190 073 | −72 465 | 405 953 |
| 016332 | 2 388 | +12 529 | −10 872 | 20 376 |
| 029313 | 199 | +1 428 | −906 | 2 810 |
| 039668 | 199 | +1 042 | −906 | 2 404 |
| 049371 | 7 363 | −469 | −33 522 | 62 841 |
| 055703 | 398 | −868 | −1 812 | 4 472 |
| 099439 | 9 950 | +52 539 | −45 299 | 93 540 |
| 693055 | 1 990 | −2 030 | −9 060 | 19 600 |
| **Total 12 matières** | **100 097** | **−631 348** | **−455 693** | **2 103 548** |

Pour 693055 seulement, le débit net I de **2 030 kg** est proche des
**1 990,009 kg** théoriques (rapport 1,02010). Cela ne se généralise pas :
001757 donne 0,06030 fois la théorie, 002612 50,84091 fois, 007923 11,93918
fois ; I de 016332 est positif. Ce dernier est un apport net au stock dans
cette comptabilité, pas une consommation négative. Les types d'opérations
industrielles correspondants restent inconnus.

Pour les douze matières, `−somme(I+J)` vaut **1 087 041,108 kg** contre
**2 103 548,459 kg** de besoins MRP sur les mêmes semaines. Ce rapprochement
prévu/enregistré au niveau article-site ne doit pas être présenté comme le
rapport matières/conditionnement 4,55, ni comme un taux de service client.

MRP : une seule ligne par semaine cible et par matière, issue du plan daté du
dimanche précédant le lundi retenu, avec le même repère dimanche en semaine
cible. Aucune addition des versions successives d'un même horizon. Ce sont
des **besoins prévus pour l'article/site**, pas des consommations réalisées.
Leur total dépasse les sorties réalisées de 56 %, 55 % et 77 % respectivement.
L'examen du plan publié une semaine plus tôt donne encore des valeurs
différentes ; il ne faut pas considérer ces différences comme des sorties
physiques manquantes. Le rattachement exact des buckets MRP au calendrier
des mouvements reste une convention de comparaison explicite.

**Produits finis : pas de rapport 4,55 mesuré en sortie d'usine.** Le fichier
de mouvements et les photos ne contiennent pas de couple PF 268091/Avène ni
268967/Gien. À Muret, pour les deux PF, J Scan3 est nul sur les 42 semaines.
I comporte des valeurs positives et négatives : somme **+782 529 UN** pour
Cicalfate et **−523 363 UN** pour Permixon. Ce ne sont pas des livraisons
clients brutes. Exemple Cicalfate : `I745 = +177 610 UN`, `G745 = −18`,
et `Stocks!E11/E62` passe de 423 434 à 601 026 UN. La colonne I contribue
ici à une hausse de stock. Les reconstitutions de sorties usine de la carte
restent des calculs conditionnels, pas une mesure directe de production.

En revanche, les emballages de Cicalfate se corroborent sur les 42 semaines :
**4 901 500 étuis**, **4 919 050 tubes** (écart +0,36 %) et **54 800 caisses**
dans J ; la BOM des étuis correspond à 53 916,5 caisses avec 11/1 000.
Cette proximité ne prouve pas la quantité finie exacte, mais ne présente pas
le même décalage d'un facteur 4,55 que les matières.

**Les stocks confirment le bilan des mouvements.** Pour chacune des 12 matières,
41 des 42 bilans hebdomadaires concordent. Le seul résiduel, semaine du
16 juin, est compensé par un résiduel opposé semaine du 23 juin, exclue de
l'intersection des 42 semaines. Sur la fenêtre continue du 6 janvier au
29 décembre, les bilans ferment pour les 12 matières. Exemple 693055 :

```text
950 kg initiaux + 13 190 kg reçus − 2 160 kg autres sorties
− 9 840 kg Scan3 = 2 140 kg finaux.
```

Ces quantités portent sur la fenêtre continue, pas sur les 42 semaines du
tableau. Sources : `Inventory_movements/Feuille1`, colonnes G à J ;
`Inventory_and_Replenishment_rules/Stocks!E544` et `E619` pour les deux photos.

**Les inventaires d'emballages ferment aussi, à un autre volume équivalent PF.**
Sur cette même fenêtre continue, les étuis 338929 à Avène donnent :

```text
354 000 UN initiaux + 5 501 500 UN entrées − 2 400 UN autres sorties
− 5 016 700 UN Scan3 = 836 400 UN finaux.
```

Photos `Stocks!E191/E1310` ; 46 lignes hebdomadaires de mouvements renseignées.
Pour les tubes 338928, le bilan ferme également :
`404 065 − 5 367 + 8 670 621 − 2 321 199 − 5 037 642 = 1 710 478 UN`
(`Stocks!E716/E805`, 45 lignes renseignées). Les semaines sans ligne ont des
photos consécutives inchangées : cela ne prouve pas l'absence de flux bruts.
Des résiduels hebdomadaires se compensent sur la fenêtre ; la fermeture cumulée
ne signifie donc pas que chaque mouvement est daté exactement comme la photo.

À titre de contre-calcul seulement, les 5 016 700 étuis documentés exigent
**2 036,7802 kg de 693055** à la BOM. Remplacer les 9 840 kg Scan3 par cette
quantité, en conservant tous les autres mouvements, donnerait **9 943,2198 kg**
de stock final, contre **2 140 kg** observés. Il resterait **7 803,2198 kg** à
expliquer. Réduire le mouvement Scan3 sans contrepartie détruit donc le bilan ;
cela ne justifie ni de changer la BOM, ni d'affecter d'office l'excédent à des
produits supplémentaires. Les inventaires corroborent les débits enregistrés,
pas leur transformation exclusive en PF 268091 conditionnés.

Le PF 268091 à Muret passe sur la même fenêtre de **423 434 à 1 010 323 UN**
(`Stocks!E11/E74`). Ses 51 lignes ferment le cumul : `+3 840 Divers +583 049
dans Sorties = +586 889 UN`. Cette colonne signée ne sépare pas les réceptions
et les départs clients ; elle ne mesure pas la production annuelle de l'usine.

**Le stock MRP des matières partagées reprend généralement le stock total.**
En sommant `Stock_physique` sur l'horizon d'une seule version MRP, les photos
concordent dans 41 versions sur 42 pour chacune des trois matières. Par exemple,
le 5 janvier : 152 520,588 kg pour 002612, 53 669,480 kg pour 007923 et 950 kg
pour 693055, exactement les photos du 6 janvier. Le 26 janvier pour 002612 :
`MRP!J3160 = 109 103,940 kg` immédiatement disponibles et `J3161 = 22 500 kg`
disponibles ultérieurement donnent 131 603,940 kg, soit `Stocks!E379` du 27 janvier.
Ce n'est pas un stock limité à Cicalfate ; la disponibilité ultérieure ne crée
pas une nouvelle réception physique.

Contrôle élargi du seul plan du **5 janvier** contre les **31 photos du
6 janvier** : le J courant concorde exactement dans **19 cas** ; la somme J
sur tous les horizons de cette même version concorde dans **22 cas**. Aucun
H et aucune autre version n'entrent dans ce décompte. Les trois rapprochements
supplémentaires sont 021081/Gaillac, 001848/Gien et 773474/Gaillac, grâce aux
quantités J disponibles plus tard. Ces comptages restent identiques avec une
tolérance de 1e-6 dans l'unité source.

Parmi les neuf écarts restants, **099439/Avène** se distingue :
`J508 = 2 572,742 kg`, contre `Stocks!E694 = 4 672,742 kg`, mais l'entrée prévue
`H508 = 2 100 kg` complète exactement la photo. C'est une concordance
arithmétique stock-plus-entrée, **pas la preuve d'un stock oublié ou bloqué**.
La date de coupe ou le classement en stock/entrée doit être éclairci ; ne pas
réinjecter automatiquement ces 2 100 kg dans J tout en conservant H. Pour les
huit autres écarts, ajouter H courant ne rétablit pas l'égalité. Les différences
de somme J moins photo restent : 001893/Gaillac −375 kg, 002612/Gaillac −855 kg,
007923/Gien −120,020 kg, 038005/Gien −800 kg, 042342/Gien −1 500 000 UN,
693055/Gaillac −10 kg, Cicalfate/Muret −20 UN et Permixon/Muret −3 285 UN.
Elles ne doivent pas être qualifiées automatiquement de stock qualité.

**Stock initial MRP et stock projeté ne sont pas la même observation.** Pour
693055/Avène, la ligne 811 du plan du 5 janvier contient `J = 950 kg`,
`H = 600 kg`, `I = 260 kg` et `K = 1 290 kg` : le départ concorde avec la photo
du 6 janvier, puis le plan applique `950 + 600 − 260 = 1 290`.
Sur l'intervalle de photos du 6 au 13 janvier, les mouvements renseignés
(`Inventory_movements!G1065:J1065`, repère 5 janvier) donnent au contraire
`950 + 0 − 20 = 930 kg`, exactement la photo `Stocks!E568` du 13 janvier.
Le rapprochement conserve la convention des repères hebdomadaires des exports.
La différence ne démontre ni un mauvais stock initial ni une autre BOM :
réception et sorties prévues ne sont pas les mouvements exécutés de cet
intervalle. Les 260 kg du MRP sont le besoin total article/site, tandis que
les mouvements distinguent ici 20 kg en I et zéro en Scan3 J.

**La colonne « Sorties » n'est pas toujours une consommation.** Sur les
42 semaines, elle contient 75 valeurs positives pour 001893, 016332, 029313,
039668 et 099439. Les entrées H sont nulles sur ces lignes ; des hausses de
stock confirment les signes positifs. Exemple 016332, semaine du 3 février :
I = +200 kg, J = 0, Divers = −2,590 kg ; stock 507,050 → 704,460 kg.
La nature précise de ces mouvements positifs n'est pas documentée : ne pas
les appeler automatiquement retours, ni les transformer en consommations.
Aucun I positif n'annule exactement J sur sa semaine, et dix de ces lignes
ont J nul. Il n'y a donc pas de preuve d'une annulation systématique du facteur
matières/emballages par cette colonne ; des retours différés restent possibles.

**Conséquence :** la présence de matières partagées explique une partie des
besoins et stocks totaux du site. Elle ne résout pas automatiquement le facteur
4,55 calculé à l'intérieur de Scan3 : les sorties hors Scan3 sont déjà distinctes.
Pour 001757 et 049371, Scan3 représente même respectivement 98,69 % et 98,62 %
des sorties enregistrées. Le raccordement recette/conditionnement reste à
résoudre sans corriger arbitrairement les coefficients BOM.

Le [rapprochement reproductible](../artifacts/testing/gaillac_sequence_20261008/diagnostics/shared_scope_20261009.json)
conserve semaines, cellules, signes, bilans, versions MRP et empreintes.
Le [script](../artifacts/testing/gaillac_sequence_20261008/diagnostics/shared_scope_20261009.py)
lit seulement les données et crée un rapport. Les totaux ont été retrouvés
indépendamment par deux explorateurs ; six rapprochements stock MRP/photo ont
été contre-vérifiés cellule par cellule. Aucun changement du nominal, aucune
simulation ni suite de tests n'a été exécuté pour ce diagnostic.

### Portée de la proximité avec la demande client

Une quantité servie proche de la demande entrée dans le simulateur ne valide
ni les consommations industrielles, ni la production amont, ni le taux de
service réel. Pour Cicalfate, le contrôle E4C sur les 362 jours dispose de
430 538 PF initiaux à Muret, termine 1 945 715 PF provenant des OF d'ouverture
et exécute 2 318 400 PF nouveaux. Les matières non-Pack des OF initiaux sont
supposées déjà incorporées avant l'horizon : cette hypothèse doit rester visible.

Les 4 264 115 PF achevés/conditionnés se répartissent en 3 976 115 PF expédiés
à Muret et 288 000 PF encore retenus qualité en usine. Le bilan Muret est :
`430 538 + 3 976 115 − 3 572 642 = 834 011 PF`. Sur les 3 572 642 PF demandés,
3 538 909 ont été servis au client à la fin du calcul ; les 33 733 restants
sont déjà expédiés et encore en transport. Ces égalités expliquent le service
simulé ; elles ne résolvent pas l'écart matière/BOM/Scan3.

De même, la différence entre besoin MRP industriel prévu et sortie matière
réalisée n'est pas directement un défaut de service client : ce sont deux
mesures différentes, et les matières partagées couvrent d'autres usages.
Ne pas convertir ce différentiel en produits finis manquants sans raccorder
les prévisions, OF, nomenclatures, en-cours et livraisons sur un même périmètre.

### Consommation en usine confrontée à la production estimée — 9 octobre

Le contrôle part d'un indicateur **indépendant de la matière vérifiée** :
les étuis Scan3 pour les PF d'Avène et Gien ; le bilan de stock du produit
fabriqué pour 773474 à Gaillac. Il applique ensuite les coefficients des
classeurs BOM, sans les modifier :

`matière théorique = production estimée × quantité matière BOM / quantité produit BOM`.

Une production déduite de la consommation de cette même matière ne permettrait
pas de la vérifier : l'égalité serait imposée par le calcul. Les semaines
retenues doivent comporter toutes les observations utilisées ; une absence
ne devient pas un zéro. Les périodes ci-dessous sont discontinues et ne sont
pas des totaux annuels exhaustifs.

| Usine / produit | Base de production estimée | Semaines communes | Volume estimé |
|---|---|---:|---:|
| Avène / 268091 | Scan3 des étuis 338929, un étui par PF | 42, avec les 12 MP | 4 901 500 PF |
| Gien / 268967 | Scan3 des étuis 333362, un étui par PF | 30, avec les 3 MP | 1 000 180 PF |
| Gaillac / 773474 | Δstock du 773474 − G − I − J, signes conservés | 35, avec 021081 | 83 200 kg |

Les quantités suivantes sont arrondies au kg pour la lecture. Les calculs
conservent les décimales sources. « Sorties Scan3 » signifie ici `−ΣJ` de
`Flow_Data_Inventory_movements.xlsx`, pas une consommation certifiée par OF.
Les autres mouvements signés I restent séparés.

| Usine / composant | Besoin selon BOM et production estimée | Sorties Scan3 enregistrées | Rapport |
|---|---:|---:|---:|
| Avène / 12 matières en kg, total | 100 097 kg | 455 693 kg | 4,55 |
| dont 001757 | 7 960 kg | 36 240 kg | 4,55 |
| dont 049371 | 7 363 kg | 33 522 kg | 4,55 |
| dont 693055 | 1 990 kg | 9 060 kg | 4,55 |
| Gien / 038005 | 17 502 kg | 85 995 kg | 4,91 |
| Gien / 773474 | 9 656 kg | 47 794 kg | 4,95 |
| Gien / 042342, gélules en unités | 60 352 862 UN théoriques | 291 790 000 UN | 4,83 |
| Gaillac / 021081 | 743 808 kg | 794 238 kg | 1,068 |

**Avène :** pour 1 000 PF estimés par les étuis, la BOM des douze MP représente
20,4218 kg, contre 92,970103 kg enregistrés en Scan3 sur ce périmètre. Les tubes
recoupent le conditionnement : 4 919 050 tubes pour 4 901 500 étuis (+0,36 %),
sur les mêmes 42 semaines. Les dates et quantités détaillées figurent dans le
[rapprochement existant](../artifacts/testing/gaillac_sequence_20261008/diagnostics/shared_scope_20261009.json).

**Gien :** les semaines retenues commencent les 13/01, 24/02, 03/03, 10/03,
17/03, 24/03, 31/03, 07/04, 19/05, 02/06, 23/06, 30/06, 07/07, 14/07,
21/07, 28/07, 04/08, 08/09, 15/09, 22/09, 29/09, 06/10, 13/10, 20/10,
27/10, 03/11, 10/11, 17/11, 24/11 et 01/12/2025.
Les coefficients viennent de `268967.xlsx/BOM`, lignes 2–4 ; l'étui est ligne 5.
042342 est en UN : il ne faut pas l'additionner aux deux matières en kg.
Les emballages corroborants sont beaucoup plus proches de leur BOM :
708073 à +2,9 % sur les 30 semaines ; 730384 à +5,0 % sur 25 semaines ;
734545 à +0,2 % sur 29 semaines. 344135 n'est pas couvert sur ces semaines.
Restreindre le calcul à tous les emballages disponibles supprimerait notamment
des semaines de consommation de matières sans conditionnement et changerait
fortement le rapport ; cette sélection ne résoudrait pas l'écart.

Les bilans hebdomadaires stock/mouvements se ferment sur les 30 intervalles
pour 773474 et 333362. Pour 038005 et 042342, un décalage entre les semaines
du 16 et du 23 juin laisse respectivement −400 kg et −1 625 000 UN de résiduel
dans ce sous-ensemble, qui ne contient que le 23 juin. Il ne faut pas présenter
ces deux sous-totaux comme des bilans parfaitement fermés.

**Gaillac :** retenir les lundis du 06/01 au 22/12/2025 avec une ligne mouvement
773474, deux photos de ce produit espacées de sept jours et une ligne mouvement
021081 donne 35 intervalles. La BOM `773474.xlsx/BOM!C2,F2:G2` indique 8,94 kg
de 021081 pour 1 000 g de 773474 : `83 200 × 8,94 = 743 808 kg`.
Scan3 donne 794 238 kg, soit 50 430 kg de plus (+6,8 %), et I est nul.
Pour 021081, les bilans stock/mouvements se ferment en cumul sur ces 35
intervalles ; 33 se ferment individuellement, les deux autres présentent
−2 270 kg le 16 juin et +2 270 kg le 23 juin, qui se compensent.
La colonne H brute du 773474 donne 166 400 kg sur ces mêmes semaines,
soit le double des entrées compatibles avec son bilan de stock. Elle reste
inchangée et ne sert pas de production certaine. Les prélèvements et
achèvements peuvent être décalés ; le résiduel de +6,8 % n'est donc pas
automatiquement un taux de rebut. Pour 693055 à Gaillac, l'absence de BOM
industrielle amont empêche ce contrôle matière ; un intrant fictif ne serait
pas une preuve industrielle.

**Conclusion limitée :** l'écart matières/conditionnement est confirmé à Avène
et Gien, alors que le contrôle 021081 → 773474 à Gaillac est nettement plus
proche de la BOM sur son périmètre documenté. Ces contrôles ne démontrent pas
encore si l'écart aval provient d'en-cours, d'affectations à d'autres formats,
d'une conversion d'unité ou d'une incohérence source. Les consommations
simulées contrôlées respectent la BOM ; aucun multiplicateur correctif n'est
introduit.

Les sorties usine reconstituées depuis Muret constituent un autre indicateur :
le HTML actuel utilise `Δstock Muret + |Historique Flow| − Divers`, puis un
décalage de transport issu de la simulation. Ce n'est ni une mesure directe
de production ni le calcul `demand_PF × part de CA livré`. Sans variation
du stock PF détenu en usine, ces départs ne remplacent pas silencieusement
l'estimation de conditionnement ci-dessus.

Les OF initiaux sont également séparés : 1 945 715 PF Cicalfate représentent
39 735 kg théoriques des douze MP. Le moteur les considère déjà incorporées
avant l'horizon ; le classeur des en-cours ne prouve pas ce prélèvement.
Il ne faut donc pas retrancher ces 39 735 kg des sorties industrielles sans
rattachement aux ordres. Dans le CSV d'ouverture, 693055 est en G et les onze
autres MP en KG : convertir avant toute somme.

Contrôles : lectures des XLSX, calculs en mémoire et recoupements indépendants
des bases de production et des coefficients. Aucun moteur, classeur source
ou HTML modifié ; aucune nouvelle simulation ni suite globale exécutée.

### Lots de fabrication : rapprochement avec les prélèvements

Les tailles de fabrication ne sont ni la base 1 000 de la BOM, ni les quantités
standard d'achat FIA. Les deux feuilles de lots donnent les règles suivantes :

| Produit / site | Ancien Extract, feuille Taille de Lots | Flow Inventory, feuille Taile de Lot |
|---|---|---|
| 268091 / Avène | Min. 14 400, max. 142 485 UN, fixe 0 ; E2:G2 | Min. 28 800, max. 142 485 UN, fixe 0 ; E3:G3 |
| 268967 / Gien | Min. = max. 107 800 UN, fixe 0 ; E3:G3 | Identique ; E2:G2 |
| 773474 / Gaillac | Fixe 3 200 000 ; E4 | Identique ; E4 |
| 693055 / Gaillac | Absent | Fixe 600 000 ; E5 |

Les feuilles de lots omettent l'unité. Stocks et en-cours permettent
d'interpréter les deux PF en UN et les deux intermédiaires en G : les lots
fixes de Gaillac représentent donc 3 200 et 600 kg. Aucune colonne ne prescrit
un multiple de palette. Le changement du minimum Cicalfate n'est pas daté.

**Clarification du pas de production :** l'absence de colonne « multiple »
dans ces deux feuilles ne signifie pas son absence dans notre règle de
simulation. Le calcul E4C conserve bien un pas de 14 400 UN, avec minimum
28 800 et plafond 142 485. Les tailles admissibles des nouvelles campagnes
sont 28 800, 43 200, 57 600, 72 000, 86 400, 100 800, 115 200 et 129 600 UN.
Le plus grand multiple sous le plafond est donc **129 600**, et non 142 485.
Les 40 nouvelles campagnes Cicalfate du registre
`gaillac_sequence_20261008/run_E4C_362/data/production_campaigns.csv`
respectent cette liste. Les quantités des ordres déjà engagés sont conservées
séparément ; elles ne prouvent pas la taille initialement lancée. Le pas
configuré n'est pas une colonne supplémentaire inventée dans le classeur.

**Normalisation au plafond source de 142 485 PF**, sans l'assimiler à un lot
admissible dans le simulateur : sa BOM demande 231,39564 kg de 001757, 214,040967 kg de 049371 et
57,84891 kg de 693055. Les incréments relevés dans J Scan3 sont proches de
240, 222 et exactement 60 kg, avec des multiples communs aux douze MP sur
les 45 semaines renseignées. Ils représentent environ 3,7185 % de plus que
la BOM de ce plafond. Au maximum effectivement admissible de 129 600 PF,
la BOM de 693055 vaut 52,6176 kg et l'écart à 60 kg devient 14,0303 %.
La proximité de 3,7 % ne valide donc pas la taille de lancement simulée.
Ce motif est compatible avec des charges répétées ; il ne prouve ni taille
de cuve, ni rendement, ni numéro de lot.

En revanche, I seul n'indique pas un même nombre de lots pour les MP : sur
06/01–29/12, 720,022 kg de 001757 représentent 3,112 équivalents du plafond source,
691,050 kg de 049371 en représentent 3,229 et 2 160 kg de 693055 en
représentent 37,339. Le total 2 160 est divisible par 60, mais les lignes I
de 693055 comportent aussi 10, 20, 30, 40, 50 kg, etc. : le quotient 36 ne
prouve donc pas 36 fabrications exécutées.

Sur les 42 semaines communes matières/emballages, les 9 060 kg Scan3 de
693055 donnent 156,615 équivalents du plafond source par la BOM, contre
34,400 pour les 4 901 500 étuis. Le rapport reste 4,552493 : changer l'unité
en nombre de lots ne supprime pas l'écart matière/conditionnement.

**Permixon :** le lot de 107 800 PF demande 1 040,7786004 kg de 773474,
1 886,4111728 kg de 038005 et 6 504 867,6 gélules 042342 théoriques.
Les J de 773474 du 6 et du 13 janvier, 1 026,4 et 3 166 kg, représentent
0,986 et 3,042 équivalents de lot. Mais le 13 janvier, 038005 et 042342
n'en représentent que 2,332 et 2,556 : les agrégats hebdomadaires ne donnent
pas des lots individuels concordants pour toutes les matières.

**Gaillac :** un lot de 3 200 kg de 773474 exige 28 608 kg de 021081 selon
la BOM. Les entrées H des plans MRP à Gaillac sont des multiples exacts des
lots fixes : 906/906 lignes positives pour 773474 et 953/953 pour 693055,
sur les 52 versions. Ces nombres de lignes ne sont pas des nombres d'OF :
les versions peuvent répéter un même événement. Les PF ne figurent dans
ce fichier MRP qu'à Muret, dont les entrées ne comptent pas directement
les lots de fabrication.

Les 20 lignes O.Proc initiales de Cicalfate totalisent 1 945 715 UN, avec
notamment cinq lignes à 141 795 et trois à 141 800. Certaines sont inférieures
aux minimums ; leur caractère initial ou résiduel n'est pas précisé. Elles
ne justifient pas d'imposer partout une taille fixe de 142 485 UN.
Contrôles en lecture seule des paramètres et motifs par deux agents distincts ;
aucune règle de simulation modifiée ni fabrication industrielle inventée.

### Permixon : distinction boîte, gélule et plaquette

La référence 268967 est libellée `PERMIXON 160MG 60GÉL VTE` dans les
mouvements, et son étui 333362 `ETUI PERMIXON 160/60GE`. La
[fiche officielle BDPM](https://base-donnees-publique.medicaments.gouv.fr/medicament/63398507/extrait),
consultée le 9 octobre 2026, confirme une présentation de 60 gélules sous
plaquettes PVC/aluminium et 160 mg d'extrait par gélule. Elle ne permet pas
de confirmer la proposition « quatre plaquettes de quinze ou six de dix
selon les lots » ; ce détail ne devient pas une règle de simulation.

La BOM `268967.xlsx/BOM`, lignes 3–5, prévoit pour 1 000 PF : 60 342 gélules
042342, 9 654,718 g de 773474 et 1 000 étuis 333362. L'unité PF correspond
donc à une boîte, pas à une gélule ou une plaquette. Contrôles de dosage :

- 60 × 160 mg = 9,6 g par boîte, soit 9,6 kg pour 1 000 boîtes ;
- BOM : 9,654718 kg pour 1 000 boîtes, soit +0,56998 % ;
- 60 342 × 160 mg = 9 654,72 g, presque exactement la quantité de 773474.

Cette concordance étaye l'unité de la BOM ; elle ne prouve pas que l'excédent
de 0,57 % est un rebut ou un rendement documenté. Les supports de plaquettes
708073 et 730384 sont déjà donnés par 1 000 boîtes : 7,930 kg de PVC et
212 mètres d'aluminium. Aucun facteur supplémentaire de quatre ou six
plaquettes n'est appliqué dans les ratios du moteur contrôlé.

Le registre E4C le confirme pour la production simulée du jour 103 :
107 800 PF, 107 800 étuis, 6 504 868 gélules après arrondi entier,
1 040,7786004 kg de 773474, 854,854 kg de PVC et 22 853,6 m d'aluminium.
Cela vérifie l'exécution de la BOM, pas la fabrication industrielle.

Sur les 30 semaines communes Gien du rapprochement précédent, les
291 790 000 gélules Scan3 équivalent à 4 863 167 boîtes de 60, sans pertes,
contre 1 000 180 étuis sortis. Avec la BOM de 60,342 gélules par boîte,
l'équivalent devient 4 835 604 boîtes : l'écart reste proche de cinq.
Le détail du nombre de plaquettes par boîte ne résout donc pas l'écart
matières/conditionnement constaté. Aucune nomenclature ni simulation modifiée.

**Hypothèse distincte : matières communes à plusieurs présentations Permixon.**
Le [RCP ANSM R0437036](https://agence-prd.ansm.sante.fr/php/ecodex/rcp/R0437036.htm),
mis à jour le 14 août 2025 et consulté le 9 octobre 2026, liste des boîtes
sous PVC/Alu de 30, 56, 60, 100 et 180 gélules, avec des codes CIP distincts
(rubriques 6.5 et 8), ainsi que des présentations en flacon. Cela confirme
l'existence réglementaire de plusieurs présentations, pas leurs volumes de
fabrication à Gien ni leur inclusion dans l'extraction Scan3.
La relecture des 14 classeurs locaux n'identifie que le PF Permixon 268967,
libellé 60 gélules. Les matières 038005, 042342 et 773474 ne portent pas de
format commercial ; l'étui 333362 et l'aluminium 730384 mentionnent 60.
Le fichier des mouvements ne comporte pas de colonne PF consommateur,
format ou OF permettant d'attribuer J aux autres présentations.

Si les sorties des matières communes couvrent plusieurs présentations alors
que 333362 représente uniquement l'étui du 268967 en boîte de 60, le
rapprochement actuel oppose un périmètre matière plus large à une seule
référence conditionnée. C'est une explication plausible de l'écart, mais pas
une affectation industrielle prouvée. La BOM de la boîte de 60 peut rester
correcte dans ce cas. L'hypothèse doit être distinguée du sens utilisateur
initial « Scan3 concerne uniquement 268091 et 268967 ».

Sur les 30 semaines communes, la BOM des 1 000 180 étuis représente
60 352 861,56 gélules, contre 291 790 000 en Scan3. Le résiduel à expliquer
vaut 231 437 138,44 gélules. Son attribution à d'autres formats, rebuts ou
en-cours ne peut pas être déduite de la seule liste des CIP. Cinq formats
ne donnent pas automatiquement un facteur cinq ; les volumes de chaque
présentation et leur contenu en gélules déterminent le besoin total.
Si le périmètre partagé est confirmé, conserver le stock matière total et
distinguer les besoins du 268967 et les autres besoins, sans multiplier
sa BOM, diviser arbitrairement le stock ou compter deux fois les usages.

### Colonne Sorties seule : équivalents BOM et parallèle avec le CA perdu

Période : mouvements des semaines du 06/01 au 22/12/2025 incluses, jusqu'à
la photo de clôture du 29/12. Ici, seule la colonne I de
`Flow_Data_Inventory_movements.xlsx` est utilisée, sans ajouter J Scan3 :

`équivalent PF = −somme(I) × 1 000 / quantité matière BOM pour 1 000 PF`.

Les unités sont harmonisées avant division. Ces équivalents sont des
conversions théoriques, pas des fabrications observées. Ils ne s'additionnent
pas entre composants. Un crédit net de stock donne un équivalent négatif,
jamais une production négative.

| Usine / matière | Sortie I nette, kg sauf mention | Équivalent PF selon BOM |
|---|---:|---:|
| Avène / 001757 | 720 | 443 363 |
| Avène / 001848 | 876 | 719 255 |
| Avène / 001893 | 7 112 | 921 910 |
| Avène / 002612 | 565 342 | 278 493 476 |
| Avène / 016332 | −12 857 | −26 389 676 |
| Avène / 029313 | −1 354 | −33 340 764 |
| Avène / 039668 | −1 010 | −24 870 074 |
| Avène / 049371 | 691 | 460 025 |
| Avène / 055703 | 960 | 11 821 613 |
| Avène / 099439 | −54 054 | −26 627 497 |
| Avène / 693055 | 2 160 | 5 320 197 |
| Avène / 007923 | 202 983 | 62 494 791 |
| Gien / 038005 | 27 999 | 1 600 013 |
| Gien / 042342 | 25 159 000 UN | 416 940 |
| Gien / 773474 | 10 641 | 1 102 114 |

Les valeurs affichées sont arrondies ; les équivalents sont calculés avant
arrondi. Les coefficients viennent de `268091.xlsx/BOM` lignes 2–13 et
`268967.xlsx/BOM` lignes 2–4. Les étuis, avec cette seule colonne I, donnent
2 400 UN à Avène et 0 UN à Gien. Les semaines absentes ne sont pas remplacées
par zéro. Cette dispersion ne permet pas de traiter I comme une consommation
BOM homogène des deux PF ; elle ne prouve pas non plus à elle seule la nature
de chaque autre usage, retour ou correction.

Le parallèle avec le CA conserve la formule de la comparaison client :
`non livré estimé semaine = demande_PF × CA perdu / (CA livré + CA perdu)`.
La demande est positive, les deux CA hebdomadaires non négatifs, leur somme
strictement positive et les cinq jours financiers présents. La correction
négative quotidienne de CA reste signée dans l'agrégation. La conversion en
unités suppose un prix moyen et un périmètre communs pour livré et non livré.

| Produit | Semaines estimables sur 51 | Demande, UN | Non livré estimé, UN | Livré estimé, UN |
|---|---:|---:|---:|---:|
| Cicalfate 268091 | 51 | 3 563 142 | 228 131 | 3 335 011 |
| Permixon 268967 | 47 | 1 688 810 | 71 318 | 1 617 492 |

Pour Permixon, les semaines des 14, 21, 28 avril et 26 mai ont une demande
négative ramenée à zéro, mais un CA positif : l'estimation est exclue, pas
remplacée par zéro. Le total sur 47 semaines n'est pas une livraison annuelle
mesurée. Les taux non livrés pondérés par la demande valent 6,4025 % et
4,2230 % ; ils diffèrent des ratios financiers pondérés par les euros.
Pour comparer directement I à ces 47 semaines de Permixon, retirer aussi
les quatre semaines de ses mouvements : 038005 donne alors 25 998,986 kg,
soit 1 485 726 PF équivalents ; 773474 donne 9 587,400 kg, soit 993 027 PF ;
042342 reste à 25 159 000 UN, soit 416 940 PF. Les retraits viennent de
la semaine du 21 avril (`Feuille1!I474` et `I1250`). Ces quantités ne doivent
pas être confondues avec les totaux sur 51 semaines du tableau précédent.

À Avène, les 228 130,900678 PF non livrés estimés correspondraient à
92,621146 kg de 693055, 342,698239 kg de 049371 ou 370,484583 kg de 001757
selon la BOM. Ces besoins théoriques ne sont ni des pertes physiques de
matière ni des quantités à retrancher des mouvements réels. Le CA perdu
ne permet pas d'attribuer une sortie I à une commande non livrée, ni de
prouver que celle-ci manque de matière : stock PF, en-cours, fabrication et
transport interviennent aussi. Il ne résout pas à lui seul le rapport
matières/conditionnement constaté dans Scan3.

Ces calculs ont été faits en lecture seule à partir des XLSX et du CSV CA,
sans changement de simulation ni de graphique.

### Prévisions clients et demande : le dénominateur du service

Le recoupement direct des deux fichiers de demande confirme que la prévision
Flow est nettement supérieure à la demande `demand_PF` utilisée dans le graphe.
Sur les mêmes 42 semaines discontinues que l'audit des 12 matières :

| Produit | Prévision Flow connue avant la semaine, UN | Demande `demand_PF`, UN | Historique Flow, UN |
|---|---:|---:|---:|
| Cicalfate 268091 | 8 278 537 | 3 025 902 | 3 493 833 |
| Permixon 268967 | 2 508 672 | 1 456 031 | 1 457 884 |

Une seule prévision est sélectionnée pour chaque semaine : dernier snapshot
strictement antérieur qui contient la semaine cible. Les projections révisées
ne sont pas additionnées. `demand_PF` conserve la convention step 1 = 30/12/2024
et les valeurs négatives Permixon ramenées à zéro. Sa colonne `forecast_demand`
est égale à `real demand` : elle ne constitue pas la prévision Flow indépendante.

La demande affichée vaut ainsi 36,6 % de la prévision pour Cicalfate et 58,0 %
pour Permixon. Un taux de service calculé sur cette demande peut être élevé
sans réaliser tout le volume initialement prévu. Il ne faut pas assimiler
le ratio consommation réelle/prévision MRP au taux de service client.

Cela ne démontre pas la cause complète de l'écart matière : avec la BOM fournie,
les 8 278 537 PF prévus de Cicalfate représenteraient seulement 3 361,086 kg de
693055, contre 19 600 kg dans les plans MRP matière sur ces repères. Le lien
prévisions PF/ordres/consommations reste donc non réconcilié. L'historique Flow
diffère aussi de `demand_PF` et ne doit pas le remplacer silencieusement.

Les [valeurs sélectionnées et cellules sources](../artifacts/testing/gaillac_sequence_20261008/diagnostics/customer_forecast_gap_20261009.json)
sont conservées avec les empreintes stables des classeurs. Lecture seule ;
aucune simulation ni règle modifiée. Les chiffres Cicalfate ont été retrouvés
indépendamment par un explorateur.

## 9. Preuves et entretien de cette connaissance

Le [registre durable](reference/source_knowledge.json) conserve le catalogue,
les 22 empreintes, les paramètres extraits, les conclusions et leurs limites.
Il rassemble les résultats pour éviter une collection de nouvelles notes.
Le [dossier local de preuves](../artifacts/testing/source_knowledge_20261008/)
contient les six rapports détaillés et les calculs de cette passe.

Les contrôles exécutés sont des lectures de sources, calculs en mémoire,
rapprochements indépendants et vérifications d'empreintes. Le rapport
demande/finance a été reproduit sans différence sur ses 22 sections contrôlées.
Le facteur deux et le calendrier ont été contre-vérifiés par un agent distinct.
Le [doctor](../artifacts/testing/toolbox/doctor-78120460a26b42faaf346acd83087458/manifest.json)
est passé ; il vérifie l'environnement, pas la calibration industrielle.
Le [manifeste final](../artifacts/testing/source_knowledge_20261008/manifest.json)
consigne les empreintes finales et les documents produits.

**Non exécutés :** simulation, tests globaux, navigateur, recalcul Excel,
rafraîchissement des preuves Internet et tests altérant volontairement des
fichiers. Rien de cela n'est compté comme une vérification réussie.

À la réception d'un nouveau fichier, comparer son contenu métier et ses dates,
pas seulement son nom ou sa date de modification. Mettre à jour ce document et
le registre ; conserver une conclusion ancienne comme historique lorsqu'une
cellule source a changé. Une empreinte différente signale la nécessité d'un
nouveau rapprochement, pas automatiquement une erreur du fichier.

### Essai des autres formats : comparaison 2025 — 9 octobre 2026

**Réexamen métier de F2 : voir le diagnostic ci-dessous.** Les vérifications
arithmétiques de cet essai ne suffisent pas à valider son hypothèse de périmètre.

La [comparaison séparée](../resultats/formats_partages_20261009/comparaison.html)
oppose les stocks et mouvements sources à E4C (référence conservée) et F2.
F2 est un essai explicatif rétrospectif du 1er janvier au 28 décembre, avec
les 52 photos de stocks jusqu'au 29 décembre. Il ne remplace pas le nominal.

**Essai historique invalidé le 16 octobre 2026 :** cet essai supposait qu'une partie de Scan3 correspondait à d'autres formats
utilisant les mêmes matières. La part supplémentaire est constante par famille :
`1 − étuis × coefficient BOM du composant pivot / sorties Scan3 du pivot`.
Gien : 79,31634 %, d'après 1 000 180 étuis et 291 790 000 gélules sur les
30 semaines communes. Avène : 78,03522 %, d'après 4 901 500 étuis et 9 060 kg
de 693055 sur les 42 semaines communes. Ces parts sont estimées après coup
avec 2025, pas connues industriellement au 1er janvier.

Le complément physique est appliqué uniquement aux jours dont I est déjà
représenté comme une sortie observée : 038005 et 773474 à Gien ; 001757,
001848, 002612, 007923, 049371, 055703 et 693055 à Avène. Il vaut
`part supplémentaire × (−J)` et s'ajoute à I, sans remplacer celui-ci.
Les semaines sont réparties uniformément du lundi au dimanche ; les cinq
jours de janvier appartenant à la première semaine source sont conservés.
La prévision des neuf couples devient `max(besoin BOM propre, besoin I MRP
déjà connu)`, avec les protections séparées. Le futur J n'alimente pas le MRP.

Cette hypothèse contredit la sémantique désormais confirmée de I et J et ne doit
plus être utilisée dans le nominal ni dans une projection. Les six autres
couples (042342/Gien ; 001893, 016332, 029313, 039668,
099439/Avène) conservent leurs usages estimés existants : ajouter encore une
part de J pouvait les compter deux fois. Le premier calcul F1 a été interrompu
pour cette raison et n'est pas utilisé. Les BOM, stocks initiaux, en-cours,
délais, sécurités et demandes des deux PF restent inchangés. Aucun stock ni
approvisionnement réel n'est imposé. Les autres formats sont représentés par
leurs besoins matières, sans inventer leurs références, ventes ou capacités.

| Écart absolu moyen aux 52 photos | E4C | F2 |
|---|---:|---:|
| 773474 / Gaillac, kg | 12 000 | 5 846 |
| 773474 / Gien, kg | 7 520 | 5 366 |
| 021081 / Gaillac, kg | 579 002 | 276 527 |
| 693055 / Gaillac, kg | 497 | 853 |
| 693055 / Avène, kg | 451 | 743 |
| 268091 / Muret, UN | 289 191 | 289 191 |
| 268967 / Muret, UN | 177 680 | 173 533 |

La production physique de 773474 à Gaillac, carnet initial inclus, passe de
28 800 à 89 600 kg sur les 362 jours ; celle de 693055 de 2 400 à 12 600 kg.
Les quantités produites des deux PF et le service client journalier sont
inchangés. Les besoins supplémentaires de F2 sont tous servis le jour prévu.
L'hypothèse rapproche donc plusieurs volumes amont, mais ne résout pas les
stocks de 693055 et ne constitue pas une identification du MRP industriel.

Le HTML compare, sur les neuf couples, les sorties totales sources `−I−J`
aux consommations simulées BOM + autres usages. Les estimations de production
des PF utilisent leurs étuis spécifiques (et le tube pour Cicalfate) : les
matières supposées familiales ne sont plus affichées comme une production
certaine de la seule référence. La demande et la réponse réelle estimée
acceptées précédemment sont conservées.

[Protocole et exécution](../artifacts/testing/formats_partages_20261009/simulation/report_F2.json),
[oracle indépendant](../artifacts/testing/formats_partages_20261009/validation/independent_final.json)
et [manifeste de livraison](../artifacts/testing/formats_partages_20261009/manifest.json).
L'oracle spécifique passe ; le contrôleur générique refuse quatre familles de
contrôles car il ignore le calendrier additionnel F2. Ce refus reste conservé,
sans déclarer la qualification globale réussie. Le navigateur automatique
a rencontré un refus d'accès Windows à la création de son canal de communication ;
aucune relance ni contournement n'a été tenté. Les contrôles JavaScript en mémoire
ne constituent pas une revue visuelle dans un navigateur.

### Réexamen de l'essai autres formats : bilan physique et calendrier

Relecture des sources et des CSV existants, sans nouvelle simulation ni
modification du moteur, des classeurs ou du HTML. Le [rapport de rapprochement](../artifacts/testing/formats_partages_20261009/validation/physical_scope_review.json)
conserve les semaines, les quantités, les cellules et les empreintes consultées.
Les bilans principaux ont été recalculés par un agent indépendant.

**Deux paramètres changent simultanément dans F2.** Le calendrier physique
ajoute une part de J et la prévision des neuf couples devient le maximum entre
le besoin BOM propre et le besoin MRP source connu. L'amélioration des stocks
ne peut donc pas être attribuée aux seuls autres formats. La colonne I des
mouvements désigne un mouvement signé ; I du fichier MRP désigne un besoin
prévisionnel : ce sont deux informations différentes.

**Une part annuelle ne reproduit pas le calendrier des consommations.**
Sur une semaine où les usages I sont servis, le bilan de l'essai est :

`sorties F2 = consommation BOM simulée + sorties I + part autres formats × sorties J`.

Ce total n'égale I + J que si la consommation BOM simulée correspond à la
part restante de J. Du 13 au 19 janvier, 693055/Avène présente 360 kg en J,
zéro en I, mais F2 ne consomme que 281 kg : la production propre n'en prélève
aucun. Pour 773474/Gien, les quantités correspondantes sont 3 166 kg et
2 511 kg. Le premier prélèvement BOM propre des deux matières a lieu le
14 avril dans F2. Les OF d'ouverture d'Avène supposent leurs matières déjà
incorporées avant janvier ; cette hypothèse doit être revue séparément de la
part des autres formats. Une différence de calendrier vrac/conditionnement
reste également possible ; les étuis ne datent pas la fabrication du vrac.

**Exemple continu vérifié : 693055/Avène, du 6 janvier au 2 juin.** Les
21 semaines sont toutes documentées et Divers est nul :

| Bilan, kg | Sources industrielles | F2 |
|---|---:|---:|
| Stock au 6 janvier | 950 | 976,556 |
| Réceptions sur la période | 5 390 | 6 000 |
| Consommation totale sur la période | 5 470 | 4 655,393 |
| Stock au 2 juin | 870 | 2 321,163 |

L'excès final de 1 451,163 kg se décompose en 26,556 kg au départ,
610 kg de réceptions supplémentaires et 814,607 kg de consommation manquante.
Sources : mouvements `Feuille1!G1065:J1085`, stocks `Stocks!E544/E1220`.
Les niveaux réels ne sont pas corrigés. Les écarts hebdomadaires et les bilans
sur les semaines communes sont distincts des totaux annuels : une semaine
absente reste inconnue.

**Conséquence pour la suite :** garder F2 comme essai explicatif ; ne pas
adopter son coefficient comme règle industrielle. Isoler d'abord un rejeu
amont avec les sorties totales documentées imposées, sans les ajouter aux
prélèvements propres, pour évaluer le réapprovisionnement. Tester séparément
la modification de prévision. Revoir ensuite les consommations de la
production propre, les en-cours initiaux et le lien vrac/conditionnement.
Ces essais ne sont pas exécutés dans ce réexamen.

### Protocole F3 : usages agrégés reconstitués dans le stock commun

Suite autorisée après le réexamen : conserver les sources et représenter les
usages complémentaires dans le simulateur. Essai séparé sur 2025, même réseau
et mêmes neuf couples que F2. Les six couples déjà traités par estimation
restent hors de cette extension ; leurs données comportent des mouvements I
positifs qui ne peuvent pas être qualifiés automatiquement de consommations.

Pour une semaine documentée, `A = -I` conserve les autres sorties observées.
`T = -J` est le volume agrégé Scan3 et `O` le prélèvement propre réellement
exécuté par la simulation pendant cette même semaine. Le complément appelé
vaut `R = max(0, T - O)` ; le dépassement propre `D = max(0, O - T)` reste
visible. L'identité est `A + O + R = A + T + D`. Déduire O de I + J effacerait
potentiellement des usages I distincts : ce calcul est exclu.

R est appelé une seule fois à la clôture du dimanche, après les prélèvements
propres, puis servi sur le stock commun disponible ; le manque devient un
retard distinct. Le dimanche est une convention de comptabilisation de la
semaine observée, pas une date de fabrication industrielle connue. Aucun
prélèvement passé n'est annulé, aucun excès n'est compensé par une semaine
ultérieure. Les semaines sans source conservent le traitement précédent.
La première semaine tronquée au 1er janvier utilise un prorata explicite et
est exclue des bilans industriels portant sur des semaines complètes.

La prévision F2 est conservée : maximum du besoin BOM propre et du besoin
MRP source déjà connu, protections séparées. Les observations J futures
n'alimentent pas le plan. Les BOM, demandes clients, stocks initiaux et
paramètres d'approvisionnement ne sont pas modifiés. Le seul levier changé
par rapport à F2 est la construction de l'usage complémentaire physique.

R doit être nommé **usages agrégés reconstitués**, pas consommation mesurée
des autres formats. Sa valeur dépend de la production propre simulée : il
peut absorber un décalage de fabrication propre, d'en-cours ou de
conditionnement. La fermeture du bilan J est construite et ne valide donc
pas à elle seule la fabrication industrielle ni la répartition par format.
Il s'agit d'un rapprochement 2025 avec les observations disponibles, pas d'un
modèle autonome des autres produits au-delà des données.

Les preuves et résultats de cet essai sont conservés séparément sous
`artifacts/testing/formats_reconciles_20261009/`. La référence F2 et la
référence antérieure E4C sont conservées pour comparaison.

**Résultat F3 exécuté.** Un calcul de 362 jours s'est terminé en 946,812 s,
code retour nul et empreintes stables. La [comparaison HTML](../resultats/formats_reconciles_20261009/comparaison.html)
oppose F2 et F3 aux sources ; E4C reste accessible dans la comparaison précédente.
Les quantités ET les dates de production des deux PF, ainsi que les livraisons
clients quotidiennes, sont identiques à F2. Aucun stock réel n'a été ajusté.

Sur les 47 semaines complètes de 693055/Avène, les 9 840 kg de Scan3 se
répartissent désormais en 847,728 kg propres et 8 992,272 kg reconstitués.
Les 2 160 kg d'autres sorties I restent distincts. Tous les compléments des
neuf couples ont été servis à leur clôture, sans retard. Les consommations
propres restent supérieures à J sur deux semaines de 773474/Gien (2 081,557 kg
d'excès cumulé) et cinq semaines de 038005/Gien (8 379,260 kg). Ces excès ne
sont ni annulés ni déplacés ; un rapprochement parfait n'est pas revendiqué.

| Écart absolu moyen aux 52 photos, kg | F2 | F3 |
|---|---:|---:|
| 693055 / Avène | 743 | 563 |
| 693055 / Gaillac | 853 | 898 |
| 773474 / Gien | 5 366 | 5 600 |
| 773474 / Gaillac | 5 846 | 5 723 |
| 021081 / Gaillac | 276 527 | 255 621 |
| 001757 / Avène | 2 029 | 1 421 |
| 001848 / Avène | 2 363 | 1 866 |
| 049371 / Avène | 2 434 | 1 592 |
| 007923 / Avène | 10 640 | 8 672 |
| 002612 / Avène | 19 153 | 18 761 |
| 055703 / Avène | 133 | 142 |
| 038005 / Gien | 21 716 | 18 709 |

Les deux stocks PF de Muret restent identiques à F2. Le bilan est donc neuf
rapprochements améliorés, trois dégradés et deux inchangés sur les quatorze
couples contrôlés ; F3 ne remplace pas automatiquement la référence.

**Le défaut résiduel de 693055/Avène est maintenant isolé sur la période
continue du 6 janvier au 2 juin :** réel `950 + 5 390 - 5 470 = 870 kg` ;
F3 `967,143 + 6 600 - 5 470 = 2 097,143 kg`. L'écart provient de 1 210 kg
de réceptions supplémentaires et de 17,143 kg initiaux. Il ne faut plus
présenter la consommation manquante comme la cause de cet écart sur cette
période. La suite porte sur le réapprovisionnement et, à Gien, sur les
semaines de prélèvements propres excédentaires.

Le [contrôle indépendant](../artifacts/testing/formats_reconciles_20261009/validation/independent_final.json)
passe 1 214 444 vérifications, sans certifier la calibration industrielle.
La qualification native reste refusée : son contrat ne connaît pas les
438 allocations et 347 demandes journalières du complément F3 ; ces écarts
sont [entièrement rapprochés](../artifacts/testing/formats_reconciles_20261009/validation/generic_refusal_review.json),
sans transformer le refus en succès. Les champs de provenance du CSV
quotidien natif décrivent I seul ; le complément est documenté dans le
registre hebdomadaire F3 et les événements de lots. Le navigateur reste
non exécuté après son refus d'accès Windows antérieur. Les preuves finales
sont réunies dans le [manifeste de livraison](../artifacts/testing/formats_reconciles_20261009/manifest.json).

### Audit exhaustif de l'amont — 9 octobre 2026

**Présentation retenue par l'utilisateur pour les prochaines comparaisons :**
conserver le format de cet audit HTML : classement des écarts, sélection par
matière et site, courbes sources/simulation/référence antérieure clairement
nommées, détail cliquable de chaque semaine et accès aux paramètres, en-cours
et décisions. Garder les unités, dates, cellules sources et données absentes
explicites ; séparer mouvements exécutés, reconstitutions et plans MRP. Cette
préférence valide la présentation, pas les paramètres ni la calibration de F3.

Le [rapport interactif par matière et site](../resultats/amont_audit_20261009/audit_amont.html)
rapproche les 30 couples documentés : 1 213 lignes de mouvements et 1 540 photos.
Les 52 versions du MRP ont été relues (53 398 lignes, y compris les deux PF à
Muret) : tous les bilans K ferment. Le rapport conserve les sources, les
reconstitutions et les événements simulés séparément. Il examine F3 face aux
sources, avec E4C comme témoin de stock ; il n'adopte pas F3 comme nominal.

Constats établis, à distinguer des règles encore à calibrer :

- **Périmètre incomplet** : 007923/Gien n'a pas d'état de stock dans le modèle.
  001893/Gaillac et 002612/Gaillac ont un stock initial mais leur approvisionnement
  est explicitement `unconfigured`. Une valeur absente n'est pas un stock nul.
- **Première semaine F3** : le prorata 5/7 décrit plus haut est contredit par les
  photos du 1er et du 6 janvier. Quatorze des quinze bilans sources ferment avec
  les mouvements entiers, aucun avec leur prorata. Pour 693055/Avène, les 60 kg
  correspondent déjà au 1er–5 janvier : leur proratisation crée 17,143 kg de
  stock supplémentaire. L'exception 002612/Gaillac présente un écart source.
  Ce constat n'a pas encore donné lieu à un nouveau calcul corrigé.
- **Sens de I** : 81 mouvements positifs sur six couples font entrer du stock.
  H seul ne suffit pas à représenter leurs réceptions ; `-I-J` est un mouvement
  net, pas nécessairement une consommation brute. Le mécanisme actuel exclut
  ces couples du rejeu observé I et conserve son estimation précédente.
- **773474/Gaillac** : les entrées brutes H donnent 185 600 kg, contre 92 800 kg
  reconstitués par les photos/G/I/J. Le facteur deux est exact sur les 41 bilans
  disponibles. Les valeurs sources restent inchangées. Les 91 autres écarts
  de bilan hebdomadaire se compensent par épisodes ; 17 couples présentent des
  écarts opposés les semaines du 16 et du 23 juin.
- **Date H du MRP** : 50/51 groupes d'en-cours concordent avec leur semaine de
  livraison physique, contre 5/53 avec leur disponibilité après traitement.
  Cela soutient H = arrivée physique pour les engagements documentés, sans
  identifier chaque proposition future. Les J futurs sont du stock déjà
  présent qui devient disponible, conformément à la confirmation utilisateur.
- **Dates exportées** : 43 ordres internes de 693055/Avène et 773474/Gien ont
  une `order_date_imt` différente de `release_day`. Les consommateurs identifiés
  sont des exports, rapports et suivis ; aucun effet sur l'ordonnancement
  physique n'est démontré. L'audit utilise le départ réellement exécuté.
- **Transport interne** : les sorties de Gaillac et entrées du site aval sont
  égales chaque semaine commune (36 pour 773474, 35 pour 693055). Cela peut
  refléter une comptabilisation commune ; ce n'est pas une preuve de transit
  nul ni une validation du délai FIA comme durée physique de transport.

Les FIA documentent des quantités standards, sans établir universellement un
minimum ou un multiple obligatoire. Les tailles reçues de 001848/Avène et
055703 correspondent bien aux standards ; ce n'est pas le cas de toutes les
matières et des étuis. Les versions MRP montrent des maintiens, changements
de quantité, anticipations et reports, sans prouver un gel universel.

Ordre des corrections proposé : compléter les routes manquantes ; corriger
le prorata initial et les dates trompeuses ; traiter explicitement les
mouvements nets positifs ; puis tester les protections datées, engagements
maintenus/replanifiables et tailles de lots sur toutes les paires. Les photos
réelles et la BOM ne sont pas redimensionnées. Le facteur « autres formats »
ne constitue pas une identification de fabrications industrielles.

Les [lignes rapprochées](../artifacts/testing/amont_audit_20261009/comparaison_mouvement_par_mouvement.csv)
et le [bilan complet](../artifacts/testing/amont_audit_20261009/bilan_par_matiere.csv)
permettent de vérifier chaque chiffre. Les totaux de flux comparés portent
uniquement sur les mêmes semaines complètes documentées ; ce ne sont pas
automatiquement des totaux annuels.

**Besoins prévus comparés à date identique :** 45 944 positions futures
complètes, sur 27 couples, sont rapprochées dans l'onglet MRP. Seules les
lignes simulées `requirement` sont additionnées, avant anticipation de
sécurité ; les diagnostics `industrial_*` ne sont pas ajoutés. Les 1 404
sommes par plan concordent avec `dated_requirement_qty`. La semaine courante
et la dernière semaine partielle de l'horizon sont exclues. Les sources
absentes restent absentes. Sur les huit prochaines semaines des plans,
le rapport besoin simulé/source vaut 63,3 % pour 021081/Gaillac, 49,5 % pour
693055/Gaillac et 64,2 % pour 773474/Gaillac. Ces statistiques portent sur
des positions répétées de plans glissants, pas des consommations annuelles.

La propagation aval → Gaillac → BOM **fonctionne** : dans le plan du
5 janvier, 10 800 kg proposés vers Avène donnent 10 800 kg de besoins à
Gaillac ; 56 351 kg proposés vers Gien donnent le même besoin à Gaillac,
puis 48 000 kg de nouvelles fabrications après déduction des stocks et
en-cours, soit 429 120 kg de 021081 (`48 000 × 8,94`). Les propositions
futures sont propagées, pas seulement les commandes exécutées.
En revanche, les besoins industriels locaux des produits fabriqués à
Gaillac ne sont pas directement réconciliés : leur demande vient des
destinations représentées. 021081 reste hors des neuf paires F3 et son
complément prévisionnel « autres usages » devient nul dès le 6 janvier.
Il faut donc vérifier le périmètre et le calcul net de chaque nœud ; ajouter
tous les I industriels aux besoins déjà propagés créerait un double compte.

La comparaison complète des réceptions prévues H et des stocks projetés K
simulés reste limitée par les journaux : pas de K explicite, et dates des
propositions essentiellement exportées en disponibilité, tandis que le H
source est rattaché aux arrivées physiques. Elle n'est pas déclarée réalisée.
Les preuves sont dans le
[manifeste](../artifacts/testing/amont_audit_20261009/manifest.json).

### Suite proposée après l'audit amont : corrections et délais

La présentation HTML est acceptée ; aucun nouveau paramétrage du moteur n'est
adopté par cette décision. L'aval constitue une référence fonctionnelle à
préserver, mais ses stocks et son service ne sont pas entièrement calibrés :
F3 présente encore un écart moyen de 289 191 UN pour Cicalfate à Muret et
173 533 UN pour Permixon. Cette section décrit l'essai historique F3. Dans la
référence actuelle, le CA reste un indicateur financier séparé : aucune quantité
de service en unités n'en est déduite.

This paragraph describes the historical F3 experiment, not the current rule.
F3 placed the 10/15 working-day finished-goods delay at Avene/Gien before
shipment. The current reference instead places those same durations after
physical arrival at Muret, following the MRP rows for Division 1920 and the
user confirmation. F3 also modeled 28/33 working days at Gaillac, 7/10 calendar
days of transit to Avene/Gien, then 7/6 working days at receipt. The 7-day
693055 transit remains a hypothesis and is not reconciled with its 70-day FIA
reference; the 28/33-day duration has not been proven to be only a release.
`tau_process = 3` reste une convention de planification, pas une durée
physique de fabrication. Les jours fériés ne sont pas intégrés au calendrier
générique de réception ; les dates explicites des en-cours restent prioritaires.
Les transports usine–Muret sont effectivement de 2 jours, issus de l'arrondi
de 2,5 jours dans le graphe ; Muret–client utilise également 2 jours. Ces durées
ne sont pas des mesures industrielles. La fermeture d'Avène du 4 au 15 août
arrête la fabrication, sans suspendre automatiquement les autres opérations.

Ordre proposé, avec un témoin conservé et un essai annuel par changement :

1. Corriger les défauts établis : prorata initial 5/7, date de commande exportée
   et distinction des dates d'arrivée physique et de disponibilité dans les plans.
2. Compléter les états/circuits absents : 007923/Gien, 001893 et 002612/Gaillac,
   avec une provenance explicite pour les conditions d'approvisionnement.
3. Reprendre les six couples exclus du rapprochement observé à cause d'un I
   positif ; préserver le mouvement signé sans l'assimiler arbitrairement à un
   achat brut. Séparer besoins propres et usages complémentaires sans double compte.
4. Revoir les besoins nets à Gaillac et leurs dates : besoins aval propagés,
   usages locaux, stocks utilisables, libérations futures, en-cours et transports.
   Clarifier les délais hypothétiques avant de modifier les stocks de sécurité.
5. Tester une règle commune de regroupement et de replanification : même calcul
   de besoin net, paramètres par route et article, engagements conservés une
   seule fois. Comparer quantités, dates, stocks, manques et service aval sur
   toutes les paires ; une amélioration isolée ne suffit pas à adopter la règle.

Le rejeu F3 utilise des mouvements observés pour expliquer les écarts ; il ne
faut pas présenter cette alimentation rétrospective comme une prévision autonome.
Les futurs essais prédictifs devront utiliser seulement les prévisions et
engagements connus à leur date de décision.

### Corrections amont du 9 octobre : première période et cadence des campagnes

La [comparaison des essais](../resultats/amont_corrections_20261009/comparaison_amont.html)
conserve la présentation acceptée : mêmes trente couples, stocks sources
inchangés, mouvements et cellules d'origine, décisions et prévisions datées.
Elle compare F3 aux essais annuels terminés, sur les 362 jours du 1er janvier
au 28 décembre 2025. Les sorties sont locales ; la référence demande/client
n'est pas remplacée.

**G1 — corriger une quantité et une date erronées, sans nouveau réglage MRP.**
Les mouvements du 1er au 5 janvier sont déjà des quantités pour cette période.
Sur les quinze bilans initiaux contrôlés, quatorze ferment avec leurs quantités
intégrales, aucun avec le prorata 5/7 précédemment utilisé. L'exception de
002612 à Gaillac reste identifiée comme écart source. L'essai rétablit les
quantités intégrales pour les dix séries I initiales déjà représentées
(trois non nulles) et les sept budgets J initiaux du périmètre F3. Il conserve
les stocks de départ et la BOM ; il n'invente aucune réception.

Dans `mrp_orders_daily.csv`, `order_decision_day` désigne désormais la décision
effectivement enregistrée ; la décision originale d'un en-cours initial reste
inconnue. `order_date_imt` est un alias de `release_day`, pas une date reconstruite
en retirant un délai à la disponibilité. L'arrivée physique et la disponibilité
restent deux autres dates. Cette correction d'export ne change pas les flux.

G1 a été resimulé et contrôlé : écart moyen de stock de 007923/Avène ramené
de 8 672 à 7 936 kg, de 001848/Avène de 1 866 à 1 785 kg ; cinq couples
s'améliorent, quatre se dégradent légèrement, vingt sont inchangés et
007923/Gien reste non représenté. Stocks Muret, production PF et service client
sont identiques à F3. Les détails et dégradations figurent dans le
[bilan indépendant G1](../artifacts/testing/amont_corrections_20261009/validation/qualification_G1_review.json).
L'oracle indépendant passe 1 266 344 contrôles. La qualification native demeure
refusée sur les deux contrats des consommations résiduelles F3 qu'elle ne sait
pas relire (440 allocations et 347 journées), tous rapprochés indépendamment.
Ce refus n'est pas transformé en qualification globale réussie.

**Précision de capacité apportée par l'utilisateur.** Une grande quantité peut
être fabriquée dans la journée ; environ vingt lots peuvent être produits par
semaine si nécessaire. Le périmètre de ce plafond (usine, ligne ou ensemble)
reste à préciser. Le frein constaté dans le moteur est différent : il ne
termine qu'un lot par produit et par jour, même quand la campagne est déjà
engagée et dispose des matières. Dans F3, sept journées de 773474/Gaillac et
une de 693055/Gaillac présentent ce cas ; aucune à Avène/Gien avec leur capacité
finie. La [preuve de calcul](../artifacts/testing/amont_corrections_20261009/capacity_preanalysis.json)
identifie les lignes du registre. Une quantité produite n'est pas encore
utilisable tant que son contrôle/libération n'est pas terminé.

**G2 — plusieurs lots par jour dans une campagne déjà engagée.** L'essai a été
exécuté sur les mêmes 362 jours, en 18 min 15 s. La règle commune poursuit la
même campagne après un lot terminé, si les matières et la capacité du jour le
permettent. Chaque lot garde son identité et ses matières ; un travail inachevé
reste un en-cours. La capacité journalière est partagée avec les conditionnements
initiaux. La projection de fin de campagne suit également cette convention de
cadence ; il ne s'agit pas d'une modification d'exécution seulement.

L'option `production_intraday_policy = continue_engaged_campaign_v1` est active
dans G2 et inactive par défaut. Les plafonds existants comptent les lots engagés
par article/site, sur les tranches J0–6, J7–13, etc. : ils ne représentent pas une
capacité industrielle confirmée de vingt lots par semaine calendaire. Les
semaines sources des comparaisons restent lundi–dimanche. En l'absence de débit
industriel documenté, l'option teste la possibilité de finir une campagne dans
la journée ; ce n'est pas une mesure de capacité réelle. Les délais de contrôle,
de transport et les stocks de sécurité sont conservés.

Résultat : 773474/Gaillac peut effectivement terminer deux lots de 3 200 kg le
29 mai, deux le 4 août et six le 25 août. Le volume annuel reste **92 800 kg**,
et les productions hebdomadaires sont identiques à G1. Les écarts moyens de
stock aux photos hebdomadaires sont inchangés pour tous les couples comparables,
y compris les deux PF à Muret ; le service client et les productions PF sont
inchangés. La première libération différente est le 15 juillet : 6 400 kg au
lieu de 3 200 kg ce jour-là. La cadence corrige donc une limitation de simulation,
mais **aucun gain de calibration hebdomadaire n'est démontré**. Elle ne résout
pas le décrochage de mai à Gien.

Les trajectoires quotidiennes ne sont pas identiques : sept clôtures à Gaillac
changent, avec jusqu'à 16 000 kg supplémentaires de 773474 déjà fabriqué et
143 040 kg de 021081 consommés plus tôt (`16 000 × 8,94`, BOM conservée).
Ces déplacements restent à l'intérieur des mêmes semaines et ne changent
aucun des 1 213 rapprochements de mouvements ni des 1 540 photos contrôlés.

Les trente tests de calcul sélectionnés et le doctor ont réussi sur les sources
stabilisées. L'oracle G2 vérifie 1 297 280 assertions sans erreur : bilans,
matières par passage, capacité cumulée, en-cours, parents et libérations des lots.
Les 641 empreintes de qualification et 66 entrées de l'oracle restent identiques.
La qualification native et son agrégation demeurent refusées pour les mêmes
440 événements et 347 journées du contrat résiduel F3 ; aucune autre famille
ne présente d'échec. Le
[rapport indépendant G2](../artifacts/testing/amont_corrections_20261009/validation/qualification_G2_review.json)
conserve ces deux statuts séparément. Aucun contrôle navigateur n'a été relancé
après le refus d'accès déjà rencontré. Ces vérifications techniques ne prouvent
pas une calibration industrielle ni l'autonomie prévisionnelle du rejeu F3.

**Circuits encore incomplets.** Le rapprochement confirme un stock passif de
200,560 kg de 007923 à Gien, retiré par un ajustement source pendant la semaine
du 17 au 23 février ; il ne justifie pas un achat récurrent. Pour 001893 et
002612 à Gaillac, les cinq jours de réception sont documentés mais les offres
locales d'achat et la sécurité ne le sont pas. Les lots locaux candidats sont
950 kg (connu le 12 janvier) et 1 250 kg (connu le 5 janvier). Des délais de
56 et 35 jours pourraient être testés depuis les offres du même article à
Avène ; ce seraient des hypothèses de transfert, pas des faits Gaillac, et
aucune route Avène–Gaillac n'en découle. Les
[propositions sourcées](../artifacts/testing/amont_corrections_20261009/sources/proposals.json)
séparent ces hypothèses des données observées.

**773474 à Gien : une réception attendue dès le démarrage manque au carnet.**
Le premier plan du 5 janvier prévoit 6 400 kg à Gien dans la semaine MRP du
12 au 18 janvier (`Flow_Data_MRP_results.xlsx`, `Feuille1!H942`). Il prévoit
également une sortie de 6 400 kg de Gaillac dans la semaine du 5 au 11 janvier
(`I968`). Les mouvements physiques confirment une entrée de 6 400 kg à Gien
pendant la semaine du 13 au 19 janvier (`Flow_Data_Inventory_movements.xlsx`,
`G1238:J1238`) ; le stock passe de 13 566 à 16 773 kg, après consommation et
ajustement. L'écart résiduel du bilan source reste visible dans l'audit.

Le carnet initial de G1 provient d'`Extract_En_cours` : ce fichier contient un
OF de 3 200 kg à Gaillac (ligne 105), mais aucun transfert initial de 773474
vers Gien. Le moteur ne reprend donc pas H942. Le 5 janvier, il voit 14 593 kg
utilisables à Gien, une protection de 10 488 kg et aucun engagement en transit.
Son plan sur 52 semaines propose un premier départ le 22 janvier ; ce jour-là,
le besoin de 2 185 kg est arrondi à 3 200 kg, reçu physiquement le 1er février
et utilisable le 10 février. Le problème n'est pas l'absence de projection :
le calcul net reconstruit choisit une échéance plus tardive, sans cet engagement
initial pour la contraindre.

L'ancien essai isolé E2 avait repris H942 comme engagement initial : départ
de 6 400 kg le 8 janvier depuis le stock existant de Gaillac, arrivée le
18 janvier et disponibilité le 27 janvier. Cela démontre la faisabilité
physique de l'hypothèse, pas sa validité sur le modèle complet : E2 excluait
les productions PF. H est une entrée prévue, sans identifiant ni statut ferme.
Il faut donc tester une règle commune de reprise du carnet initial, en évitant
de compter deux fois les en-cours déjà connus, avant de l'adopter.

Le contre-exemple de 693055/Avène interdit une reprise aveugle de tous les H :
le plan prévoit 600 kg le 5–11 janvier et 600 kg le 19–25 janvier (H811/H813),
mais les mouvements ne donnent aucune entrée du 6 au 19 janvier, puis 1 190 kg
le 20–26 janvier (H1067). G1 reçoit déjà 600 kg le 15 janvier et 600 kg le
22 janvier. La quantité de janvier est proche ; le premier lot est trop tôt.
La [chronologie des deux circuits](../artifacts/testing/amont_corrections_20261009/map/initial_plan_gaps.json)
conserve les cellules sources. Pour 773474, les dix jours proviennent de
`268967.xlsx!FIA!F9`, dont l'en-tête F1 est « Délai prévisionnel de livraison
en jours », pas d'une mesure de transport. Le graphe les affecte actuellement
au transit camion ; cette interprétation reste à vérifier sans supprimer le
délai total annoncé. L'hypothèse E2 doit
donc aussi être confrontée à la date de sortie de Gaillac : un meilleur stock
à Gien ne suffit pas si la sortie amont devient trop précoce.

**Cadence et délai sont distincts.** Dans les conventions actuelles, un lot
de 773474 fabriqué le 29 mai est libéré le 15 juillet après 33 jours ouvrés,
reçu à Gien le 25 juillet après dix jours de transport, puis utilisable le
4 août après six jours ouvrés à réception. Accélérer sa fabrication ne suffit
pas à combler le stock manquant en mai. La signification des 33 jours à Gaillac
reste à vérifier ; ils ne sont pas supprimés pour rapprocher artificiellement
les courbes.

Enfin, prendre le maximum entre besoin industriel et besoin propre pour
chaque semaine peut retenir deux fois un besoin dont la date a changé. La
[lecture des plans](../artifacts/testing/amont_corrections_20261009/planning_overlap_preanalysis.json)
mesure cet effet potentiel, sans déclarer ces quantités supprimables. Un plan
est une projection à une date donnée ; additionner plusieurs versions du plan
ne donne pas une consommation annuelle. Aucun nouveau maximum hebdomadaire
ou cumulatif n'a été ajouté dans G1/G2.

### Relecture exhaustive du 11 octobre : 693055/Gaillac et 042342/Gien

L'[audit détaillé](../artifacts/testing/deep_693055_042342_20261011/bilan.md)
conserve les cellules et bilans de 106 photos, 77 lignes de mouvements et
2 280 lignes MRP locales. Les marqueurs des mouvements et des prévisions
restent distincts. Les absences de lignes ne sont pas remplacées par zéro.

- **042342 :** le standard de 30 000 000 UN vient de `268967.xlsx!FIA!G3:H3`,
  mais ne prouve pas un minimum/multiple obligatoire. Le coefficient actuel
  des autres usages, 46,386 %, provient d'une différence entre le premier I
  industriel et la théorie BOM, pas d'une proportion industrielle mesurée.
  Les en-cours de 60 millions annoncés pour janvier ne correspondent qu'à
  29,5 millions de H effectivement documenté avant le 17 mars ; les identités
  des commandes ne peuvent pas être reconstituées avec certitude.
- **693055 :** I1030 = −1 190 kg à Gaillac et H1067 = +1 190 kg à Avène,
  sur la semaine du 20 au 26 janvier. La version MRP du 19 janvier annonce
  déjà 1 190 kg en H2794. Le standard de fabrication de 600 kg n'impose donc
  pas une quantité de transfert universellement multiple de 600.
- Les 1 451 lignes MRP de 693055/Gaillac comportent 593 I explicitement nuls.
  Elles sont désormais toutes auditées, mais la série locale entière reste
  absente du branchement moteur, qui utilise les propositions d'Avène.
- Deux écarts source opposés restent présents en juin pour chaque matière :
  +600 / −600 kg à Gaillac et −1 625 000 / +1 625 000 UN à Gien. Leur
  compensation ne valide pas chaque semaine. Les différences entre J MRP
  et photo physique ne sont pas assimilées à une disponibilité connue.

Aucun classeur ni paramètre source n'a été corrigé pour rapprocher les courbes.

### 693055/Gaillac — rapprochement du 12 octobre 2026

Le [dossier E1/E2](../artifacts/testing/gaillac_693055_20261012/bilan.md)
sépare désormais arrondi de commande et quantité physiquement transférable.
Les 600 kg de commande restent une hypothèse : la FIA indique 1 g. Les
846 positions futures positives d'Avène sont des apparitions dans des plans
successifs, pas 846 commandes différentes.

Le premier plan connu distingue 590 kg disponibles immédiatement et 1 200 kg
déjà présents, disponibles le 12 janvier, pour 1 800 kg de photo physique.
Les 10 kg restants sont conservés hors disponible MRP avec statut inconnu ;
ils ne sont assimilés ni à une perte ni à un blocage qualité documenté.

Au dernier trimestre, les 13 plans de Gaillac ont un J futur nul. Les photos
moyennes valent 148 kg, dont 138 kg de J courant et 10 kg hors J. Les bilans
fermés des semaines du 3 novembre, du 1er et du 8 décembre imposent chacun
qu'au moins 590 kg nouvellement entrés ressortent dans la même semaine.
Cela ne permet pas de dater la fabrication d'un lot, mais contredit une
attente systématique de 28 jours ouvrés après chacune de ces entrées.
Les cellules et contre-calculs sont conservés dans l'oracle du dernier
trimestre du dossier E1/E2 ; les données sources ne sont pas modifiées.

### Delai de disponibilite des PF deplace a Muret - 20 octobre 2026

Les durees restent celles de `Flow_Data_MRP_results.xlsx / Feuille1` : 10
jours ouvres pour `268091` (cellule source E545) et 15 jours ouvres pour
`268967` (E593). L'utilisateur a confirme que le controle/liberation des
produits finis se fait a Muret. Le moteur compte donc ces jours apres l'arrivee
physique au depot : le stock est d'abord present mais retenu, puis cette meme
quantite devient disponible. Le transport usine-Muret reste une etape distincte
et inchangee. Cette regle applique le delai MRP a la disponibilite ; elle ne
pretend pas disposer de l'historique date des controles de lots industriels.
