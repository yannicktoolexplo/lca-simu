# Expériences MRP 2025 — archive de travail

Ce document conserve la chronologie des analyses, essais, hypothèses et
contre-exemples qui ont conduit à la référence actuelle. Il ne décrit pas le
système nominal à exécuter. Les liens vers d'anciens dossiers sous
`artifacts/testing` indiquent leur emplacement historique ; ces artefacts
volumineux peuvent avoir été supprimés après consolidation. Les règles actives
et la commande de reproduction sont dans
[`../REGLES_MRP.md`](../REGLES_MRP.md).

# Anciennes règles MRP et chronologie des essais

**Projection sur cinq ans — candidat du 14 octobre 2026.**
La référence `source_priority` reste disponible et reste le choix par défaut.
L'option `coherent_scenario` teste une prévision future cohérente avec le
scénario de demande exécuté. Elle ne constitue pas une nouvelle règle
industrielle démontrée. Les résultats et le statut de qualification figurent
dans le [bilan de correction](../artifacts/testing/corrections_5ans_20261014/bilan.md).

- Jusqu'au 31 décembre 2025 inclus, les décisions conservent les mêmes
  données et prévisions que le précédent calcul sur cinq ans.
- Le scénario est publié le 1er janvier 2026 ; il concerne les besoins du
  5 janvier 2026 et suivants, sans réviser la semaine client déjà commencée.
- `Prévision client future = demande de la même semaine du profil 2025 ×
  1,05^cycle`. Le cycle fait 52 semaines, soit 364 jours. C'est une hypothèse
  prospective connue, pas une observation de ventes futures.
- `Prévision des autres usages = quantités demandées dans W pour la même
  semaine × 1,05^cycle`. On conserve la demande, même quand elle n'a pas pu
  être servie ; une rupture ne diminue donc pas artificiellement le besoin.
- `Besoin matière futur = BOM des fabrications planifiées + autres usages
  prospectifs + réserves`, chacun compté une seule fois. Les anciens totaux I
  ne remplacent plus cette somme après la bascule. Les engagements fermes,
  stocks disponibles, sécurités et délais continuent à entrer dans le calcul
  du besoin net selon les règles existantes.

Les demandes physiques, BOM, stocks initiaux, encours, sécurités et capacités
ne changent pas entre ces deux calculs. Le candidat connaît son propre profil
de demande future : une amélioration mesure l'effet de cette cohérence, et
ne valide ni la précision des prévisions industrielles ni la calibration du
MRP. Le détail des décisions MRP est désormais exporté chaque dimanche sur
toute la durée du calcul, au lieu de s'arrêter après 2025.

**Comparaison client.** Le constructeur de carte charge désormais directement
`demand_PF.xlsx` et le fichier de CA livré/perdu. Les trois quantités sont :
demande client source ; réponse réelle **estimée** par
`demande × CA livré / (CA livré + CA perdu)` ; service physique calculé par le
simulateur après transport. L'estimation suppose prix et périmètre communs.
Une semaine inconnue reste absente ; l'historique Flow ne remplace plus
silencieusement une demande source manquante. Les deux suivis de lots sont
conservés.

**693055 — contrat de délai non couvert, confirmé le 13 octobre 2026.**
`268091.xlsx / FIA!F22` annonce 70 jours d'approvisionnement auprès de Gaillac.
Cette valeur est conservée dans le graphe, mais les huit essais B/W/WT3/WT1/
S2/S3/S2A/WS3 ne l'appliquent pas comme délai effectif : le calendrier utilise
le transport hypothétique et les étapes de disponibilité séparées. La marge
de planification de 3 jours et les 28 jours ouvrés à Gaillac ne démontrent pas
le respect des 70 jours. Le contrat doit être réconcilié depuis la décision
d'approvisionnement, sans transformer 70 en durée de camion ni additionner
automatiquement 70 et 28. Voir le [constat source et moteur](../artifacts/testing/gaillac_70j_20261013/bilan.md).
Aucune nouvelle règle de délai n'est encore appliquée par cet audit.

**Corrections de la chaîne — G1/G2, 12 octobre 2026.**
Ces deux essais de 2025 repartent d'E2 ; E2 et R5 sont conservés. Le
[bilan des corrections](../artifacts/testing/chaine_corrections_20261012/bilan.md)
doit être consulté avant de choisir une nouvelle référence.

**Résultat : pas de promotion de G1/G2.** Les deux simulations annuelles
ont été exécutées. Les engagements sans premier travail sont corrigés,
mais les écarts moyens de 693055/Gaillac (888 kg, 80,3 %) et
773474/Gien (5 761 kg, 33,4 %) restent inchangés. L'écart de 021081/Gaillac
passe de 16,5 % à 7,3 % seulement dans G2, qui rejoue les réceptions
historiques initiales ; ce gain ne valide pas un MRP autonome.
La demande et les livraisons clients simulées restent identiques à E2.

- **Début de fabrication (G1 et G2).** Une autorisation sans matière
  exécutable ne crée plus de campagne ferme ni de débit du quota de lots.
  `première quantité exécutable = min(quantité autorisée, capacité disponible,
  quantité permise par chaque composant)` après arrondi physique des UN.
  Si cette quantité est nulle, l'autorisation reste révisable. Dès le premier
  travail physique positif, le reste de la campagne devient ferme ; une
  campagne commencée n'est pas annulée. C'est la convention du modèle,
  pas une preuve du statut administratif des OF industriels.
- **Stock initial de 021081 à Gaillac (G1 et G2).** Les 1 142 100 kg
  physiques au 1er janvier sont conservés ; 379 880 kg sont déjà sur site
  mais indisponibles jusqu'au 12 janvier, d'après le premier plan MRP
  (`Feuille1!J278`). Il reste donc 762 220 kg immédiatement utilisables.
  Le plan du 5 janvier et la photo du 6 janvier totalisent 1 132 192 kg ;
  leur différence de date de 9 908 kg avec l'ouverture n'est pas effacée.
  Cette utilisation du premier plan à l'ouverture reste une hypothèse
  rétrospective déclarée. La libération n'est pas une nouvelle réception.
- **Réceptions initiales (G2 seulement).** La date promise d'une commande
  n'est plus exécutée comme une réception certaine dans ce rejeu historique.
  Le MRP conserve la promesse et sa quantité non reçue. Les entrées réalisées
  ne deviennent connues qu'à la clôture de leur semaine source ; elles sont
  affectées FIFO aux commandes initiales, sans création d'une seconde commande.
  `reste engagé = quantité initiale − quantité effectivement reçue`.
  Ce FIFO ne retrouve pas les identifiants industriels. Le périmètre est
  exclusivement les 23 achats initiaux de 021081 à Gaillac : 1 320 000 kg
  engagés, 1 319 640 kg reçus dans la source, 360 kg encore engagés.
  Le traitement de 75 jours ouvrés repart de la réception physique dans
  cet essai : c'est une convention testée, pas une date de libération retrouvée.
  Les futures entrées réalisées ne sont jamais fournies à la planification.

Le rejeu G2 ne valide pas un MRP autonome. La cellule source H393 garde son
écart de bilan de 2 270 kg ; elle n'est pas corrigée arbitrairement. Les
autres usages reconstitués F3/E4 restent actifs comme dans E2, désormais
déclarés dans le résumé via `effective_runtime_rules` : le maximum entre
besoin BOM et besoin industriel connu concerne neuf couples article/site,
et dix couples ont des consommations historiques complémentaires.
La demande client validée, les BOM, stocks de sécurité, transports,
lots et délais de 28/33 jours de Gaillac restent inchangés. Les quantités
UN exécutées restent entières. Le placement physique de ces 28/33 jours
n'est pas résolu par ces deux corrections.

**Coordination Gaillac–Avène — essai du 12 octobre 2026.**
La règle candidate de révision de la semaine courante utilise la dernière
prévision industrielle déjà connue au jour du calcul. Pour une semaine
explicitement renseignée, le besoin encore futur vaut :

`prévision hebdomadaire connue × nombre de jours futurs couverts / 7`.

Elle ne réécrit ni les consommations exécutées ni les jours passés. Une
semaine absente garde la politique de repli déclarée ; un zéro explicite
reste un zéro. Les engagements de fabrication et les réceptions déjà en
transit restent déduits une seule fois. L'essai F1 est limité à 693055/Avène,
sur la base E2, pour mesurer séparément cette correction de prévision.
L'option antérieure reste disponible pour reproduire les références.

Exemple contrôlable : le plan du 13 juillet annonce 270 kg pour sa semaine,
contre 380 kg dans le plan précédent. Pour les six jours futurs, retenir
`270 × 6/7 = 231 kg` plutôt que `380 × 6/7 = 326 kg` (arrondis pour lecture).
Ce besoin prévisionnel ne constitue pas une consommation physique ajoutée.

Les délais, jours de sécurité, lots de fabrication, demande client et BOM
ne changent pas dans cet essai. Les 28 jours de Gaillac restent appliqués
selon la convention antérieure, dont le positionnement physique n'est pas
encore établi. Les [résultats et contrôles de F1](../artifacts/testing/gaillac_coordination_20261012/bilan.md)
ne justifient pas une nouvelle référence : l'écart moyen de Gaillac passe de
888 à 877 kg, mais celui d'Avène de 557 à 600 kg. Le stock moyen des deux
sites et du transit augmente de 51 kg ; les 22 lots fabriqués restent inchangés.
F1 reste optionnel, sans remplacer E2 ni la référence historique R5.

**693055 — séparation commande/transfert et initialisation, 12 octobre 2026.**
Les essais E1/E2 complètent D1 ci-dessous ; ils ne remplacent pas R5 comme
référence de calibration. Le [bilan et les contrôles](../artifacts/testing/gaillac_693055_20261012/bilan.md)
conservent la comparaison aux 52 photos des deux sites.

- Une nouvelle proposition MRP peut avoir son propre arrondi :
  `commande = plafond(besoin net protégé / multiple de commande) × multiple`.
  Les stocks et réceptions déjà engagées sont déduits avant cet arrondi.
  `order_multiple_qty` est distinct du quantum de départ physique. Sans ce
  paramètre optionnel, le comportement antérieur est conservé.
- Pour ces essais 693055, commande et fabrication gardent 600 kg, tandis
  qu'un départ peut être de 590 ou 1 190 kg. Le multiple de commande de 600 kg
  est une hypothèse soutenue par les projections MRP, pas le standard FIA
  (1 g). Les limites de stock, de réservation et de transport restent actives.
