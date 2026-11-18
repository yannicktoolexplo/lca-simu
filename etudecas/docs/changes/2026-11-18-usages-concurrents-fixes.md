# Comparer les lancements avec les mêmes besoins concurrents

Étude du 18 novembre 2026, départ `a8ac63fed`, du 1er janvier au 1er juin 2025.
La référence `coherent-MRP-20261014` reste conservée. Les deux options étudiées
sont expérimentales ; aucune n'est activée par défaut.

## Question et intervention

La [comparaison précédente](2026-11-18-applicabilite-substitutions.md) améliore
localement le calendrier de 268967. Mais elle diminue aussi de 1 393 900 unités
le besoin reconstruit des autres usages de 042342. Le déplacement de notre
production change ce résidu : le gain ne peut donc pas être attribué à la seule
règle de lancement dans une comparaison à demandes concurrentes constantes.

Le nouvel essai fixe les mêmes **quantités demandées**, aux mêmes dates de
clôture et de connaissance, dans les deux variantes. Le profil provient du
témoin v2 conservé : 206 clôtures, dix couples article/site, dont trente demandes
explicitement nulles. Il ne rejoue ni les consommations servies ni les anciens
besoins en attente. Ces derniers sont recalculés par le registre natif.

Les prévisions, observations directes et besoins concurrents déjà présents dans
le graphe restent identiques. Les quantités fixées sont publiées après la
production propre du jour ; elles ne sont pas introduites dans une prévision
antérieure. Le contrôle porte sur l'ensemble des **27 couples × 152 jours**, et
non sur le seul total de 042342.

La seule différence entre les deux nouveaux calculs est la politique de
lancement : `known_dated_priority_v2` ou `known_dated_substitution_v3`. Avant de
lancer v3, le témoin avec profil fixe doit reproduire numériquement l'ancien
témoin : productions, stocks, flux, service, commandes et décisions matière.
Les différences de provenance sont explicites, sans exiger une identité
textuelle entre des exports de schémas différents.

## Preuves et limites de l'expérience

Le [protocole](../../artifacts/testing/usages_concurrents_fixes_20261118/protocol.json)
fixe avant exécution deux calculs séquentiels de 152 jours, limités chacun à
3 600 secondes et 4 Gio de mémoire, avec 6 Gio de stockage pour l'étude. Aucun
calcul annuel supplémentaire n'est prévu. Les sources sont gelées après les
65 tests ciblés en mémoire, le contrôle d'environnement et la revue indépendante
de préparation (81 vérifications). Le profil a été contrôlé séparément sur
2 562 points ; l'oracle de reconstruction historique compte 181 vérifications.

Le nouveau témoin termine en 373,33 secondes. Sa qualification native passe,
ainsi que la revue physique indépendante (424 594 contrôles). Le rejeu retrouve
les quantités, dates, commandes et décisions de l'ancien témoin : 54 des 57 CSV
sont même identiques octet par octet.

La première comparaison stricte est conservée en refus. Son diagnostic établit
que les différences restantes portent sur la provenance, 28 arrondis de l'audit
cumulatif en grammes ou kilogrammes (au plus 1,7 × 10⁻¹⁰), et l'ordre de blocs
de composants dans les traces de décisions. La revue finale distincte compte
13 443 contrôles réussis : elle conserve l'ordre des événements physiques et
l'ordre interne de chaque composant, compare tous les champs de décision et
borne uniquement ces arrondis descriptifs par la précision des nombres
exportés. Aucune tolérance n'est ajoutée aux unités physiques et aucune
nouvelle simulation du témoin n'est nécessaire.

Ce profil reste une **hypothèse commune issue d'un témoin simulé**, pas un carnet
industriel indépendant. Le fixer rend la comparaison plus interprétable ; cela
ne transforme pas son attribution aux autres usages en fait observé. Les écarts
entre retraits sources, production propre et besoins fixés sont conservés avec
leur signe, sans correction artificielle.

La production réelle utilisée pour la comparaison est estimée par les retraits
d'étuis : treize semaines renseignées pour 268967, vingt et une pour 268091,
et vingt-deux photographies de stock par produit. Une semaine absente reste
inconnue. Les sept premières fenêtres de retraits partiellement couvertes sont
conservées selon la convention du témoin, sans changement de périmètre dans
cet essai. Capacité quotidienne, calendrier industriel et dates de
comptabilisation restent à départager.

Les index documentaires générés de cinq domaines sont périmés et exclus du
contrôle technique ciblé. Aucun navigateur, suite globale ni test d'altération
de fichiers n'est exécuté.

## Résultat : le gain précédent subsiste, sans gain supplémentaire

Le candidat termine en 428,53 secondes, soit 801,86 secondes pour les deux
simulations. Les deux qualifications natives passent. La revue indépendante
du candidat compte 444 211 contrôles ; l'égalité des demandes concurrentes,
121 290 ; la contre-comparaison, 3 727. Toutes passent avec des sources stables.