- À l'ouverture E2 : `1 800 kg physiques = 590 disponibles + 1 200 à date
  connue + 10 hors MRP`. Les 1 200 kg conservent leur disponibilité du
  12 janvier. Les 10 kg restent physiquement présents, de statut inconnu,
  sans date de libération inventée. Cette initialisation utilise le premier
  plan connu selon la convention rétrospective déjà déclarée.
- Le délai source de 28 jours ouvrés reste conservé. Son application
  **après chaque nouvelle entrée physique** est toutefois une hypothèse
  du moteur : trois semaines sources exigent qu'au moins 590 kg entrés
  repartent dans la même semaine. Le jalon industriel de l'entrée reste
  à identifier avant de modifier les étapes physiques.

E1 retrouve exactement les stocks 693055 de R5. E2 donne un écart moyen de
**888 kg à Gaillac et 557 kg à Avène**, contre **887 et 564 kg** dans R5.
L'initialisation et la séparation des quantités sont corrigées dans l'essai,
mais le surstock principal de Gaillac n'est pas résolu. Les productions PF,
stocks de Muret et livraisons clients des deux produits restent identiques.

**Gaillac — corrections et essais séparés du 12 octobre 2026.**
Les paramètres et résultats antérieurs restent disponibles. D1 repart de C1 ;
D2 ajoute uniquement le calendrier de réception/libération de Gaillac.
Le [bilan de cette passe](../artifacts/testing/gaillac_corrections_20261012/bilan.md)
précise les essais réellement exécutés, leurs écarts et leur qualification.

1. **Fabriquer et transférer ont des tailles différentes.** Pour 693055,
   `fabrication = plafond(besoin / 600 kg) × 600 kg`, mais
   `transfert = min(besoin à expédier, stock utilisable libre)`.
   Les réservations, engagements et capacités de transport continuent de
   borner le départ. Le transfert réel de 1 190 kg confirme qu'un quantum
   obligatoire de 600 kg n'est pas justifié. D1 enlève ce quantum uniquement
   sur Gaillac–Avène ; la taille de fabrication reste 600 kg.
2. **Ne pas compter deux fois une consommation décalée entre semaines.**
   Pour les couples déclarés par C1,
   `complément = max(0, sorties Scan3 cumulées connues − BOM déjà consommée
   sur les semaines couvertes − compléments déjà demandés)`.
   Les compléments déjà demandés incluent ceux encore en retard. Une semaine
   absente n'est pas un zéro ; une consommation physique n'est jamais annulée.
   C'est un rapprochement historique des usages, pas une prévision autonome
   des autres formats. Les données futures réalisées ne pilotent pas le MRP.
3. **Séparer date physique et disponibilité.**
   `disponibilité = ajouter les jours de traitement à la date physique`.
   Le jour physique est exclu du décompte ; un délai nul garde cette date.
   D2 compte lundi–vendredi hors dates explicitement fermées à Gaillac :
   fériés nationaux 2025/2026 et fermeture du 4 au 15 août 2025, cette dernière
   restant une hypothèse pour Gaillac. Les nouveaux achats, les libérations
   des nouveaux lots fabriqués et leur anticipation MRP utilisent le même
   calendrier. Une date non déclarée n'est pas automatiquement reportée l'année
   suivante. Les délais sources 5/75/28/33 jours ne sont pas diminués.
4. **Conserver les engagements initiaux.** Les dates G/I d'`Extract_En_cours`
   ne reçoivent pas un deuxième délai. La replanification de certaines promesses
   d'achat, déjà déclarée dans la référence, reste une règle distincte. Les deux
   OF initiaux Gaillac gardent leurs dates explicites. La sécurité, `tau_process`,
   la demande, la BOM, les délais physiques des trajets et les capacités ne sont
   pas modifiés par le calendrier de réception.
5. **Ne pas confondre encours et stock fini.** L'hypothèse de sept jours avant
   l'entrée physique, puis 21/26 jours après, n'est pas démontrée par les sources.
   Un diagnostic conserve la disponibilité totale de 28/33 jours et rapproche
   `stock physique + encours` avant/après. Il ne constitue ni un nouveau calcul
   MRP ni une amélioration des livraisons. Aucun timer de fabrication n'est
   introduit dans le moteur sur cette seule base.

001893/002612 à Gaillac restent des articles de stockage/redistribution :
leurs cinq jours de réception sont connus, leurs destinations sortantes ne
le sont pas. Aucune liaison sortante supplémentaire n'est inventée.

**Gaillac, site mixte — configuration H1 du 10 octobre 2026.**
Un article acheté et stocké n'a pas besoin d'une BOM pour être réapprovisionné.
Le rôle s'applique au couple article/site : Gaillac fabrique 773474/693055,
consomme 021081 et peut acheter, détenir puis distribuer d'autres matières.
Changer tout le site en centre de distribution supprimerait cette distinction.

Dans la configuration H1, les stocks 001893 et 002612 passent de
`unconfigured` à `configured_candidate` dans `managed_inventory_pairs`.
Le calcul utilise leurs prévisions I locales connues à chaque date, le stock
utilisable, les réceptions déjà engagées, le délai fournisseur et les 5 jours
ouvrés de traitement locaux. Il commande en multiples candidats de 950 et
1 250 kg, puis enregistre réception physique, disponibilité et sortie distinctement.
Aucune fabrication fictive ni consommation BOM n'est créée pour ces articles.

Les fournisseurs et délais de 56/35 jours sont repris des offres du même
article à Avène : leur application à Gaillac reste une hypothèse explicite.
La sécurité locale n'est pas documentée ; H1 teste zéro protection additionnelle,
sans modifier les sécurités sources des autres couples. Les sorties industrielles
existantes gardent une destination inconnue : elles ne justifient pas une liaison
Gaillac–Avène inventée, ni un double prélèvement comme transfert et consommation.

Une seule réception initiale de 1 250 kg de 002612 est ajoutée depuis le premier
MRP, distincte du stock déjà présent. Les autres entrées H futures restent des
prévisions, pas des commandes fermes injectées. Le graphe, les hypothèses et la
commande de reproduction sont conservés dans
`artifacts/testing/gaillac_hub_20261010` ; les résultats et l'adoption sont à lire
dans les preuves de cette exécution, pas à déduire de cette configuration.

**Carnet initial — correction et essais du 10 octobre 2026.**
`Extract_En_cours` sert à représenter ce qui était déjà prévu au démarrage,
pas à imposer les événements effectivement réalisés pendant toute l'année.
Une commande du carnet peut arriver en mai : ne pas la supprimer parce que
sa livraison dépasse janvier. Ne pas la sélectionner non plus selon sa
confirmation dans un historique futur. Le premier MRP corrobore le carnet,
mais ne fournit pas les dates réelles de création ni les statuts matière.

La règle est : **reprendre une fois le carnet initial ; compter ses
réceptions prévues dans le calcul du besoin net ; distinguer ces prévisions
de leur exécution ; laisser ensuite le MRP produire les nouveaux ordres.**
Les fabrications initiales doivent porter un état matière distinct : déjà
prélevée, à prélever ou inconnu. Le mode par défaut considère les O.Proc
comme déjà prélevées hors emballages ; cette hypothèse n'est pas établie par
la source. Le mode expérimental `opening_production_material_policy` permet
de sélectionner des ordres sources comme « matières à prélever » : chacun
attend toute sa BOM et sa capacité, puis consomme et produit une seule fois.
Il remplace leur réception inconditionnelle ; il ne s'y ajoute pas. Si la
fabrication est retardée, la durée G→I en jours lundi–vendredi est conservée.
Un stock déjà sur site mais disponible plus tard reste du stock
initial, jamais une nouvelle réception. Les propositions MRP connues après
J0 entrent à leur date de connaissance ; toute reprise rétrospective doit
rester une hypothèse explicite. Le [bilan de l'extrait](../artifacts/testing/extract_en_cours_audit_20261010/bilan.md)
sépare faits et hypothèses. Les achats initiaux conservent maintenant leur
fournisseur exact ; une route absente est signalée, sans substitution par
un autre fournisseur. La date de création reste inconnue. G5 isole cette
correction ; G6 teste le statut matière des deux OF de Gaillac. G7 remplace
seulement les réceptions de 021081 par un calendrier historique explicite :
il utilise le futur et ne prouve pas une règle prédictive.
Voir le [bilan des corrections et contrôles](../artifacts/testing/extract_corrections_20261010/bilan.md).
**G2 est conservé ; les hypothèses ne deviennent pas automatiquement nominales.**

**Sécurité locale — essai G8, distinct de G6 et G7.** La politique facultative
`local_safety_forecast_policy` distingue l'assiette de sécurité des nouveaux
besoins nets :

```text
sécurité(t) = max(sécurité fixe source,
                 sorties prévues dans ]t ; t + jours de sécurité ouvrés])
besoin net(t) = max(0, besoins à servir(t) + sécurité(t)
                      − stock projeté avec engagements déjà comptés)
```

Elle s'applique aux sorties fabriquées ayant des jours de sécurité locaux
documentés et un calendrier I local : seule 773474/Gaillac satisfait ces
conditions dans les données actuelles. Le dernier plan connu sert uniquement
au calcul de sécurité ; ses sorties ne sont pas ajoutées aux consommations
ni aux besoins nets. Une période documentée à zéro reste zéro. Une période
absente conserve le signal de besoins du réseau ; une version future ne peut
pas être utilisée plus tôt. La convention de semaine courante figée reste active.
La protection suit aussi les recalculs après exécution. Aucun H n'est injecté,
aucun jour de sécurité n'est augmenté. Cette variante est guidée par les
prévisions industrielles, pas une reconstitution autonome de l'ERP. Son
acceptation dépend des résultats et contrôles consignés dans le bilan.

**Diagnostic Gaillac du 10 octobre — règles à tester, pas encore adoptées.**
Le [bilan chiffré](../artifacts/testing/gaillac_diagnostic_20261010/bilan.md)
montre que les arrivées promises de 021081 ne sont pas toutes exécutées aux
dates initiales, que les besoins locaux de 773474 persistent quand nos
nouvelles commandes nettes disparaissent, et que les 28 JO de 693055 ne
peuvent pas être systématiquement placés après les entrées physiques décrites
par trois bilans industriels. La référence G2 et les règles exécutées sont
conservées ; aucune correction du délai ou de la BOM n'est appliquée ici.

L'essai de protection G8 distingue **besoins bruts datés**,
**engagements existants** et **nouveaux ordres nets**. Un programme proche
maintenu doit remplacer des propositions futures, pas s'y additionner.
Une sécurité absente (693055/Gaillac) ne doit pas être présentée comme un
zéro industriel confirmé. Enfin, `dated_protection_target_qty` est le maximum
sur l'horizon ; pour la cible courante, lire `prospective_safety_tomorrow_qty`
ou `source_safety_target_qty`. Les 12 427 kg cités dans le diagnostic antérieur
ne sont donc pas la cible courante du 17 mars, qui vaut 6 879 kg.

**Référence amont acceptée le 9 octobre 2026 : G2.**
La [comparaison amont](../resultats/amont_corrections_20261009/comparaison_amont.html)
est le point de départ des essais suivants. Elle conserve la demande client,
les BOM, les sécurités et les délais précédents. Deux corrections sont acquises
dans ce parcours : les mouvements du 1er au 5 janvier sont comptés en entier,
et plusieurs lots d'une campagne déjà engagée peuvent être fabriqués dans la
journée si les matières et la capacité le permettent. Le nombre de lots
autorisés n'est pas augmenté arbitrairement.

### Suite amont du 9 octobre : règles et conditions des essais

| Règle | Calcul simple et conditions | Statut |
|---|---|---|
| Reprendre un transfert prévu au démarrage | Au premier plan connu, sur une liaison interne unique compatible, rechercher une réception future compatible avec le premier départ autorisé. `quantité nouvelle = max(0, réception prévue − engagements déjà présents)`. Elle doit être couverte intégralement par les sorties prévues à l'origine, son stock disponible source et son stock utilisable simulé. | Essai G3 ; un programme prévu n'est pas une preuve de commande ferme. |
| Ne compter chaque engagement qu'une fois | Déduire les ordres existants dans la même liaison et la même semaine physique ; partager le budget de sortie et le stock de l'origine entre les destinations. Un engagement transféré à une expédition ne reste pas une deuxième réception future. | Contrat de G3, vérifié par des cas en mémoire et un oracle indépendant. |
| Distinguer attente et transport | `délai de livraison L = attente sur site W + transport T`. Essai : `T = min(2, L)` jours calendaires et `W = L − T`. La date d'arrivée reste inchangée ; pendant W, les lots sont réservés mais physiquement à l'origine. | Hypothèse G4, limitée aux liaisons internes de semi-finis fabriqués vers l'entrée d'usine. Deux jours ne sont pas une durée industrielle mesurée. |
| Séparer arrivée et disponibilité | `disponibilité = arrivée + traitement à réception`, selon lundi–vendredi. Les dates explicites des en-cours priment sur un recalcul avec un délai générique. | Convention conservée. À Gaillac, le placement du délai de traitement après la fabrication reste à confirmer. |
| Comparer une seule version MRP connue | Choisir d'abord le dernier plan publié à la date étudiée, puis sa semaine cible. Une semaine omise reste inconnue ; ne pas reprendre silencieusement une ancienne valeur. | Règle de l'audit des prévisions ; aucune réduction des besoins n'est déduite du rapport prévu/réalisé. |

La nouvelle règle de transferts G3 ne lit le premier plan qu'à sa date de
connaissance, le 5 janvier. L'initialisation héritée conserve séparément des
hypothèses rétrospectives déclarées pour le stock indisponible et deux achats
de 001848/Gien ; cette causalité n'est donc pas générale à tout G3. Pour 773474,
les cellules `Flow_Data_MRP_results!Feuille1!H942`, `I968` et `J968`
recoupent 6 400 kg. La règle ne crée pas de stock. Elle ne sélectionne rien
pour 693055 dans la première semaine de réception future atteignable.
Les dates de création industrielles restent inconnues ; la date d'adoption
du programme, la réservation simulée et le départ physique sont distincts.

Ces essais restent comparés à G2 ; leur implémentation ne vaut pas adoption.
Leurs résultats et contrôles sont conservés sous
`artifacts/testing/amont_suite_20261009`. Le nominal historique, la référence
client et les anciennes comparaisons sont conservés.

**Résultat G3 sur 2025.** L'erreur absolue moyenne de stock de 773474 passe
de 5 600 à 5 294 kg à Gien et de 5 723 à 5 538 kg à Gaillac, sur les mêmes
52 photos. Les deux transferts de 3 200 kg des 22 et 29 janvier deviennent
un transfert de 6 400 kg le 8 janvier. Le volume annuel reste 76 800 kg.
Les autres stocks représentés, les productions de PF, le service client et
les consommations complémentaires reconstituées restent inchangés.
Cette amélioration moyenne conserve des écarts ponctuels, dont un départ
trop précoce par rapport à la photo du 13 janvier à Gaillac. Voir la
[contre-vérification](../artifacts/testing/amont_suite_20261009/validation/qualification_G3_review.json).
Le contrôle natif reste refusé sur le contrat des consommations complémentaires
F3, contrôlées séparément ; ce résultat ne vaut pas qualification globale.

**Résultat G4 sur 2025.** Conserver le stock réservé à Gaillac jusqu'au départ
physique réduit l'erreur moyenne de 773474 de 5 538 à 4 800 kg, mais augmente
celle de 693055 de 887 à 1 012 kg. Les arrivées, les disponibilités, les
productions de PF et les livraisons clients restent identiques à G3.
L'hypothèse de deux jours de transport n'est donc pas adoptée comme règle
industrielle commune. Pour 693055, les sept jours appliqués dans G3 restent
distincts des 70 jours de référence FIA ; G4 conserve cette convention sans
prétendre l'expliquer. Un transfert de 600 kg reste réservé à la clôture du
28 décembre, son départ étant prévu le 29 : il n'est pas compté comme expédié.
Le [bilan complet](../artifacts/testing/amont_suite_20261009/bilan.md) et la
[comparaison interactive](../resultats/amont_suite_20261009/comparaison_amont.html)
présentent les trois scénarios. **G2 reste la référence acceptée.**

**Limite du rapprochement des consommations hérité de F3.** Sur les semaines
documentées, `complément = max(0, sorties Scan3 − consommation BOM simulée)`.
Les autres sorties de la colonne I s'ajoutent séparément. Ce complément aide
à expliquer le stock historique ; il ne mesure ni la demande d'autres
formats, ni une demande autonome. Si la production simulée change, le
complément peut changer en sens inverse. Les comparaisons G3/G4 doivent donc
contrôler aussi cette série, et pas seulement l'écart de stock.
Pour un futur scénario d'incident, il faudra une demande complémentaire
indépendante, ou une série estimée explicitement figée à partir de la référence.
Les besoins MRP prévus ne doivent pas être remplacés automatiquement par les
consommations finalement réalisées.

**Référence acceptée — demande client et centre de distribution, 8 octobre 2026.**
Décision utilisateur : conserver le résultat `demand_pf_20261008` comme point
de départ sur ce périmètre. Le [registre](reference/mrp_current.json) identifie
le scénario exécuté sur 362 jours, le HTML et leurs empreintes. Un instantané
compressé conserve le graphe exact, la comparaison autonome, la commande
d'exécution et les preuves. Cette adoption conserve explicitement la nature
**estimée** de la réponse industrielle et les quatre semaines non estimables.
Elle ne signifie pas que tous les stocks amont sont calibrés.

**Sorties d'usines reconstituées — comparaison ajoutée le 8 octobre.**
L'[onglet Usines → Muret](../resultats/factory_dispatch_20261008/comparaison.html)
compare les deux PF sans changer cette référence client ni les règles du moteur.
La reconstitution utilise `entrées Muret estimées = stock lundi suivant − stock
lundi + historique Flow − Divers`, sous l'hypothèse explicite que cet historique
représente les sorties clients. La colonne I des mouvements, qui contient un
solde net, n'est pas utilisée comme livraison brute.
Les volumes sont attribués à une fenêtre de départ estimée en reculant les
bornes de réception du délai retenu ; les départs simulés `lane_ship` de l'usine
vers Muret sont sommés sur exactement cette fenêtre. Le décalage initial de
deux jours correspond aux dates exécutées dans les simulations, pas à une
mesure du transport industriel ; il est modifiable dans l'affichage.
Une valeur négative reconstituée signale une incohérence : elle reste dans le
tableau de calcul et interrompt la courbe, sans devenir zéro. Les dates exactes
des départs industriels et leur fréquence dans la semaine restent inconnues.

**Comparaison client — affichage rectifié le 8 octobre.** Le premier graphique
affiche la demande `demand_PF!Demande/E` utilisée par l'essai et les quantités
effectivement servies aux clients dans la simulation (`served_qty`). Il ne
remplace pas le service client par les départs simulés du dépôt.
La correction des quatre demandes négatives de Permixon à zéro reste une
hypothèse de cet essai, explicitement indiquée, pas une mesure industrielle.

Après la précision utilisateur demandant de croiser demande, sorties et CA
perdu, la troisième courbe est une **réponse réelle estimée**, explicitement
distincte d'un comptage des livraisons :
`livré estimé = demande PF × CA livré / (CA livré + CA perdu)`.
Cette formule suppose mêmes périmètres et même prix moyen pour les quantités
livrées et non livrées. Le complément donne le non-livré estimé. Aucun prix
client n'est inventé. Les quatre semaines de demande PF nulle avec du CA
positif restent inconnues, pas zéro, et interrompent la courbe Permixon.

Un tableau rapproche ces valeurs avec la colonne I signée des mouvements
de Muret et le service simulé. Cette colonne n'est pas transformée en livraison
brute : elle contient aussi des mouvements positifs et se rapproche des
variations nettes de stock. La nature de `Actual Demand` (commandes ou ventes)
reste à confirmer ; la série n'est pas renommée en livraison mesurée.
Le CA reste aussi consultable séparément, sans comparaison de son taux avec
le quotient hebdomadaire des unités simulées. Les références historiques
93 % / 80 % n'ont pas de définition suffisamment établie pour ce rapprochement.

Le second graphique compare les **besoins prévus** : colonne I du plan MRP
industriel et besoins projetés par la simulation au même jour, pour le PF à
Muret. Le choix de version est indépendant du site sélectionné ailleurs.
Les semaines de projection suivent la convention dimanche–samedi existante ;
les quantités clients sont agrégées lundi–dimanche. Les entrées prévues et les
stocks projetés restent dans l'onglet MRP. Aucun plan n'est une livraison exécutée.
La simulation n'est pas recalculée pour cette correction d'affichage.
La [vérification indépendante de l'affichage précédent](../artifacts/testing/demand_pf_20261008/quantity_view_validation.json)
rapproche 17 711 contrôles sans erreur : demande, service et besoins MRP des
deux produits avec leurs sources Excel/CSV. Les
[22 contrôles JavaScript historiques en mémoire](../artifacts/testing/demand_pf_20261008/quantity_view_javascript.json)
vérifient notamment l'ordre des graphiques et le changement de version MRP.
Le navigateur n'a pas été exécuté ; ces preuves ne certifient pas la calibration.
Le [rendu des trois courbes](../artifacts/testing/demand_pf_20261008/quantity_reconciliation_revision.json)
conserve exactement les mêmes données et résultats de simulation. Ses
[contrôles JavaScript](../artifacts/testing/demand_pf_20261008/quantity_reconciliation_javascript.json)
vérifient les trois rôles, le calcul estimé et les quatre semaines incohérentes.

**Essai demandé le 8 octobre — retour à la demande `demand_PF`.**
La comparaison `demand_pf_20261008` utilise `demand_PF.xlsx`, feuille
`Demande`, colonne E (`real demand`), comme demande physique des clients.
Pour cet essai seulement, `demande = max(0, real demand)` : les quatre
valeurs négatives de Permixon deviennent zéro, sans réduire les demandes
positives suivantes. Le brut signé et les cellules sources restent visibles.
L'historique de `Flow_Data_Customer_Demand` est affiché séparément ; il
n'est pas renommé en expéditions industrielles mesurées.

Les prévisions datées `Flow / Projection`, les règles MRP, les stocks et
engagements initiaux sont conservés. Seul `meta.customer_demand_history`
change dans le graphe de l'essai. La répartition quotidienne reste entière
et la simulation expédie uniquement pour satisfaire la demande connue.
La réponse simulée comparée est le service exécuté au client, après transport.

La source PF contient des numéros de semaine, sans dates explicites.
Convention de comparaison : `step 1 = lundi 30 décembre 2024`.
Ses 52 semaines se terminent le 28 décembre 2025 ; l'exécution couvre donc
362 jours, sans fabriquer la demande des 29–31 décembre. La part des deux
jours de 2024 n'est pas redistribuée en 2025. Les totaux des 51 semaines
complètes affichées se distinguent de ceux des 362 jours exécutés.
La référence de travail précédente reste conservée comme témoin. La décision
utilisateur ci-dessus promeut cet essai sur le périmètre demande / dépôt ;
elle ne prouve pas le sens industriel des valeurs négatives.

Résultat vérifié : l'écart absolu moyen de stock à Muret, sur les mêmes
52 photos (celle du 29 décembre représente la clôture du 28), passe de
240 023 à 289 191 UN pour Cicalfate et de 177 434 à 177 680 UN pour Permixon.
Ce retour à la demande PF ne suffit donc pas à améliorer ces deux stocks.
La [comparaison interactive](../resultats/demand_pf_20261008/comparaison.html)
conserve les deux calculs ; la [vérification indépendante](../artifacts/testing/demand_pf_20261008/validation.json)
rapproche sources, quantités quotidiennes, événements et valeurs du HTML.
Le [rapport d'exécution](../artifacts/testing/demand_pf_20261008/report_pf_zero.json)
et le [contrôle des bilans et tests](../artifacts/testing/demand_pf_20261008/toolbox/gate-83c1f1c7841c42939a294f9315f3874d/manifest.json)
documentent cet essai ; aucun contrôle navigateur n'a été exécuté.

**Référence MRP 2025 précédente — conservée pour comparaison.** La version
`customer_orders_only_20261008/run_candidate_365`, avec son graphe
`graph_candidate.json`, était le point de départ avant l'adoption de la
référence demande / centre de distribution ci-dessus.
Elle conserve les règles amont C8R et limite les départs clients à la demande
connue (`known_demand_only_v1`). C8R devient un témoin historique, hors du
parcours courant ; ses résultats restent conservés pour mesurer les progrès
et les régressions. Ce choix corrige une incohérence métier, mais ne signifie
pas que tous les stocks se rapprochent des sources : les écarts de Cicalfate
baissent et ceux de Permixon augmentent sur les 52 photos 2025. Le nominal
historique de cinq ans et ses campagnes de risques restent distincts de cette
référence de travail annuelle.
Le [registre de cette référence](reference/mrp_current.json) fixe le graphe,
les paramètres de la commande exécutée, les fichiers du moteur et les résultats.

**Comparaison prévisions / départs.** Pour chaque semaine complète de 2025,
retenir une seule valeur prévisionnelle de cette semaine, dans la dernière
version qui la renseigne et qui était connue au lundi d'ouverture. Si le
nouveau plan omet la semaine courante, conserver sa dernière valeur explicite
du plan antérieur ; une absence n'est pas un zéro. Ne pas sommer les versions
mensuelles. Le total ainsi obtenu est un total de prévisions glissantes,
pas celui d'un plan annuel unique. Les départs simulés sont les événements
`lane_ship` de Muret vers le client, non les réceptions ni le service après
transport. `Actual Demand` reste l'historique client source, sans être assimilé
à des expéditions industrielles tant que son sens physique n'est pas confirmé.
Les mouvements signés du dépôt ne permettent pas de reconstruire ces départs
bruts avec certitude. La concordance historique/départs simulés n'est pas un
test indépendant, puisque cet historique alimente aussi la simulation.

**Clarification client du 8 octobre — commandes connues uniquement.** L'utilisateur
confirme qu'il s'agit de clients, sans politique de stock de distribution à
réapprovisionner depuis une prévision. Les prévisions servent à planifier les
fabrications et les approvisionnements ; elles ne constituent pas des commandes
physiques à expédier. La règle `known_demand_only_v1`, sélectionnée explicitement
par article/client, remplace la couverture prévisionnelle historique :

```text
après les réceptions et le service du jour :
quantité à expédier = max(0, demande connue restant à servir
                            − stock client encore utilisable
                            − quantités déjà engagées vers ce client)
```

Tous les engagements ouverts couvrent le besoin une seule fois, même si leur
date est tardive. Stock, transport et quantités UN entières restent applicables.
Ni le reliquat d'une prévision hebdomadaire ni une prévision future ne créent
un départ client dans ce mode. Les anciennes règles restent reproductibles.

Les sources donnent une demande historique hebdomadaire, sans dates de prise
de commande et de livraison souhaitée. La comparaison conserve sa répartition
journalière existante et la considère connue le jour où elle apparaît. Avec
deux jours de transport, cela peut produire un reliquat durant le transit : ce
compteur ne démontre pas un retard industriel. Ne pas supprimer le délai ou
utiliser la demande future pour le masquer. L'étude séparée
`artifacts/testing/customer_orders_only_20261008` conserve les exécutions et
leurs preuves ; la conformité à cette règle ne certifie pas la calibration
des stocks ni le calendrier des fabrications.

**Résultat de l'essai 2025 :** les deux PF n'ont aucun départ excédant la
demande connue, aucun stock client après service et aucune demande connue
restant à expédier. L'attente finale correspond entièrement au transport de
deux jours. Les 48 tests ciblés et les qualifications CSV passent ;
l'oracle indépendant contrôle 19 872 assertions. L'erreur moyenne de stock
Muret sur 52 photos passe de 254 470 à 240 023 UN pour 268091, mais de
145 076 à 177 434 UN pour 268967. La correction d'expédition ne résout donc
pas la calibration amont. Le témoin reproduit les deux PF sur 90 jours ;
une différence préexistante de 1 UN sur 338929 empêche de déclarer une
reproduction strictement identique de tous les articles face à C8R.
Voir le [rapport et les courbes](../resultats/customer_orders_only_20261008/rapport.md),
le [manifeste des contrôles techniques](../artifacts/testing/customer_orders_only_20261008/toolbox/gate-d577048ba68147be867d048de1865495/manifest.json)
et l'[oracle indépendant](../artifacts/testing/customer_orders_only_20261008/validation/dispatch_oracle.json).

**Suite du 7 octobre — banc local A :** le [protocole et les résultats](REFONDATION_MRP.md#résultats-du-banc-local-a--7-octobre-2026)
portent sur quatre couples, 208 versions et 832 plans conditionnels, avec H
réservé à la comparaison. L'[HTML local](../resultats/mrp_local_20261007/comparaison.html)
sépare courant restant/exclu, addition/maximum, arrivée/disponibilité et
couverture. Le banc est retenu pour le diagnostic ; **aucune nouvelle politique
de chaîne n'est adoptée**. La matrice C8R ci-dessous reste celle de la référence
conservée. Les [preuves](../artifacts/testing/mrp_local_20261007/manifest.json)
précisent les contrôles exécutés et leurs limites.

**Correction numérique retenue :** les incréments de l'enveloppe de protection
sont publiés en fragments datés dont les représentations décimales conservent
exactement le budget. Un arrondi intermédiaire vers le haut créait auparavant
une UN supplémentaire dans 316 plans du banc. Aucun paramètre de sécurité, lot,
fournisseur ou périmètre industriel n'est modifié. Les références C8R antérieures
ne sont pas recalculées ; lire le bilan du banc pour le diff ciblé et les preuves.

**Audit aval, 7 octobre :** la lecture de la demande client et les conservations
DC/client/transit sont vérifiées sur C8R, mais le stock client anticipé n'est
pas observé. Les 10/15 jours de réception PF sont sourcés dans la division
Muret ; leur localisation avant départ dans les usines reste hypothétique.
Les départs C8R sont revus quotidiennement, sans attente camion plein ; leurs
multiples dérivent des lots de fabrication. Aucune cadence industrielle n'est
identifiée dans les soldes hebdomadaires Muret. Lire l'[audit aval](REFONDATION_MRP.md#audit-aval--demande-muret-et-expéditions-pf-7-octobre-2026)
et ses [preuves](../artifacts/testing/mrp_local_20261007/dc_dispatch_audit_manifest.json)
avant de généraliser la règle « PF directement au dépôt ».

## Registre consolidé au 7 octobre 2026 : référence C8R

**C8R est le compromis de comparaison conservé, pas un modèle industriel calibré.**
Le [graphe exact](../artifacts/testing/mrp_packaging_solutions_20261006/graph_C8R.json)
et le [rapport d'exécution](../artifacts/testing/mrp_packaging_solutions_20261006/report_C8R.json)
désignent 365 jours physiques de 2025. Les projections restent glissantes sur
52 semaines et peuvent dépasser décembre. Les résultats de C8R ont été produits
sur un code stable à l'exécution ; le moteur de travail a changé depuis. Lire
ses CSV ne constitue pas une réexécution de ce moteur actuel.

L'[inventaire machine du scénario](../artifacts/testing/scan3_scope_20261007/scenario_audit.json)
joint le graphe, la commande et `run_C8R_365/run/policy.json`. C'est indispensable : le
graphe garde notamment 1 825 jours et `state_scale=0.02`, mais la commande
exécutée impose **365 jours et une échelle 1**. Les flags dynamiques finaux
annulent les anciens couples statiques ; le résumé effectif donne une liste
statique vide. La projection MRP vaut **364 jours**, soit 52 semaines, et non
la durée physique de simulation.

**L'exclusivité Scan3 aux seuls PF 268091/268967 est une hypothèse rouverte.**
I = « Sorties » et J = « Sorties_article_scan3 » dans le fichier de mouvements.
Leurs signes participent au bilan ; I n'est ni un total incluant J, ni une
consommation hors projet prouvée partout. Dans le fichier MRP, I désigne au
contraire les besoins et J des contributions de stock datées. Ces deux contrats
de colonnes ne sont jamais interchangeables. Voir l'[audit consolidé](../artifacts/testing/audit_perimetre_scan3_20261007.md).

La table ci-dessous prime pour l'activation C8R. Les fiches qui suivent conservent
les formules et essais historiques, avec leurs noms C, A, Q, PACK, etc. Une règle
présente dans ces fiches n'est pas automatiquement active dans C8R.

| Règle et formule | Périmètre et condition réelle C8R | Origine / statut de preuve |
|---|---|---|
| Prévision connue : dernière version publiée avant la décision ; `reste = max(0, prévision semaine − demande arrivée)` | Clients des deux PF puis réseau amont ; 52 semaines glissantes. Les prévisions 2026 sources sont conservées sans +5 %. | Classeur client + convention de publication au lundi ; consommation de prévision programmée, pas mode ERP identifié. |
| Besoin composant : `Σ(fabrication restante × coefficient BOM de son étape) + autres usages prévus` | `separate_own_and_other_v1` ; le total MRP industriel reste une comparaison, sauf les deux étuis ci-dessous. Ne pas transformer l'écart industriel/BOM en consommation physique. | BOM source ; séparation des usages et estimation complémentaire hypothétiques tant que Scan3 n'est pas identifié. |
| Étuis : sur semaine renseignée, `besoin = max(besoin industriel restant, besoin déjà engagé)` ; sinon besoin du modèle | 338929/Avène et 333362/Gien seulement : `source_weekly_with_committed_floor_v1`. | Compromis C8R ; identité commune des OF et des besoins MRP non prouvée. C9/C10 exclusifs et C11/C12 cumulés non retenus. |
| Révision industrielle : dernière version connue de l'article/site pour le futur ; semaine en cours gelée à sa version préalable | `latest_vintage_v1`. Une semaine supprimée n'est pas réimportée d'une ancienne version ; absence ne signifie pas zéro. | Correction de sélection des versions ; repli BOM/autres usages conservé. Distinct du calendrier de prévisions client. |
| Exécution historique I : répartir `−I` sur les sept jours de la semaine ; UN par différences de cumuls entiers | Couples admissibles seulement : aucune I positive, pas de fabrication locale ni de transfert sortant déjà représenté. Jour documenté remplace estimation ; jour absent garde estimation. | Observation hebdomadaire + convention de répartition journalière ; l'affectation aux « autres usages » demeure hypothétique. Ce rejeu n'est pas une prévision autonome. |
| Position : `disponible + entrées utilisables à t − besoins restants à t` ; `déficit = max(0, protection − position)` | Tous les stocks effectivement planifiés ; disponible, réservé, indisponible, fabrication et transit restent séparés. | Noyau commun ; déduire chaque engagement une seule fois. Une libération ne crée pas une réception physique. |
| Achat protégé : `date besoin − sécurité ouvrée − réception ouvrée − délai fournisseur` | Achats datés déterministes ; calendrier réellement appliqué ; regroupement 1 jour, sauf politique explicitement configurée. | Jours source et confirmation lundi–vendredi ; délai fournisseur sans Erlang dans cette phase. |
| Sécurité achats : anticipation des besoins + stock fixe ; autres nœuds : `max(stock fixe, besoins pendant jours source)` | Ne pas ajouter une seconde anticipation à un besoin déjà avancé. 049371, 333362, 730384, 708073 possèdent les deux paramètres. | Convention actuelle à identifier ; l'addition et le maximum ne sont pas deux formulations équivalentes du même choix métier. |
| Dépôt Muret : 20 jours 268091, 25 jours 268967, à 100 % | Comparaison 2025, sans coefficient 0,75. | Choix utilisateur ; distinct des politiques plus récentes conservées dans les sources. |
| Fournisseur : offre choisie/parts configurées, ou principal/secours si déclaré | 001848/Avène : principal 1,58 €/kg, 56 j, 6 000 kg ; secours 4,20 €/kg, 21 j, 4 000 kg. Ne pas généraliser cette sélection. | Offres source et principal confirmé ; déclencheur du secours et parts des autres offres restent conventions. |
| Quantité : arrondi net masse au kg le plus proche, demi supérieur ; puis minimum/multiple/plafond propres à l'opération | UN physiques entières. 268091 : min 28 800, multiple 14 400, plafond 142 485 (plus grand multiple admissible 129 600). 268967 : 107 800 UN ; 773474 : 3 200 kg ; 693055 : 600 kg. | Sources + conventions utilisateur/modèle ; un standard achat n'est pas nécessairement un multiple. Standards des deux étuis non contraignants dans C8R. |
| Complément carnet initial : `max(0, H premier plan − engagements représentés)` | Deux étuis ; connu au premier plan du 5 janvier. 423 027 UN supplémentaires à Avène, sans créditer le stock du 1er janvier ni créer un achat nouveau. | Reconstruction hypothétique d'engagements ; jour et fermeté non démontrés. |
| Report de promesse : retirer sa seule couverture, rechercher son besoin, garder identité/quantité/fournisseur et plancher de date originale | Promesses d'achats des deux étuis supposées modifiables ; revue hebdomadaire. Ni réception exécutée ni transport parti déplacés. | Hypothèse de statut ; C8R meilleur compromis local du lot d'essais, pas validation des commandes ERP. |
| PACK initial : `reste à conditionner = quantité OF − quantité déjà conditionnée`, limité par emballages, capacité et calendrier | 20 OF initiaux Avène, 1 945 715 PF ; matières supposées incorporées avant ouverture, Pack prélevé au conditionnement. Pas de même OF initial à Gien. | Rôle Pack source ; statut matière/emballage initial hypothétique. **Actif dans C8R**, même si les premières fiches ci-dessous le décrivent comme essai. |
| Lancement : minimum du besoin dû, composants utilisables, capacité et lots admissibles | Avène/Gien/Gaillac. Fermeture Avène 4–15 août inclus. `tau_process` reste un paramètre de planification. | Contraintes programmées ; aucune durée physique de fabrication déduite sans confirmation. Capacité Gaillac d'un lot/jour conventionnelle. |
| Libération et circulation : présence physique puis disponibilité ; PF libérés poussés à Muret sous contraintes | PF Avène 10 j ouvrés, Gien 15 ; Gaillac 693055 28 ouvrés, 773474 33 ouvrés. Routes semi-finis : 773474 transport 10 j puis réception Gien 6 ouvrés ; 693055 transport 7 j puis Avène 7 ouvrés. PF → Muret : 2,5 j ; Muret → client : 2 j. | Sources/conventions localisées ; transports 693055, PF/Muret et Muret/client hypothétiques. Les 70 j FIA ne sont pas 70 j de camion. `stochastic_lead_times=false` malgré le type historique `erlang_pipeline` des routes. |
| Fabrication 693055 : lot Gaillac avec intrant fictif explicite | BOM amont industrielle absente. | Hypothèse autorisée ; ne prouve ni formule ni consommation industrielle réelle. |
| Bilan : `stock fin = stock début + entrées + mouvements signés` ; `retard fin = retard début + besoin arrivé − servi` | Chaque article/site ; propositions, achats engagés, fabrications, départs, réceptions, disponibilité et deux suivis de lots restent distincts. | Invariants physiques ; fermeture numérique ≠ calibration. Objectif d'un an médicament global, pas un an à chaque nœud. |

### Matrice d'application par nœud et opération

| Nœud / articles | Besoin utilisé | Protection / ordre / exécution | Limite à garder visible |
|---|---|---|---|
| Clients 268091/268967 → DC-1920 Muret | Historique au jour courant + prévision résiduelle connue | Dépôt 20/25 jours ; couverture client pendant transport ; expédition puis service | Demande arrivée n'est pas livraison industrielle mesurée ; tampon client non observé. |
| M-1810 Avène / 268091 | Besoin net dépôt, engagements, BOM | Fabrication par lots ; PACK initial ; libération 10 ouvrés puis transfert | Correspondance matières/conditionnement/Scan3 non résolue. |
| M-1430 Gien / 268967 | Besoin net dépôt, engagements, BOM | Lot 107 800 ; libération 15 ouvrés puis transfert | PGA inactif ; 60,342 capsules/PF ne justifie pas une BOM multipliée par cinq. |
| M-1810 / 338929 ; M-1430 / 333362 | Besoin industriel des semaines renseignées, plancher engagé ; modèle hors couverture | Achat protégé, standard non contraignant, complément ouverture, revue et report hebdomadaires | Compromis C8R limité aux étuis, non généralisable à 049371. |
| M-1810 / autres composants BOM, dont 049371 | BOM + prévision séparée des autres usages ; MRP industriel comme comparaison | Achat par offre ou transfert 693055 ; rejeu I uniquement si admissible | I peut contenir des contre-mouvements ; les couples avec I positive sont exclus du rejeu et gardent l'estimation. |
| M-1430 / autres composants BOM, dont 773474 et 042342 | BOM + autres usages prévus | Achats externes ou transfert 773474 ; délais/réception propres | Quantités de capsules et semi-fini cohérentes entre elles, périmètre de l'étui différent ou étape à documenter. |
| Gaillac / 773474 → Gien | Besoin interne de Gien + besoins locaux distincts | Fabrication 3 200 kg, stock Gaillac, transport 10 j, réception 6 ouvrés | I Gaillac peut être transfert ; égalité annuelle 67 200 kg ne relie pas individuellement les ordres. |
| Gaillac / 693055 → Avène | Besoin interne d'Avène + besoins locaux distincts | Fabrication 600 kg, intrant fictif, transport 7 j hypothétique, réception 7 ouvrés | Absence de BOM amont ; hypothèse explicitement séparée des données source. |
| Gaillac / 021081 | Explosion BOM de 773474 | Achat selon offres et calendriers | Coefficient 8,94 kg pour 1 kg de 773474 ; transformation, pas égalité de masses sans rendements/coproducts. |
| Autres couples présents dans les Excel | Ne pas les créer par simple présence documentaire | Déclarer état, route et politique propres avant approvisionnement | Couverture partielle/absente et unités restent visibles dans le classement historique. |

Périmètres exacts tirés de la politique exécutée, sans confondre présence dans
les sources et activation :

| Site | Besoins MRP industriels (24 couples) | Rejeu physique I admissible (21 couples) |
|---|---|---|
| Gien | 038005, 042342, 333362, 344135, 708073, 730384, 734545, 773474 | 001848, 038005, 333362, 344135, 708073, 730384, 734545, 773474 |
| Avène | 001757, 001848, 001893, 002612, 007923, 016332, 029313, 039668, 049371, 055703, 099439, 338928, 338929, 426331, 693055 | 001757, 001848, 002612, 007923, 049371, 055703, 338928, 338929, 426331, 693055 |
| Gaillac | 021081 | 001893, 002612, 021081 |

Les prévisions séparées d'autres usages concernent **18 couples**, listés avec
les paramètres détaillés dans l'inventaire machine. Une I positive sur une seule
semaine exclut **tout le couple** du rejeu, même si son total annuel reste négatif :
c'est le cas de 001893/Avène. Les quatre autres exclusions de matières Avène sont
016332, 029313, 039668, 099439. L'absence de rejeu ne signifie pas absence d'usage.

001848/Gien utilise une **politique candidate** de multiple 7 000 kg et protection
26 jours ouvrés, pas une sécurité source confirmée. Gaillac 001893/002612 restent
partiellement représentés, sans politique complète d'approvisionnement.

**Transferts expérimentaux inactifs dans C8R :** les trois clés
`internal_transfer_planning_lot_policy` (L), `internal_transfer_commitment_policy`
(K), `internal_transfer_rescheduling_policy` (A) sont absentes du graphe et du
journal exécuté. `production_programme_policy` (PGA) est également absente.
Le multiple physique de transfert 600 kg de 693055 reste actif ; le lot de
fabrication 3 200 kg de 773474 n'est **pas** un multiple de transfert actif C8R.

### Essais et décisions

- C8R : reproduction annuelle de C8 après correction décimale ; mêmes achats,
  réceptions et contraintes, au plus 1 UN d'écart sur 11 clôtures 338929.
  Compromis conservé ; 9 des 27 stocks annuels restent au-dessus de 50 % d'écart
  moyen rapporté au stock réel moyen. [Bilan et preuves](../artifacts/testing/mrp_packaging_solutions_20261006/bilan.md).
- PGA : avancement d'un lot existant dans chaque usine ; **non retenu**,
  9 stocks améliorés, 15 dégradés, 3 identiques, volumes annuels inchangés.
  [Bilan annuel](../artifacts/testing/mrp_production_programme_20261006/bilan.md).
- Q et C11/C12 (enveloppes cumulées), C9/C10 (industriel exclusif), essais de
  maintien/avancement des transferts : conserver leurs résultats et limites
  propres ; aucune adoption implicite par leur présence dans le code.
- Audit Scan3 du 7 octobre : **correction documentaire retenue** ; périmètre
  produit/vrac encore hypothétique ; aucune modification ni nouvelle simulation
  du moteur. A = identification locale avec besoins industriels connus ;
  B = chaîne depuis demande/BOM. Un rejeu des observations ne valide pas B.

## Fiches historiques et formules détaillées

Les paragraphes suivants décrivent leurs références nommées, principalement C,
puis les essais successifs. Les anciens essais restent dans le
[journal d'analyse](../data/reports/mrp_source_rules.md).

## Deux essais isolés sur les emballages

La référence C conserve ses règles. Les options suivantes ne sont activées que
dans les graphes expérimentaux PACK et REPORT, sur 365 jours. Les résultats et
leurs vérifications sont conservés dans
`artifacts/testing/packaging_trials_20261005` ; la présence du code ne signifie
pas que la règle est validée industriellement ou adoptée dans le nominal.

**PACK — terminer le conditionnement des fabrications initiales.** Pour les OF
explicitement sélectionnés et les composants classés « Pack » dans la BOM :

```text
reste à conditionner = quantité de l'OF − quantité déjà conditionnée
quantité réalisable = minimum(reste, capacité libre, quantité permise par les emballages disponibles)
besoin d'emballage restant = besoin total de l'OF − prélèvements déjà exécutés
```

Les OF initiaux sont servis dans l'ordre de leur date source, avant les nouvelles
fabrications, sur la même capacité journalière. Les emballages sont prévus dans
le MRP et prélevés physiquement lors du conditionnement. Les matières déjà
incorporées dans l'encours ne sont pas prélevées une seconde fois. Les unités
physiques restent entières ; l'arrondi cumulé par OF évite de répéter l'arrondi
à chaque fraction. Un retard de conditionnement décale la libération en
conservant la durée en jours ouvrés entre les dates G et I de l'OF source.
L'état « matières incorporées, emballages non encore prélevés » est une hypothèse
de cet essai, pas un statut industriel disponible dans les fichiers.

**REPORT — décaler une réception encore modifiable.** Uniquement pour un
engagement déclaré non expédié, non réceptionné et replanifiable :

```text
date limite = première date où, sans cet engagement, le stock projeté passe sous la protection
nouvelle disponibilité = au plus tard cette date, sans avancer la réception existante
```

Les autres engagements restent déduits du besoin. La quantité et l'identité
sont conservées, puis le MRP est recalculé avant tout nouvel achat. En l'absence
de déficit, le report reste limité à l'horizon continu des prévisions connues ;
une semaine absente n'est pas un besoin nul. Le délai de traitement à réception
reste compté du lundi au vendredi. Le scénario Gien porte sur six commandes
initiales ; leur permission expérimentale de report expire avant leur date
physique initiale, même si leur réception a entre-temps été décalée. Les sources
ne prouvent pas leur statut d'expédition. La date reconstruite de lancement
d'une commande n'est donc pas utilisée comme preuve de départ d'un camion.

## Le principe commun

On part de la demande client, puis on remonte les besoins vers le dépôt, les
usines de produits finis, les semi-finis et les fournisseurs. On exécute ensuite
les mouvements dans l'autre sens, avec les matières réellement disponibles.

```text
position prévue à t = disponible aujourd'hui
                      + entrées utilisables d'ici t
                      − besoins restant à servir d'ici t