Les 4 104 demandes quotidiennes sont identiques. Les quantités consommées par
les autres usages et leurs attentes agrégées restent également identiques.
L'ancien effet de diminution des besoins concurrents est donc bien supprimé
de cette comparaison.

| Mesure | Témoin v2, profil fixe | Candidat v3, même profil |
|---|---:|---:|
| 268967 : erreur moyenne sur 13 semaines renseignées | 29 319,62 UN | 27 595,38 UN |
| 268967 : écart de production cumulé sur ces semaines | +35 915 UN | +13 300 UN |
| 268967 : nouveaux produits finis terminés | 431 200 UN | 431 200 UN |
| 268967 : travail exécuté dans le dernier lot inachevé | 61 600 UN | 61 600 UN |
| 268967 : erreur moyenne de stock à D1920 | 82 525,32 UN | 82 525,32 UN |
| 268091 : erreur moyenne sur 21 semaines renseignées | 84 871,19 UN | 84 871,19 UN |
| 268091 : erreur moyenne de stock à D1920 | 289 163,27 UN | 289 163,27 UN |
| Coût d'immobilisation connu, sous-total du réseau | 679 116,5248 | 679 135,7213 |

Le gain de **5,88 %** sur l'erreur hebdomadaire de 268967 est le même que dans
l'essai précédent. Le nouveau test le confirme à demandes concurrentes
identiques ; il ne constitue pas un rapprochement supplémentaire.

Le quatrième lot démarre le **1er mai au lieu du 28 avril**, évite les arrêts
des **7 et 8 mai**, et termine toujours le **20 mai**. Les trois premiers lots
restent inchangés. Les cinq lots de 268967 sont explicitement admis par le
contrôle ; celui-ci ne se contourne plus à cause de la substitution configurée.
Les 39 admissions positives des deux produits concordent avec le travail
exécuté sur les jours présents dans l'essai. Le cinquième lot de 268967 est
encore incomplet à la fin : sa fin projetée au 9 juin n'est pas une réalisation
vérifiée. Le 1er mai ouvré reste une hypothèse du calendrier utilisé.

| Semaine du | Production réelle estimée | Témoin | Candidat |
|---|---:|---:|---:|
| 28 avril | 15 500 UN | 38 500 UN | 15 400 UN |
| 5 mai | inconnue | 15 885 UN | 38 500 UN |
| 19 mai | 24 500 UN | 38 015 UN | 38 500 UN |

Le calendrier de la semaine du 28 avril se rapproche nettement du renseignement
industriel, tandis que la semaine du 19 mai se dégrade de 485 unités. Les
22 615 unités déplacées sur la semaine inconnue du 5 mai empêchent de conclure
que tout le mois est mieux reproduit.

Les stocks quotidiens physiques et utilisables de D1920, les disponibilités
et les livraisons clients sont identiques. Les trajectoires de 268091 restent
inchangées. L'immobilisation connue augmente de **19,1965** unités monétaires
du modèle ; les achats externes connus diminuent de **0,3426**. Ces sous-totaux
ne valorisent pas tous les stocks, notamment les produits finis à D1920.

## Ce qui reste non expliqué par les données

Pour 042342, les quinze fenêtres de retraits documentées couvrent 105 jours,
avec dernière clôture le 25 mai. La consommation propre passe de 18 585 338 à
19 979 238 unités dans ces fenêtres, et de 11 151 202 à 9 757 302 hors de ces
fenêtres. Son total sur les 152 jours reste **29 736 540 unités** dans les deux
cas.

La cible cumulée documentée (134 124 997 unités) et le besoin résiduel fixé
(115 539 659) restent identiques. L'écart « retrait documenté moins consommation
propre moins besoin fixé » passe donc de zéro à **−1 393 900 unités** à cette
dernière clôture documentée. Ce n'est ni une perte physique ni une dette : il
mesure la limite de correspondance avec les fenêtres industrielles lorsque
la production est déplacée tout en maintenant un profil concurrent commun.
L'écart est conservé, pas compensé artificiellement.

La règle de lancement évite un démarrage prématuré dans cet essai. Elle ne
suffit pas à expliquer l'ensemble de la production industrielle. La prochaine
cible reste de départager **capacité réellement disponible, calendrier de
travail et date d'enregistrement des retraits**, sur un bloc court de 2025,
avec ces besoins concurrents constants. Les prévisions révisées et les ordres
figés restent des causes possibles d'écart de volume, distinctes du calendrier
de fabrication. Aucune capacité arbitraire par référence ni observation future
n'est introduite ici.

La [comparaison HTML](../../resultats/usages_concurrents_fixes_20261118.html)
présente les courbes et les écarts. Le
[manifeste final](../../artifacts/testing/usages_concurrents_fixes_20261118/final_manifest.json)
relie les exécutions, qualifications, revues et limites ; le refus strict
initial est conservé séparément. La référence nominale n'est pas promue.