déficit à t = max(0, protection demandée à t − position prévue à t)
```

Un déficit de date ne signifie pas automatiquement une nouvelle commande :
si une quantité est déjà commandée mais arrive trop tard, il faut traiter sa
date et son retard sans la commander deux fois. Le moteur conserve ces deux
questions : **combien manque-t-il réellement** et **quand cette quantité sera-t-elle disponible**.

## Toutes les règles de décision de ce parcours

| N° | Règle simple | À quoi elle s'applique |
|---|---|---|
| 1 | **Recalculer sur 52 semaines glissantes**, avec les prévisions connues au jour du calcul. | Toute la chaîne ; le calcul physique de comparaison reste limité à 2025. |
| 2 | **Ne pas ajouter la demande réelle à la prévision complète.** `Prévision restante = max(0, prévision de la semaine − demande déjà arrivée)`. | Demande des clients, puis besoins remontés à Muret et aux usines. |
| 3 | **Propager les besoins par la nomenclature.** `Besoin du composant = fabrication prévue × quantité de composant par produit`. Diviser la quantité BOM par sa taille de base et convertir les unités. Utiliser la date de lancement de la fabrication. | Usines PF vers matières/emballages/semi-finis ; usine de semi-finis vers ses matières. |
| 4 | **Compléter les besoins BOM à partir du plan industriel.** Dans C, pour une semaine documentée : `complément prévu = max(0, besoin industriel total − besoin propre calculé par BOM)`. Ce maximum hebdomadaire peut gonfler le total lorsque les deux calendriers représentent un même usage décalé. | Matières et composants ayant un plan industriel. Le rapprochement des usages reste une hypothèse ; voir l'essai Q ci-dessous. |
| 5 | **Utiliser le stock disponible avant de commander.** Le stock bloqué/libéré plus tard, la fabrication en cours et le transit ont chacun leur date de disponibilité. | Tous les stocks. La sécurité est un objectif, pas une quantité physiquement bloquée. |
| 6 | **Déduire chaque engagement une seule fois.** Une quantité en commande, fabrication ou transit ne doit pas provoquer une seconde commande pour le même besoin. | Achats, fabrications et transferts. Une entrée tardive reste signalée comme tardive. |
| 7 | **Protéger les besoins avec les jours de sécurité et le stock fixe configurés.** Recalculer cette protection à chaque date future. | Matières, composants internes, fabrications et dépôts ayant une politique de stock. Voir les deux modes ci-dessous. |
| 8 | **Commander assez tôt pour disposer de la matière à la date protégée.** Retrancher traitement à réception, puis délai fournisseur, en respectant leurs calendriers. | Achats de matières et emballages. Pour les transferts internes, utiliser le transport et le traitement propres à la route. |
| 9 | **Choisir un créneau réellement autorisé.** Prendre le dernier départ/lancement permettant de respecter la date ; si elle est déjà impossible, prendre le premier encore possible et conserver le retard. | Transferts et fabrications datés. Les créneaux sont ceux du modèle, pas des rendez-vous industriels identifiés. |
| 10 | **Choisir le fournisseur selon la politique du couple article/site.** Fournisseur désigné, principal/secours ou répartition configurée ; utiliser son prix, son délai et son lot. | Achats externes des usines PF et de Gaillac. Le moins cher n'est pas imposé universellement. |
| 11 | **Dimensionner selon minimum, multiple et maximum.** Arrondir au multiple supérieur lorsqu'il est obligatoire ; découper si le maximum par lot est dépassé. Le surplus sert aux besoins suivants. | Commandes, lots de fabrication et transferts disposant d'une contrainte explicite. |
| 12 | **Regrouper seulement les besoins encore non couverts dans la fenêtre configurée.** La fenêtre d'achat actuelle est de **1 jour**. | Achats datés ; aucun regroupement mensuel universel n'est établi. Un départ hebdomadaire ne signifie pas une commande hebdomadaire. |
| 13 | **Ne lancer la fabrication que lorsqu'elle est due et réalisable.** Limiter par composants disponibles, capacité, lots et calendrier. Une autorisation n'est pas une fabrication terminée. | Gaillac, Gien et Avène. Les encours restent distincts du produit disponible. |
| 14 | **Rendre le produit utilisable après le traitement configuré.** Une matière reçue ou un produit terminé peut être présent mais encore indisponible. | Réceptions fournisseurs, semi-finis et PF. Un changement de disponibilité ne crée pas une seconde entrée physique. |
| 15 | **Envoyer au dépôt les PF libérés de l'usine**, au créneau d'expédition et dans les limites physiques. | Avène → Muret et Gien → Muret. Le stock encore en contrôle reste à l'usine selon la convention retenue. |
| 16 | **Expédier seulement la demande client connue non couverte** : `max(0, demande restant à servir − stock client utilisable − engagements ouverts)`. | Muret → client, mode `known_demand_only_v1` testé le 8 octobre. L'ancienne couverture prévisionnelle pendant le transport reste reproductible dans C8R ; elle autorisait des envois sans demande correspondante. |
| 17 | **Reporter ce qui n'a pas été servi.** `Retard fin = retard début + besoin arrivé − quantité servie`. | Demande client et autres consommations physiques ; besoins de fabrication restent en attente si les composants manquent. |
| 18 | **Recalculer les propositions non exécutées ; conserver les ordres réellement engagés.** Une proposition modifiable n'est pas une commande ferme. | Tout le plan daté. Les achats externes fermes ne sont pas automatiquement annulés ou avancés. |
| 19 | **Garder le même lot dans le plan et dans le transport interne.** | Essai L, repris dans K et A : routes internes uniques ayant un multiple physique explicite ; 3 200 kg pour 773474, 600 kg déjà configurés pour 693055. |
| 20 | **Maintenir puis avancer un transfert engagé lorsqu'un départ plus proche est nécessaire et physiquement possible.** Garder son identité et déduire la quantité effectivement expédiée. | Essai A vérifié sur 2025, sur les transferts admissibles Gaillac → Gien/Avène. Le blocage de janvier est corrigé ; A ne remplace pas globalement C. |
| 21 | **Rapprocher les besoins cumulés sans retarder les échéances.** `Cumul retenu à t = max(cumul industriel à t, cumul BOM à t)` sur les dates couvertes. | Essai Q, pour tous les composants disposant des deux prévisions. Ce n'est pas une règle ERP démontrée ni un remplacement automatique de C. |

## Les formules et conditions à ne pas confondre

### Rapprochement des besoins — essai Q

Le calcul utilise seulement les prévisions connues au jour de décision et les
dates futures effectivement documentées. Une semaine absente n'est pas un zéro.

```text
cumul BOM(t) = somme des besoins BOM couverts, jusqu'à t
cumul industriel(t) = somme des besoins industriels couverts, jusqu'à t
cumul retenu(t) = max(cumul BOM(t), cumul industriel(t))
besoin retenu(t) = cumul retenu(t) − cumul retenu(date couverte précédente)
```

Chaque quantité BOM est rattachée à ses fragments de prévision, dans l'ordre
des échéances. Sa date peut être avancée, jamais retardée. La consommation
physique reste déclenchée par la fabrication ; aucune consommation future
observée n'est injectée. Les engagements et les réserves ne sont pas des besoins
à fusionner. Les besoins hors couverture et les arriérés restent conservés.

À la fin de la période couverte, la quantité prévue vaut le plus grand des deux
totaux ; à chaque date, elle couvre au moins chacun des deux cumuls. Cette
construction suppose toutefois que les deux prévisions décrivent des usages
qui se recouvrent. Elle pourrait sous-estimer deux usages réellement distincts.
La comparaison des stocks, des fabrications et des manques matière doit donc
accompagner la vérification du calcul. Le [bilan de l'essai](../artifacts/testing/mrp_scope_reconciliation_20261005/bilan.md)
consigne les résultats et la décision de conservation.

Une journée avec un événement de manque matière peut encore comporter une
fabrication partielle. Ce compteur n'est ni un nombre de commandes manquées,
ni un nombre de journées sans production. De même, un stock disponible nul
ne prouve pas, à lui seul, qu'un besoin est resté non servi.

Le premier essai P ne protégeait que le total final : il pouvait effacer un
besoin proche en le compensant par une BOM lointaine. Ses résultats annuels
sont conservés, mais cette variante n'est pas retenue comme règle générale.

### Sécurité et dates

Pour les achats externes, le mode actif anticipe chaque besoin et conserve le
stock fixe en plus :

```text
date protégée du besoin = date du besoin − jours de sécurité ouvrés
arrivée physique visée = date protégée − traitement à réception ouvré
dernière date de commande = arrivée physique visée − délai fournisseur

quantité protégée cumulée = stock fixe source + besoins cumulés ainsi anticipés
```

Les calendriers sont inversés réellement : on ne remplace pas 20 jours ouvrés
par 20 jours calendaires. Le délai fournisseur est déterministe dans ces essais,
sans tirage Erlang. Le traitement à réception et la sécurité utilisent lundi–vendredi.

Pour les fabrications, dépôts et composants internes utilisant un plancher de
stock, la règle active est :

```text
sécurité(t) = max(stock fixe source,
                  besoins prévus entre t et la fin des jours de sécurité)
```

On n'ajoute pas une seconde anticipation de sécurité au même besoin. Aux achats,
stock fixe et anticipation sont additionnés par la politique actuelle ; aux
autres nœuds, le plancher est le maximum ci-dessus. Cette différence est explicite,
elle ne doit pas être masquée par une formule unique approximative.

### Fournisseurs et quantités

- **001848/Avène** : principal confirmé à 1,58 €/kg, 56 jours, standard 6 000 kg ;
  secours à 4,20 €/kg, 21 jours, standard 4 000 kg. Le secours est proposé pour un
  besoin non couvert avant la disponibilité du principal, s'il arrive plus tôt.
  Son déclencheur exact reste une convention testée, pas une date de commande ERP prouvée.
- Pour les autres couples, le fournisseur sélectionné ou les parts configurées
  restent appliqués. La règle principal/secours n'a pas été confirmée partout.
- Les propositions lointaines principal/secours peuvent utiliser le plus petit
  standard admissible ; au lancement, le lot du fournisseur réellement choisi
  s'applique et son surplus est immédiatement déduit des besoins suivants.
- Les standards de **338929 et 333362** restent non contraignants dans cette
  référence. Ce sont des réglages particuliers à revoir, pas une règle générale.
- Les besoins nets de masse sont arrondis **au kg le plus proche**, demi vers le
  haut, avant le dimensionnement en lots ; le résidu reste dans le calcul. Ce
  n'est pas la même chose que l'arrondi au multiple supérieur d'une commande.
  Les quantités physiques en **UN sont entières** ; les prévisions peuvent être fractionnaires.
- Un maximum de lot limite un lot, pas la production annuelle. Pour 268091 :
  minimum 28 800 UN, multiple 14 400 UN et plafond source 142 485 UN ; le plus grand
  multiple admissible est donc 129 600 UN. Plusieurs lots peuvent être nécessaires.
  268967 utilise 107 800 UN ; 773474, 3 200 kg ; 693055, 600 kg.

### Avancement d'un engagement interne — essai A

On conserve le plan normal, puis on regarde ce qui devrait partir aujourd'hui
sans les seules promesses internes encore futures. Les engagements déjà dus
restent dans ce second calcul.

```text
supplément à avancer = min(reliquat des promesses futures,
                          max(0, nouvelles propositions dues aujourd'hui sans ces promesses
                                 − nouvelles propositions normales dues aujourd'hui))
```

Ce calcul ne lance aucune autre proposition de fabrication ou d'achat. Le
contrôleur physique vérifie ensuite les lots, le créneau, le disponible, la
capacité et le partage du stock. Seule la quantité réellement partie est
affectée à l'engagement existant. Ses dates originales restent traçables ; un
reliquat non expédié conserve sa date. Le transit remplace cette partie de la
promesse, sans addition des deux.

## À chaque liaison, quelle décision ?

| Liaison | Origine du besoin | Décision |
|---|---|---|
| Client → Muret | Demande arrivée, prévision restante et retard | Préparer les expéditions et les besoins futurs du dépôt. |
| Muret → usine PF | Demande, stock/engagements du dépôt et sécurité | Proposer des fabrications PF ; les quantités libérées sont ensuite poussées au dépôt. |
| Usine PF → Gaillac semi-fini | Fabrications PF prévues, BOM, usages industriels documentés et sécurité du composant | Transférer le semi-fini, puis produire à Gaillac la quantité amont non couverte. |
| Usine PF → fournisseur | Besoins matières/emballages et autres usages prévus | Commander selon délai, réception, sécurité et lot du fournisseur. |
| Gaillac producteur → fournisseur | Besoins de fabrication des semi-finis | Même calcul d'achat pour les matières réellement représentées. |
| Site jouant le rôle de réserve → autre site | Besoin du site destinataire | Transfert du stock existant ; aucune transformation si aucune BOM n'est utilisée. Seulement pour les routes effectivement modélisées. |

## Conventions importantes et limites actuelles

- **Périmètre** : la présence d'un article/site dans un Excel ne suffit pas à
  l'activer dans le moteur. Le [bilan de couverture](../artifacts/testing/mrp_reference_coverage_20261005/bilan.md)
  distingue 27 comparaisons annuelles, 2 partielles et 4 couples non représentés
  ou non rapprochables. Un ordre initial seul n'est pas une simulation MRP complète.
  Les achats pour des usages hors BOM exigent un stock, une route et une politique
  locale documentés ; une sécurité absente reste inconnue.
- **Démarrage** : utiliser stocks et ordres en cours sources. Les matières des OF
  initiaux sont supposées déjà prélevées ; elles ne sont pas consommées deux fois.
  Cette hypothèse n'est pas démontrée pour les emballages : la
  [revue des encours](../artifacts/testing/mrp_scope_reconciliation_20261005/opening_review.md)
  identifie des prélèvements de janvier proches des dates des OF d'Avène.
  Leur séparation par étape de fabrication n'est pas encore implémentée.
- **Sécurité à Muret en 2025** : 20 jours ouvrés pour 268091 et 25 pour 268967,
  conformément au choix utilisateur historique ; 100 % des jours retenus, sans
  coefficient 0,75. Les valeurs plus récentes du classeur restent conservées.
- **Prévisions client absentes** : reprendre une version connue contenant la semaine ;
  à défaut, utiliser le repli documenté sur une période connue. Les prévisions
  2026 présentes dans le fichier client sont conservées, sans leur ajouter 5 %.
- **Révision des besoins industriels composants (correction du 6 octobre)** :
  avec `industrial_forecast_revision_policy=latest_vintage_v1`, utiliser le
  dernier plan connu de l'article/site pour les semaines futures. Ne pas reprendre
  une ancienne semaine absente du nouveau plan : un besoin déplacé risquerait
  d'être acheté deux fois. La semaine en cours conserve la dernière version connue
  avant son début. Une semaine absente reste inconnue : les besoins BOM et le
  repli documenté pour les autres usages restent applicables, sans observation
  fictive de zéro. Cette règle est indépendante des prévisions client. La
  référence C conserve son ancien comportement pour mesurer l'effet.
  Exemple source : les 110 495 UN de 333362 au 16 mars dans le plan du 23 février
  disparaissent de cette semaine et apparaissent au 23 mars dans le plan du
  2 mars. Le bilan source est `400 250 + 124 000 − 110 495 = 413 755` ; conserver
  l'ancien besoin donnerait un bilan faux de 110 495 UN.
  Les essais annuels et leurs limites sont dans le
  [bilan du 6 octobre](../artifacts/testing/mrp_overstock_root_20261006/bilan.md).
  La correction ne résout pas la replanification des achats déjà engagés :
  leurs quantités et dates restent conservées lorsque les propositions de
  fabrication évoluent. Une prévision source élevée puis révisée peut ainsi
  laisser arriver des composants sans fabrication immédiatement à lancer.
  Il faut distinguer cette limite de la sélection erronée d'anciennes versions ;
  le modèle ne connaît pas la date industrielle de départ de chaque commande.
- **Fermeture** : Avène du 4 au 15 août 2025 inclus. Les autres fermetures ne
  sont pas inventées. Le calendrier de fabrication n'est pas automatiquement
  assimilé au calendrier lundi–vendredi des traitements et de la sécurité.
- **Libération PF** : 10 jours ouvrés à Avène pour 268091 ; 15 à Gien pour 268967.
  **Gaillac** : 28 jours pour 693055, 33 pour 773474, après fabrication selon la
  convention retenue. Ces nombres sources ne prouvent pas à eux seuls un statut qualité.
- **Transferts** : 773474, 10 jours de transport puis 6 ouvrés à Gien ; 693055,
  hypothèse de 7 jours de transport puis 7 ouvrés à Avène. La référence achat de
  70 jours pour 693055 n'est pas considérée comme 70 jours de camion.
- **Fabrication** : `tau_process` garde sa signification de planification.
  À Gaillac, la capacité non fournie conserve une convention d'un lot par jour ;
  693055 utilise la matière fictive autorisée, sans prétendre disposer de sa vraie BOM.
- **Usages partagés physiques** : C, K et A conservent les consommations estimées.
  L'essai E utilisant les sorties physiques I est séparé ; il n'est pas adopté globalement.
  Les sorties Scan3 et les quantités de la BOM ne concordent pas encore partout.
- **Objectif d'un an sur la chaîne médicament** : il ne constitue pas une règle
  automatique imposant un an à chaque site. La contrainte globale bout en bout
  n'est pas identifiée ni validée comme un contrôleur distinct dans ce calcul.
- **Hors de cet essai** : pas de tirage de retards fournisseurs, pas de nouveaux
  incidents, pas de recalage du stock sur chaque photo réelle. Les données réelles
  servent à comparer, pas à imposer artificiellement le résultat physique.

## Révision des anciennes règles — essais du 6 octobre

Le nouveau scénario `separate_own_and_other_v1` teste une simplification, sans
remplacer automatiquement la référence C :

```text
besoin composant à la date t = besoin BOM des fabrications prévues à t
                              + prévision des autres usages à t
```

Les identités, dates et quantités de ces deux catégories restent conservées.
Le besoin total du fichier MRP sert à comparer ; un écart entre ce total et
notre BOM ne devient plus automatiquement une consommation supplémentaire.
La variante cumulative antérieure pouvait aussi avancer un besoin matière
sans avancer la fabrication correspondante ; ce déplacement est absent ici.

Cette règle s'applique au périmètre de composants configuré, achats externes
et entrées de transferts internes protégées. Elle ne remplace pas la demande
client ni la nomenclature d'un produit fabriqué au même site. Le taux utilisé
pour convertir les jours de protection en quantité provient des besoins propres
et autres usages sur la fenêtre prévue. Les jours et planchers source restent
inchangés. Retirer une observation MRP, ou fournir une semaine à zéro, ne change
pas ces besoins ni ce taux : le périmètre est configuré indépendamment des observations.

**Les anciennes prévisions des autres usages restent des estimations.** Le
libellé « Pack » n'établit pas qu'un article est réservé à nos produits. Les
sorties physiques documentent par exemple d'autres usages pour 338928 et
730384 ; inversement, les anciennes estimations en attribuent beaucoup trop
à 001848. Le [contrôle de périmètre](../artifacts/testing/mrp_rule_revision_20261006/scope/note.md)
donne les valeurs et la couverture des sources.

Trois essais annuels isolent les effets : **D**, règle simplifiée ; **DE**, D
avec rejeu des autres sorties physiques disponibles ; **DEP**, DE avec
conditionnement des OF initiaux. Le rejeu DE utilise les consommations au jour
d'exécution, sans fournir à la prévision leurs valeurs futures. Une journée
non renseignée conserve le repli estimé ; zéro documenté reste zéro. DEP
conserve l'hypothèse d'emballages encore à prélever sur les OF initiaux d'Avène ;
ce n'est pas une preuve de leur statut industriel.

**Résultat annuel : aucun des trois essais n'est adopté globalement.** D réduit
l'écart des deux emballages suivis par rapport au dernier essai VP, mais
augmente les jours avec manque matière à Avène de 11 à 19 et dégrade le stock
de 773474 à Gien. DE/DEP exposent une prévision manquante : les autres usages
physiques du tube 338928 sont exécutés mais ne sont pas anticipés par son
calendrier conservé. Les [résultats complets et preuves](../artifacts/testing/mrp_rule_revision_20261006/bilan.md)
distinguent baisse d'erreur de stock, ruptures et conformité des calculs.

Les nouvelles commandes restent engagées lorsque les fabrications prévues
reculent. Les sources montrent des reports de quantités entre versions MRP,
mais ne prouvent pas que chaque commande est encore modifiable. Un futur
report doit préserver son identité, sa quantité et sa couverture, distinguer
promesse et départ physique, et ne pas faire passer une réception décalée en
2026 pour un achat économisé. Le [contrat proposé](../artifacts/testing/mrp_rule_revision_20261006/orders/note.md)
est une analyse de faisabilité, pas une règle activée.

## Stock local hors BOM : 001848 à Gien (essais G1/G2)

Un article/site consommé par d'autres produits doit avoir sa propre boucle
d'approvisionnement. L'ajouter au stock et aux sorties sans route d'achat
produit mécaniquement un épuisement : c'était la limite de l'essai N.

La correction utilise les besoins I du dernier plan local connu pour planifier,
et les mouvements physiques à leur date pour consommer. Ces deux calendriers
ne s'additionnent pas. Les achats sont calculés, pas copiés des réceptions H
futures. Le netting tient compte des commandes déjà engagées et de leur date
de disponibilité ; le passage du détenu au disponible n'est pas une nouvelle
entrée physique.

Pour Gien, le multiple de 7 000 kg est une hypothèse fortement soutenue par les
plans. Le délai de l'offre fournisseur est de 56 jours calendaires et le
traitement local de 26 jours ouvrés. **La protection supplémentaire de 26 jours
ouvrés reste une hypothèse non confirmée**, car aucune sécurité locale n'a été
retrouvée. Elle ne devient pas une règle générale ni un paramètre source.

G1 conserve l'encours Extract ; G2 ajoute conditionnellement deux positions
initiales de 7 000 kg du premier plan, antérieures à la première livraison
nouvelle possible. Leur statut engagé et leur fournisseur ne sont pas prouvés.
Les engagements ne sont pas automatiquement annulés ou reportés lorsque les
prévisions diminuent : cela reste une limite à étudier, pas une permission de
réécrire rétrospectivement les commandes.

Voir le [bilan et la recette G1/G2](../artifacts/testing/mrp_gien_supply_20261006/bilan.md).
Les deux stocks Gaillac de N restent sans réapprovisionnement paramétré.

## Étuis et composants partagés : correction B1/B2/B3

G2 conserve les règles d'emballages de C ; il ne contient pas automatiquement
les anciennes variantes V ou D. Les nouveaux essais réunissent le dernier
plan industriel connu et la séparation `besoins BOM + autres usages prévus`,
avec les emballages prélevés lors du conditionnement des encours initiaux
(statut matière hypothétique conservé comme tel).

Pour B2, la prévision d'autres usages devient `part historique connue × I du
dernier plan connu`. Cette part est calculée sur les seules semaines physiques
terminées ; les prévisions restent séparées de la consommation exécutée.
B3 réserve ce remplacement aux couples dont les autres usages ont une
couverture physique source. Ce périmètre est choisi pour l'étude rétrospective,
pas présenté comme une information ERP disponible au 1er janvier.

Les délais, sécurités sources, prix, BOM et quantités initiales sont conservés.
Une baisse de stock obtenue en déplaçant un manque vers un autre composant
ne suffit pas à adopter une variante. Les [bilans, conditions et vérifications](../artifacts/testing/mrp_packaging_audit_20261006/bilan.md)
distinguent notamment le surplus d'achats à Gien et les consommations
d'emballages manquantes à Avène. B2 est écarté : le changement de prévision
sur des consommations encore estimées produit 250 jours de contrainte matière
à Avène. B3 ramène ce chiffre à 35 et améliore les deux étuis, mais améliore
12 stocks annuels et en dégrade 15 ; son adoption globale n'est pas validée.

Pour poursuivre le diagnostic des étuis, utiliser explicitement le graphe B3
et ses limites, en conservant G2 comme témoin. Ne pas repartir implicitement
de C ou G2 puis présenter leurs anciennes règles comme les corrections B3.
Les constantes sources et les fichiers historiques restent conservés.

## Essais des étuis du 6 octobre : règles d'achat explicites

Ces essais concernent **338929 à Avène et 333362 à Gien**, sur 2025. Ce ne
sont pas des paramètres adoptés pour toutes les matières. Les délais, sécurités,
BOM et fichiers industriels restent inchangés. Le [bilan des variantes](../artifacts/testing/mrp_packaging_solutions_20261006/bilan.md)
conserve aussi les essais écartés et leurs conséquences sur la fabrication.

1. **Ne compter qu'une fois le besoin et les engagements.** Dans une semaine
   industrielle renseignée : `besoin = engagé + max(0, I restant − engagé)`.
   La consommation physique reste celle des fabrications exécutées. Le cas des
   semaines omises est une hypothèse de prévision, pas une donnée industrielle
   égale à zéro. Les essais C9/C10 retirant toute prévision BOM dans ces semaines
   sont écartés : ils ne couvrent plus correctement les fabrications du modèle.
2. **Déduire le stock et les réceptions une fois.** Pour chaque besoin daté :
   `achat = plafond_UN(max(0, besoin − stock affecté − réceptions affectées − surplus déjà proposé))`.
   Une affectation ne couvre pas deux besoins. Dans ces essais, le standard FIA
   de 5 000 est non contraignant : la formule n'impose pas un multiple de 5 000.
3. **Anticiper avec les calendriers sources.**
   `date protégée = date de besoin − jours de sécurité ouvrés` ;
   `disponibilité = départ + délai fournisseur calendaire + réception ouvrée`.
   Le plan choisit le dernier dimanche de revue permettant de tenir la date
   protégée. Sans solution à temps, il conserve le retard. La première revue est
   le 5 janvier. Le plancher fixe s'ajoute une seule fois ; les jours de sécurité
   ne deviennent pas une seconde quantité ajoutée après l'anticipation.
4. **Compléter les encours sans créer un deuxième achat.**
   `complément initial = max(0, H du premier plan − engagements déjà représentés)`.
   Le complément devient connu le 5 janvier, pas au 1er janvier. Les 423 027
   étuis ajoutés au carnet d'Avène sont des réceptions supposées déjà engagées,
   jamais de nouveaux achats décidés ce jour-là. Le jour exact et la fermeté
   restent des hypothèses documentées.
5. **Réviser une date sans dupliquer l'ordre.** Pour une promesse explicitement
   supposée encore modifiable, projeter le stock en retirant seulement cette
   promesse, puis placer sa disponibilité au besoin découvert, sans avancer avant
   sa date originale. Un report peut revenir à cette date originale. Quantité,
   fournisseur et identité restent inchangés ; les réceptions exécutées et les
   transports déjà partis ne sont pas modifiés.

Les essais avec report utilisent la couverture du modèle ; elle ne prouve pas
la fermeté réelle des commandes. Une baisse de l'écart moyen accompagnée de
manques supplémentaires en fabrication est un échec, même si le stock PF
permet encore de servir les clients. Voir les [formules et paramètres détaillés](../artifacts/testing/mrp_packaging_solutions_20261006/engine/cinq_regles_effectives.md).

**Variantes C11/C12 testées puis écartées :** conserver tous les besoins engagés
`E` à leur date, affecter leur volume au budget industriel `I` selon une convention
FIFO explicite, puis rapprocher le reliquat `I'` et la prévision révocable BOM `B` :
`R(t) = max(cumul I'(t), cumul B(t))` et `besoin révocable(t) = R(t) − R(t−1)`.
Le besoin total vaut `E + besoin révocable`, avant protection et déduction du
stock/réceptions. Sur l'horizon couvert, le volume final est `max(E+B, I)` ;
aucun besoin BOM n'est retardé. Cette égalité de volumes ne prouve pas l'identité
des ordres industriels. En particulier, affecter I à un engagement plus tardif
ne couvre pas automatiquement la date industrielle antérieure : cet écart est
tracé. Hors horizon connu, le besoin initial est conservé. Les [conditions et
contrôles de cette variante](../artifacts/testing/mrp_packaging_solutions_20261006/engine/cumulative_purchase_envelope.md)
restent distincts de sa performance sur les stocks.

Les neuf calculs annuels sont terminés. C8 reste le meilleur compromis des
deux étuis : écart moyen réduit de 33 % et 59 % face à B3, sans adoption globale.
C11 augmente les écarts ; C12 crée neuf jours de contrainte sur les étuis de
Gien. La réussite des 93 tests ciblés et des bilans CSV ne suffit donc pas à
retenir ces deux variantes. Le [bilan](../artifacts/testing/mrp_packaging_solutions_20261006/bilan.md)
conserve les chiffres, les scénarios exacts et les limites du programme PF.

C8 a ensuite été réexécuté sous le nom C8R avec le moteur final et le même
graphe : achats, réceptions et contraintes identiques ; au plus une unité de
différence sur 11 clôtures de stock de 338929 après réparation des arrondis.
La [comparaison à utiliser](../resultats/mrp_packaging_solutions_20261006/comparaison_corrigee.html)
affiche cette reproduction, pas uniquement un ancien export requalifié.

## Programme de fabrication : pilote local du 6–7 octobre

L'essai part de C8R et ajoute une règle facultative, commune aux processus
sélectionnés de Gien et d'Avène : **avancer une fabrication déjà proposée si les
besoins de composants du plan connu la justifient et si elle est réalisable
aujourd'hui**. Le scénario nominal ne l'active pas automatiquement.

**Après test sur 2025, cet essai n'est pas retenu à la place de C8R.** Il
améliore les deux stocks PF, mais dégrade légèrement les deux étuis et le
semi-fini de Gien. Le progrès du début d'année ne suffit pas sur l'année entière.

```text
budget composant restant = max(0, besoin source de la semaine
                                  − usages déjà exécutés − besoins déjà engagés)
quantité proposée avant = lot avancé + propositions restantes après son crédit
```

Le lot doit être couvert par les budgets, le stock utilisable, la capacité et
les calendriers. Tout OF initial de conditionnement restant bloque l'avance,
car les lignes MRP ne permettent pas de prouver qu'il s'agit d'une autre
fabrication. La campagne est créée au moment du lancement physique ; aucune
promesse préalable ne déclenche des achats avant une éventuelle annulation.
Les libérations, transports, nomenclatures et sécurités existants restent actifs.

Ce pilote est limité à une avance par processus. Un budget d'une matière
partagée ne prouve pas l'identité d'un OF, et aucun taux de perte n'est inventé.
Le [bilan et les comparaisons](../artifacts/testing/mrp_production_programme_20261006/bilan.md)
séparent les progrès du pilote janvier–avril sur les étuis et le PF des
contreparties sur le semi-fini et des dégradations constatées sur l'année.
Les tests de conservation ne certifient pas la calibration industrielle.

## Expédition client : ancienne variante datée expérimentale

Cette variante précède la clarification client du 8 octobre et conserve encore
une couverture physique prévisionnelle. Elle n'est pas la correction
`known_demand_only_v1` décrite en tête de ce document.

Le contrat optionnel `customer_dispatch_forecast_policy` avec le mode
`dated_source_profile_v1` modifie uniquement la couverture physique des
couples explicitement sélectionnés. Il plafonne le signal futur au profil
quotidien source et au reliquat de la semaine ; il ne réécrit ni la prévision
ni sa consommation globale. La politique d'ouverture
`observed_to_date_mean_v1` utilise seulement la demande déjà connue lorsque
la semaine initiale n'a pas de prévision. Elle reste une hypothèse d'essai.

Le [premier essai Cicalfate sur 90 jours](../resultats/cicalfate_correction_20261008/rapport.md)
améliore les stocks mais ajoute trois jours de retard lorsque la demande
dépasse la prévision. Ce résultat interdit de présenter cette variante comme
un nominal validé. Sans activation du contrat, la règle antérieure demeure.

## Correspondance avec le code

### Essais Gaillac H2 / H3 du 10 octobre 2026

Ces essais restent séparés de la référence. Leurs entrées, commandes et résultats
sont conservés sous `artifacts/testing/gaillac_improvements_20261010`.

**H2 — stock physique et stock retenu par le MRP.** Lorsqu'un rapprochement
source documente une quantité physiquement présente mais exclue du stock MRP,
elle reste dans le registre physique et les coûts de détention, mais ne couvre
pas les besoins tant qu'aucune disponibilité n'est connue :

```text
stock utilisable initial = stock physique initial − quantité exclue documentée
réception future de cette quantité = aucune, si sa date de disponibilité est inconnue
```

Le contrat `initial_stock_availability` accepte alors `release_day: null`,
`availability_status: unknown_mrp_excluded` et une explication sourcée.
Il ne transforme pas un écart de périmètre en diagnostic qualité. Les lignes
datées existantes gardent leur fonctionnement. Pour 001893 à Gaillac, l'essai
conserve 1 094 kg physiques et retient 719 kg utilisables (premier plan,
`Flow_Data_MRP_results.xlsx!Feuille1!J113`) : les 375 kg restants n'ont pas de
date de libération fournie. Comme H1, cet essai reprend explicitement le plan
du 5 janvier pour initialiser le début de l'année. L'ajustement industriel
`Divers −233 kg` d'avril reste hors de cette première correction ; les photos
futures ne réinitialisent jamais le stock simulé.

**H3 — quantité standard indicative.** Essai supplémentaire sur 038005 à Gien :
le standard FIA de 10 000 kg reste une information source, mais n'est plus
imposé comme minimum ou multiple à chaque nouvel achat en l'absence de ces
contraintes documentées. La quantité vient du besoin net daté ; les délais,
la sécurité, les commandes initiales et les consommations restent inchangés.
Les entrées hebdomadaires réelles ne permettent pas de prouver la taille de
chaque commande : il s'agit donc d'une hypothèse testée, pas d'une règle ERP
confirmée. H3 ajoute ce changement à H2 afin d'en mesurer l'effet séparément.

Ces calculs conservent le rapprochement historique F3 des usages matière.
Une meilleure courbe ne suffirait pas à démontrer un MRP autonome ni à lever
les réserves de qualification de ce rapprochement.

### Essais du 10 octobre : consommations rapprochées et 693055 à Gaillac

Quatre essais indépendants de 362 jours repartent de H2. Le
[bilan détaillé](../artifacts/testing/amont_three_targets_20261010/bilan.md)
conserve les sources, formules, conditions, commandes et contrôles.

- **T1, 042342/Gien :** utiliser les semaines de mouvements exploitables,
  même si une autre semaine contient une sortie de signe ambigu. Un zéro
  explicite remplace l'estimation ; une semaine absente ne le fait pas.
  Le complément hebdomadaire `max(0, consommation source J − BOM exécutée)`
  réduit l'écart de stock de 41 %, mais conserve des doubles comptes de
  calendrier et augmente les retards matière. Essai explicatif, non adopté.
- **T3, 338929/Avène :** sur les seules semaines documentées,
  `nouveau complément = max(0, J cumulé − BOM exécutée cumulée − compléments
  déjà demandés)`. Inclure les demandes encore en retard dans le dernier
  terme évite de les demander deux fois. L'écart de stock baisse de 10 %,
  mais les consommations propres ultérieures ne peuvent annuler des sorties
  déjà exécutées : l'excès final reste explicite (170 400 UN). Cette règle
  rétrospective n'est pas une prévision autonome du MRP.
- **T2, 693055/Gaillac :** conserver 10 kg physiques hors disponible MRP
  dégrade l'écart de 887 à 1 309 kg par effet de seuil du lot de 600 kg.
  Le résultat ne permet ni de retenir cet essai comme amélioration, ni
  d'affirmer que ces 10 kg sont industriellement utilisables.
- **T4, 693055/Gaillac–Avène :** transport physique testé à un jour au lieu
  de sept, sans changer traitements, sécurités ou standard. Gain faible
  (887 à 874 kg à Gaillac) ; la durée d'un jour n'est pas démontrée.

Les livraisons clients simulées restent identiques. Le calendrier de
production et certains stocks PF changent ; leurs effets sont vérifiés
séparément. Aucun essai n'est promu comme nouvelle référence. Les quatre
qualifications natives restent refusées sur les demandes et événements F3
reconstitués, malgré les contrôles arithmétiques indépendants réussis.

### Audit du 11 octobre : candidats à vérifier, sans changement du moteur

L'[audit de 693055/Gaillac et 042342/Gien](../artifacts/testing/deep_693055_042342_20261011/bilan.md)
rapproche toutes les semaines et versions MRP des calculs existants.

- **Prévision d'une matière partagée :** le total industriel I connu doit
  être rapproché des besoins propres et engagements sur les mêmes périodes.
  Pour 042342, `BOM prévue + 46,386 % de I` ne conserve pas ce total lorsque
  la production simulée évolue. La candidate `complément = max(0, I − propre)`
  exige encore de distinguer engagements et prévisions révocables, ainsi que
  les besoins décalés entre semaines. Une semaine absente n'est pas un zéro.
  L'ajout rétrospectif des sorties ne répare pas cette anticipation.
- **Fabrication et transport :** le lot fabriqué de 600 kg pour 693055 ne
  démontre pas un multiple physique de transfert. Les sources annoncent
  puis enregistrent 1 190 kg entre Gaillac et Avène. Un départ doit être
  contraint par le disponible et par les règles logistiques documentées,
  sans copier automatiquement le lot de fabrication.
- **Étapes et engagements :** garder distincts lancement, fin physique,
  libération, expédition et réception. Les 28 jours source à Gaillac ne sont
  pas supprimés ; trois bilans hebdomadaires sont incompatibles avec une
  attente de 28 jours après leur entrée H au même périmètre. Les fabrications
  devenues fermes doivent rester liées au besoin aval lors des révisions.
  Aucun I local 693055/Gaillac n'est actuellement branché dans le graphe :
  le plan est dérivé d'Avène, même si les sources locales sont disponibles.

Ces constats définissent les prochains essais. Aucun candidat n'est adopté,
aucune simulation nouvelle n'est produite et les refus F3 restent conservés.

Les règles implémentées se lisent dans
[mrp_planning.py](../simulation/engine/mrp_planning.py) :
`plan_dated_requirements`, `plan_anticipated_requirements`,
`plan_with_stock_protection`, `plan_sourced_requirements`,
`plan_allocated_purchase_requirements`, `reconcile_industrial_requirements`
et `InternalTransferCommitments`.

Le raccord aux mouvements physiques est dans
[run_first_simulation.py](../simulation/engine/run_first_simulation.py) :
`plan_component_network`, `customer_physical_cover_need`,
`finished_goods_dispatch_need`, `dated_supply_release_calendar`,
`dated_production_release` et la boucle quotidienne.

Les paramètres exacts viennent du [graphe de référence C](../artifacts/testing/customer_comparison_20261005/graph_C.json),
de la [recette d'avancement A et du témoin R](../artifacts/testing/mrp_transfer_advance_20261005/study.py)
et des sources citées dans leurs métadonnées. Les résultats de A doivent être lus
dans [son bilan de qualification](../artifacts/testing/mrp_transfer_advance_20261005/bilan.md) ; une règle correctement calculée ne garantit
pas, à elle seule, la reproduction du comportement industriel.

### Essais du 11 octobre après l'audit : prévision, transfert et engagements

Sept calculs 2025 et leurs contre-vérifications sont décrits dans le
[bilan des corrections testées](../artifacts/testing/mrp_refinement_20261011/bilan.md).
La [comparaison interactive](../resultats/mrp_refinement_20261011/comparaison_amont.html)
conserve les stocks et flux industriels, H2 et les essais séparés. Aucun essai
ne remplace globalement la référence acceptée.

- **Prévision d'un composant partagé :** sur les semaines sources connues et
  documentées, `besoin prévu = max(I industriel, besoin déjà engagé)`.
  Remplacer le prévisionnel révocable, conserver les engagements et la réserve
  distincte. Une absence conserve le repli ; un zéro documenté reste un zéro.
  Appliquée seule à 042342/Gien (R1), cette règle dégrade les stocks ; combinée
  au rapprochement physique antérieur T1 (R4), elle les rapproche. Ce n'est
  pas une preuve que la consommation physique est correcte.
- **Rapprochement historique cumulatif, R5 :**
  `complément nouveau = max(0, cumul sorties Scan3 − cumul BOM propre − cumul
  compléments déjà demandés)`, sur les mêmes semaines exploitables seulement.
  Inclure les compléments non encore servis dans le dernier terme, pour ne
  pas les demander deux fois. La donnée devient connue à la clôture de sa
  semaine ; les semaines absentes ne fournissent pas de zéros. Cette règle
  évite le surcompte de décalages entre semaines, mais reste un rejeu de
  consommation, pas une prévision autonome des autres produits.
- **Fabrication et transfert :** le contrat du moteur accepte désormais
  `transfer_multiple_qty = 0`, avec provenance obligatoire, pour exprimer
  l'absence de quantum de transport. Le lot de fabrication reste distinct.
  L'essai R2 conserve 600 kg par fabrication de 693055 et tous les délais :
  il améliore Avène, dégrade Gaillac et fragmente les transferts. Le nominal
  n'est pas changé par cette extension du contrat.
- **Engagement et avancement :** R7 conserve les engagements de fabrication
  vers transfert, mais peut bloquer des départs pourtant réalisables. R8
  avance la partie expédiable du même engagement, conserve son reliquat et
  décompte une seule fois au départ. Il corrige cette régression, sans
  améliorer 693055 par rapport à H2 et en dégradant les stocks de 773474.

Le plan MRP local 693055/Gaillac ne pilote toujours pas directement sa
fabrication. Son raccordement doit conserver les liens entre besoins aval,
fabrications et transferts engagés : additionner I local au besoin dérivé
d'Avène ferait double compte. Les 28 jours ouvrés ne sont pas supprimés ni
transformés arbitrairement en durée physique de fabrication. Le jalon des
entrées source et le périmètre des encours restent à clarifier.

Les contrôles ciblés et les rapprochements CSV sont concluants ; les refus
natifs portant sur les demandes/événements F3 reconstitués restent signalés.
La revue JavaScript en mémoire ne constitue pas une vérification navigateur.

### Raccordement expérimental du MRP local de Gaillac — 11 octobre

Le calcul commun propage déjà les besoins d'Avène vers Gaillac. L'extension
`manufactured_output_mrp_policy`, inactive par défaut, permet de rapprocher
ces besoins du calendrier industriel **I de la sortie fabriquée à Gaillac**.
Elle utilise le même calcul de besoins nets, les mêmes stocks, lots, délais,
sécurités et nomenclatures. Elle ne crée pas un second moteur de simulation.

Le [protocole local/commun](../artifacts/testing/gaillac_local_global_20261011/protocole.md)
décrit les essais isolés L0, L et G, sur la base R5. Seul 693055/Gaillac est
activé ; 773474 et les produits finis servent de contrôles. Ces candidats
ne sont pas adoptés automatiquement dans la référence.

À chaque calcul, sélectionner les besoins I connus et les semaines
explicitement fournies. Une semaine nulle reste couverte ; une semaine
absente garde le repli du réseau. Conserver la convention existante qui
exclut le bucket courant d'une nouvelle version MRP. La série est convertie
de KG source en G internes, avec une cellule source pour chaque quantité.

Sur les semaines couvertes, noter `C` les sorties/transferts fermes restant
à servir, et `D` les besoins aval encore modifiables, aux dates de départ
de Gaillac. Les fabrications actives sont des réceptions à venir : elles ne
font pas partie de C. Rapprocher I et C une seule fois en ordre de date ;
garder les dates et identités de C. Cette allocation de quantité est une
hypothèse FIFO, pas l'identification des ordres industriels.

- **L, calendrier local :** `besoin = C + reste de I après rapprochement`.
  Ce reste remplace D sur la couverture connue.
- **G, rapprochement commun :** garder C et construire
  `prévision cumulée(t) = max(cumul du reste I(t), cumul D(t))`.
  Les accroissements de cette courbe sont les nouveaux besoins datés.
  Ainsi, 600 kg locaux en semaine 1 et les mêmes 600 kg aval en semaine 2
  ne produisent pas artificiellement 1 200 kg de besoin.

Les fragments rapprochés conservent le lien au besoin aval d'origine ; un
excédent local n'invente aucune destination. Le rapprochement ne modifie
pas implicitement une date ferme de transfert. L0/L/G gardent la politique
optionnelle d'engagements internes désactivée, comme R5, pour mesurer
uniquement l'effet de ce raccordement. Un export des décisions avant et
après départ permet une contre-vérification indépendante.

Le premier L exécuté révèle une limite de ce rapprochement restreint aux
semaines renseignées : les besoins décalés sur d'autres semaines s'ajoutent
encore à I. Le G initial reste donc préparé mais non exécuté. Le second
essai commun **G2** étend le maximum cumulatif à **tous les D révocables du
snapshot**, y compris les semaines sans I et les besoins déjà dus ; aucun
D hors couverture n'est rajouté ensuite. Une absence de I ne supprime pas D.
Le rapprochement des C reste inchangé. Cette règle suppose un même flux
global entre I et D ; elle ne prouve pas l'identité de commandes ni un usage
local supplémentaire. Les chiffres, résultats et révisions sont conservés
dans le protocole expérimental, sans réécrire les preuves du premier L.

**Résultat de ces essais : R5 est conservé.** L2 rejoue exactement L sur le
code final. L'écart moyen de stock 693055/Gaillac passe de 887 kg dans R5 à
3 118 kg dans L et 2 691 kg dans G2. Le maximum sur tout l'horizon corrige
l'addition initiale de 17 400 kg en revenant à 10 800 kg, mais les dates de
fabrication et de transfert ne sont pas replanifiées simultanément. G2 ajoute
encore trois lots de 600 kg par rapport à R5, sans gain de service client.
Le besoin industriel local est donc raccordé dans les essais ; ce raccordement
ne constitue pas encore une synchronisation complète entre sites. Les délais
de contrôle ne sont pas supprimés. Voir le [bilan chiffré et les preuves](../artifacts/testing/gaillac_local_global_20261011/bilan.md).

La [contre-analyse suivante](../artifacts/testing/gaillac_coordination_20261011/bilan.md)
précise la limite : les 2 100 kg de stock réseau moyen supplémentaires de G2
proviennent de fabrications supplémentaires, pas du seul emplacement du stock.
Avancer un transfert ne suffit pas à les supprimer. I local n'est pas le reste
à servir de la simulation : après un départ, D peut baisser alors que I persiste.
Tant que les flux ne sont pas identifiés durablement, garder le besoin aval net
comme autorité de quantité ; ne pas ajouter I brut ni soustraire arbitrairement
tous les départs de ses versions futures. Les contrôles R5 bornés ne prouvent
ni oubli du détenu/OF ni double application du délai de 28 jours. Aucune nouvelle
règle n'est adoptée par cette contre-analyse.

### Revalidation avant fabrication à Gaillac — essai P1 du 11 octobre

**R5 reste la référence.** Avant chaque nouvelle campagne proposée pour
693055/Gaillac, P1 reconstruit les besoins datés du réseau à partir de l'état
courant et refait le calcul de lancement. Une quantité encore nécessaire
peut être différée si sa date se décale. Le nouveau plan et sa quantité sont
adoptés ensemble ; une hausse est permise, sans plafonnement artificiel au
résultat précédent. Les campagnes engagées et les jours où aucun lancement
n'est proposé ne sont pas modifiés. Aucun calendrier de dates n'est codé en dur.

Lots, sécurités et délais restent ceux de R5, dont les 28 jours ouvrés de
693055. Le recalcul inclut le besoin courant du rejeu historique hebdomadaire :
ce besoin est connu dans le modèle, sans preuve qu'il l'était avant lancement
chez l'industriel. Ce n'est pas un simple rafraîchissement du stock disponible.

Sur 2025, l'écart absolu moyen de stock Gaillac passe de **887 à 876 kg**
(−1,26 %). Parmi 52 photos, 3 s'améliorent, 2 se dégradent et 47 ne changent
pas. Les 22 lots de 600 kg, les départs annuels et le stock final de 1 800 kg
restent identiques ; Avène, les productions PF et le service client ne changent
pas. Cette correction de calendrier ne résout donc pas l'écart principal.

Le prototype reste isolé et non promu. Les vérifications indépendantes des
flux passent, tandis que les refus natifs F3 et un défaut préexistant de statut
de campagne demeurent explicitement signalés. Voir le
[bilan, la comparaison et les preuves](../artifacts/testing/gaillac_prelaunch_20261011/bilan.md).

### Diagnostic des étapes physiques et du rapprochement — 11 octobre

**Aucune nouvelle règle promue ; R5 est conservé.** La comparaison du seul stock
total cachait un écart d'état : pour 693055/Gaillac, J futur du MRP source
(stock déjà présent, disponible plus tard) vaut en moyenne 565 kg sur 52 plans,
contre 1 385 kg détenus dans R5. J courant vaut 519 kg, contre 369 kg disponibles.
Trois semaines sources fermées nécessitent qu'au moins 590 kg reçus repartent
dans la semaine. L'ensemble « chaque H est une première entrée physique puis
subit 28 JO, les photos couvrent tout ce stock » est donc incompatible avec
ces observations. Cela ne justifie ni de supprimer les 28 JO, ni de masquer
le détenu : il faut raccorder les étapes fabrication, entrée physique et
disponibilité. Déplacer tous les nouveaux détenus avant H ne suffit pas non plus.

Le complément historique hebdomadaire `max(0, Scan3 − BOM exécutée)` crée un
autre biais lorsque les fabrications changent de semaine : +3 426 kg de
consommation 773474/Gien sur ses 43 semaines documentées. Ce biais est nul
pour 693055/Avène sur ses 48 semaines documentées ; il ne faut pas lui attribuer
le problème Gaillac. 042342 utilise déjà le rapprochement cumulatif dans R5.
La correction à évaluer doit conserver les consommations irréversibles,
déduire les compléments déjà demandés, et traiter séparément la prévision.

Audit et contre-calculs en lecture seule, sans nouvelle simulation ni changement
du moteur. Les refus de qualification F3 antérieurs restent ouverts. Voir le
[diagnostic détaillé, les sources et les preuves](../artifacts/testing/gaillac_root_cause_20261011/bilan.md).

### Gaillac : essais du cumul, de la prévision et du transport — 11 octobre

Trois variantes ont été exécutées sur 362 jours, avec graphes séparés et R5
conservé. **Aucune n'est promue comme nouvelle référence globale.** Le
[bilan et la comparaison](../artifacts/testing/gaillac_cycle_trials_20261011/bilan.md)
donnent les résultats, sources et preuves.

- **C1, complément historique cumulatif :** sur la couverture documentée,
  `complément nouveau = max(0, cumul Scan3 − cumul propre exécuté − compléments déjà demandés)`.
  Les demandes en attente sont déjà comptées ; les consommations sont
  irréversibles. Une semaine absente n'est pas un zéro. Ce rapprochement
  historique retire 3 426 kg supplémentaires de 773474/Gien et 12 865 kg de
  038005/Gien. Il ne prédit pas de façon autonome les usages hors BOM.
- **C2, prévision hebdomadaire source :** I remplace les prévisions révocables
  sur les semaines couvertes ; les engagements datés restent conservés,
  `complément prévu = max(0, I − engagements)`. Réserves et semaines absentes
  sont traitées séparément. La même règle est testée sur les neuf couples E4.
- **C3, trajet court isolé :** 693055 Gaillac–Avène passe de 7 à 1 jour et
  773474 Gaillac–Gien de 10 à 1 jour, sans changer les contrôles 7/6 JO ni les
  disponibilités Gaillac 28/33 JO. Un jour est une sensibilité motivée par
  les rapprochements hebdomadaires, pas une mesure industrielle.

Les écarts moyens 693055/Gaillac sont R5 **887 kg**, C1 **887**, C2 **899**,
C3 **874**. Pour 773474/Gaillac : **6 031 / 5 477 / 5 415 / 6 215 kg** ;
à Gien : **5 329 / 5 761 / 6 007 / 5 663 kg**. Une amélioration locale ne
constitue donc pas une amélioration de la chaîne entière.

La reconstitution source montre que chaque entrée H de 693055 ne peut pas
uniformément commencer 28 JO d'attente : trois semaines imposent chacune
au moins 590 kg nouvellement entrés puis sortis dans la même semaine. D'autres
entrées semblent rester différées, sous réserve d'un périmètre commun entre
photos et stock J du MRP et de l'absence de reblocage d'un stock déjà utilisable.
Sous ces conditions, aucune séparation constante avant/après H ne reproduit
toutes ces observations. La borne physique des 590 kg ne dépend pas du
non-reblocage. Ce constat ne justifie ni de supprimer
les 28 JO, ni d'en faire une durée physique via `tau_process`.

Pour 773474, les 29 H positifs de 6 400 kg laissent chacun un écart de
−3 200 kg au bilan photos/sorties. Le brut et l'entrée reconstituée restent
séparés : doublon, sortie absente ou périmètre différent ne sont pas départagés.

Les essais déclarent `formats_reconciled_execution` avant lancement.
La qualification reconstruit indépendamment chaque complément à partir des
consommations BOM réellement exécutées, de la couverture source, du mode
hebdomadaire/cumulatif et des demandes antérieures. Elle vérifie quantité,
identité, provenance et absence d'exécution anticipée, en conservant les
contrôles de stock, disponibilité, service, unités et backlog. La convention
partielle d'ouverture de R5 est conservée et exclue des bilans de semaines
complètes. Un succès de qualification ne certifie pas la calibration.
