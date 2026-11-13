# Référence 01 : risques dépendant de l'état et pilotage V3

L'utilisateur a précisé que la carte à reprendre est
[`01_demonstration_complete.html`](../../resultats/01_demonstration_complete.html),
en laissant les lots de côté. Le travail sur la comparaison 2×2 du meeting
historique ne désignait pas cette référence.

## Référence retrouvée et conservée

Le fichier autonome, assemblé le 15 septembre 2026, contient neuf vues et
50 ressources embarquées. Son empreinte est
`53ef56c1dd72061ee15553da67012a154d0d7d91d065e7738574ca5aeb86e2a7`.
L'entrée pertinente est `views/carte_reseau_lots.html`, malgré son nom : son
explorateur de risques fonctionne indépendamment des fonctions de lots.
Son empreinte embarquée est
`b25664a3fc2e143acf626c75aeca0ee7214c901ab43860287a8200a856fa7481`.

Cette vue réunit les risques fournisseurs déclenchés par l'état et le pilotage
continu `canonical_state_feedback_v3_continuous_t_plus_1`. Sa source est
`paired_mrp_vs_v3_all_nodes_full_20260828_v2/canonical_feedback/seed_320270`,
sous `C:/dev/lca-simu-pr40-validation-artifacts-20260726/`.

Le calcul historique couvre 365 jours après 60 jours de mise en régime :
88 événements uniques, 63 appliqués, 365 décisions V3 et 348 actions physiques.
Le superviseur observe l'état chaque jour, confirme les changements sur trois
jours, réexamine normalement le régime tous les sept jours et le maintient
au moins quatorze jours, avec les exceptions d'urgence prévues par sa politique.
Les commandes agissent au lendemain de l'observation. Ces chiffres restent
ceux de cette réalisation historique.

Les vues qualité, retard et comparaison de solutions de la même enveloppe
proviennent d'autres calculs. Les compteurs configurés de la carte historique
doublent aussi certaines sources : 176 occurrences ne représentent pas
176 événements uniques. Deux chronologies rapprochent des reports ou retards
antérieurs à une application locale ; ces associations ne prouvent pas une
cause individuelle.

## Fonctionnement à reprendre

La nouvelle vue reprend l'interface native de risques de `01` : choix d'une
cascade, filtres par famille et niveau de propagation, recherche, surbrillance
des nœuds et flux, valeurs et seuils des déclencheurs, effets appliqués,
diagramme et chronologie, graphiques d'intensité, étendue, production et service.
Les descriptions sont métier, les unités explicites et les noms commerciaux
de médicaments ne sont pas utilisés. Aucun développement de suivi de lots
n'est demandé dans cette phase.

Le fichier `01` original et les cartes nominales précédentes restent conservés.
Les données anciennes restent identifiées comme historiques. Une nouvelle
réalisation doit conserver les stocks et ordres de janvier, les règles MRP et
les sécurités du nominal actuel. La mémoire du contrôleur se construit alors
depuis J0 : copier les 60 jours de mise en régime de l'archive changerait les
conditions initiales.

Livraison précédente avec l'enveloppe complète, conservée :
[`01_demonstration_complete_risques_etat_20261113.html`](../../resultats/01_demonstration_complete_risques_etat_20261113.html).
L'enveloppe d'origine ouvre la nouvelle carte de risques par défaut et conserve
ses 50 ressources historiques sans modification. Le contexte nominal actuel
reste disponible dans la carte, distinct de l'essai de risques de 56 jours.
La [vue de risques historique restaurée seule](../../resultats/01_reference_risques_etat_historique_20261113.html)
permet aussi de consulter directement la réalisation annuelle ancienne.

La contre-revue finale passe 34 contrôles statiques, 28 contrôles JavaScript V8
sur les vrais gestionnaires de clic/filtres et 23 rapprochements indépendants
du témoin. Les axes des quatre graphiques de risques couvrent seulement
J0–J55, avec les dates du 01/01 au 25/02. Les 48 blocs compressés du nominal
restent identiques. V8 utilise un DOM simulé : ce n'est pas une vérification
visuelle du navigateur. Preuve : `validator/current_map/manifest.json`.

## Carte seule et accès à toutes les occurrences

À la demande suivante de l'utilisateur, la livraison à ouvrir devient la
[carte seule](../../resultats/carte_cascades_etat_20261113.html), sans l'enveloppe
de présentation et ses autres vues. Le réseau et ses interactions de risques
restent disponibles ; aucun nouveau suivi de lots n'est développé.

L'audit des identifiants constate que les données embarquaient déjà les
135 incidents du calcul, couverts par 133 racines et 47 parcours regroupés.
Le sélecteur proposait uniquement les parcours et la recherche n'incluait pas
l'identifiant de l'incident. Deux plafonds silencieux limitaient également les
listes à 80 et 120 éléments, même s'ils ne tronquaient pas les 47 parcours présents.

La correction conserve les parcours et ajoute une vue de chaque incident,
recherchable par son identifiant natif, sans additionner les deux représentations.
Les valeurs et les données de simulation restent identiques. Les preuves de
cette modification d'affichage sont séparées dans
`etudecas/artifacts/testing/carte_cascades_seule_20261113/`. Elles distinguent la
nouvelle révision d'interface de la révision native ayant produit les résultats.

Le fichier fourni `data/source/Exemple chaine causale.xlsx`, feuille `Template`,
contient également 21 lignes décrivant des chaînes : 18 risques, deux mesures
de protection et un exemple illustratif. Toutes les lignes `A2:L22` sont
consultables séparément sur la carte, avec leurs conditions, effets décrits et
cellules source. Ce catalogue n'ajoute aucun incident aux 135 événements simulés.
Il ne reçoit ni date d'occurrence ni intensité inventée. Vingt entrées ont au
moins un acteur explicitement raccordable au réseau ; les transporteurs
génériques, la mention Floride et le fournisseur fictif `VDXXX` restent signalés
lorsqu'ils ne sont pas raccordés. La présence d'une chaîne documentée ne prouve
pas qu'elle s'est réalisée. Le fichier source fourni est conservé sans modification.

Les contrôles de cette livraison passent : génération du gabarit en mémoire,
158 contrôles V8 des modes et sélections natifs (dont un jeu de 151 incidents,
au-delà des anciens plafonds), 93 contrôles V8 du catalogue et 160 contrôles
indépendants des cellules et raccordements. Le fichier livré a pour SHA-256
`4a7319fd7e5ff5087e87e41153cc55b6d1c0230fb22392d1ed9ddec7775f58b2`.
Les premières attentes erronées du harnais sur le tri et un espace final Excel
restent conservées comme refus d'oracle ; les contrôles corrigés comparent les
clés réellement triées et les cellules brutes, sans modifier les données évaluées.
Le navigateur n'est pas exécuté. La qualification scientifique globale de
l'ancien calcul reste refusée ; aucune nouvelle simulation n'est lancée pour
cette modification d'affichage. Le bilan borné est dans
`artifacts/testing/carte_cascades_seule_20261113/final_manifest.json`.

## Onglet nominal et parcours complet sur la carte

La livraison suivante est la
[carte Nominal et Cascades](../../resultats/carte_nominal_cascades_20261113.html).
Elle montre seulement ces deux onglets, avec les gestionnaires natifs. Le nominal
conserve ses 48 blocs de données, ses 1 825 jours et ses observations de 2025.
Entrer dans cet onglet efface la sélection d'incident et les surbrillances
documentaires, ferme leurs fenêtres et masque le panneau de parcours. Le mode
risques conserve ses données propres de 56 jours.

Le tracé précédent était limité pour des raisons identifiées : aucun des
135 incidents ne renseigne de produit fini ou client aval observé ; la fermeture
diagnostique dépendait de ces champs et s'arrêtait à trois niveaux ; le cadrage
restait global. Les 133 racines diagnostiques et 47 parcours sont des regroupements,
pas une généalogie d'incidents : chaque `causal_root_id` natif est son propre
identifiant d'incident.

Le nouveau panneau, visible sur la carte, complète le trajet par les recettes
déjà embarquées dans `json_panel` et les liaisons du modèle. Il conserve le couple
site/article : transport du même article, puis changement d'article uniquement
par une recette à lot et ratios d'entrée positifs. Les couples déjà visités
arrêtent les cycles, sans couper arbitrairement le parcours à trois étapes.
Les champs `from/to/items` définissent les routes ; leurs anciens identifiants
contenant `DC-1910` ne remplacent pas la destination actuelle `DC-1920`.

Exemple : l'intrant 338928 à Avène rejoint le produit fini 268091, puis Muret
et le client ; il ne rejoint pas arbitrairement le produit fini 268967 de Gien.
Le produit 038005 à Gien suit au contraire la recette de 268967. Les liaisons
locales renseignées sont en trait plein ; la suite structurelle possible est
en pointillés. Ce dessin n'attribue aucune rupture client à l'incident : les
flux physiques des deux témoins restent identiques sur les 56 jours calculés.

Le cadrage suit la sélection et réserve une zone géographique hors du panneau
de parcours. Un fournisseur sans coordonnées, `SDC-VD0956464A`, reste présent
dans le panneau avec « localisation inconnue » ; aucune position n'est inventée.
Les 135 incidents, les 47 parcours et les 21 chaînes documentées sont conservés.

Les preuves de cette retouche d'affichage sont dans
`artifacts/testing/carte_nominal_cascades_20261113/`. La vérification porte sur
le graphe et les vrais gestionnaires JavaScript sous DOM simulé, pas sur un
rendu navigateur. Le style des liens est compatible avec la version Plotly
2.32.0 embarquée ([attributs officiels de cette version](https://github.com/plotly/plotly.js/blob/v2.32.0/src/traces/scattergeo/attributes.js#L99)).
Aucune simulation, donnée industrielle ou recette n'est modifiée.

## Compatibilité exécutée sur le code courant

La configuration V3 exacte a été retrouvée dans le snapshot de provenance
`canonical_frequency_v3_closed_loop_actuator_pilot_20260827_run5`.
Son SHA est `bc871f02baecd4882092cf9022d58355a2cfeaa83dbf70142e5d2432715c3509`.
La configuration actuelle a un SHA différent à cause des fins de ligne :
les JSON sont égaux et les octets deviennent identiques après normalisation
CRLF/LF en mémoire. Aucun réglage n'est ajusté pour obtenir une courbe.

Le premier rejeu a été refusé avant J0 : la règle courante
`physical_demand_cover_v1` interdit globalement les contrôleurs actifs. Aucun
résultat courant n'a été produit par cette tentative et les preuves du refus
restent conservées.

Le raccord implémenté est limité au profil V3 d'origine : les multiplicateurs
de commande, sécurité et objectif de production restent positifs et au plus
égaux à un ; les canaux délai, expédition accélérée, capacité, recours externe
et priorité restent neutres. La compatibilité est déduite de tous les
playbooks, du repli et de la loi continue validés, sans autorisation générale
de V3, sans liste d'articles et sans désactivation de la couverture physique.
Les contrôleurs génériques, V1/V2, sondes et profils agressifs restent refusés.

Le témoin nominal de quatorze jours conservé avant modification et celui
recalculé après modification ont **48 CSV physiques et économiques strictement
identiques**, avec les mêmes indicateurs. Les 51 cas ciblés du raccord et des
régressions, puis les deux cas de déduplication des risques, passent sans cas
ignoré. Une contre-validation indépendante vérifie aussi les bornes, les
engagements fermes et l'application des commandes au lendemain de l'observation.
Ces preuves portent sur les conventions programmées, pas sur leur calibration
industrielle.

La modification de carte compte désormais une seule fois chaque identifiant
d'incident non vide, même lorsque le résumé et le CSV décrivent le même événement.

## Essai courant de 56 jours

Le nouvel essai couvre le **1er janvier au 25 février 2025**, avec la graine
`320270`, sans mise en régime physique ni incident imposé. La variante
démonstrative observe les risques dès J0, contrairement au délai d'observation
de 30 jours du parcours nominal habituel. Les stocks, ordres initiaux, sécurités,
règles MRP et délais du nominal courant restent conservés. La configuration V3
historique n'a pas été ajustée.

| Mesure | Résultat courant | Interprétation |
|---|---:|---|
| Événements endogènes distincts | 135 | Signaux générés, pas tous appliqués |
| Incidents distincts appliqués | 46 | Effets présents dans le registre natif |
| Observations et décisions du contrôleur V3 | 56 chacune | Supervision active |
| Commandes devenues effectives | 55 | Décalage au lendemain respecté |
| Actions physiques non neutres du V3 | 0 | Aucun bénéfice de réponse automatique démontré |

Les risques dépendant de l'état et la réponse du contrôleur sont deux mécanismes
distincts : des incidents sont effectivement appliqués même si le contrôleur
ne modifie pas les paramètres physiques. Il reste en régime de crise neutre
sur 55 jours. En particulier, son indicateur de service divise le livré du jour
par la demande du jour **plus le retard déjà accumulé** ; avec deux jours de
transport client et une commande au jour de la demande connue, il peut signaler
une crise alors que les livraisons quotidiennes rattrapent la demande quotidienne.
Ce signal ne peut pas être remplacé ou son seuil ajusté pour forcer une action.

La métadonnée native d'anticipation indique six jours parce qu'elle est dérivée
du lissage MRP de sept jours. Deux audits séparés des dépendances, dont
182 contrôles indépendants, montrent que ce drapeau est un faux positif pour
ce chemin précis : l'observateur reçoit les commandes du jour, la mémoire passée
et les plans déjà connus. La moyenne des demandes réalisées futures n'est pas
son signal de demande. Le drapeau natif reste conservé ; aucune correction de
métadonnée ni aucun changement du lissage n'est utilisé pour faire passer le
contrôle. Les dates de publication des prévisions sont en partie reconstruites
au début de semaine : ce constat ne certifie pas la causalité industrielle.

## Comparaison appariée : un effet sur les commandes, pas encore sur les flux

Un seul témoin supplémentaire de 56 jours a été exécuté, avec exactement le
même graphe, la même graine, les mêmes conditions initiales et les mêmes
paramètres. Seuls les risques endogènes et le V3 sont désactivés ; dans le cas
actif, toutes les commandes du V3 sont neutres. Les commandes clients restent
identiques. Ce témoin n'est pas le nominal annuel d'une ancienne réalisation.

| Mesure sur le 1er janvier–25 février 2025 | Sans risques | Avec risques |
|---|---:|---:|
| Demande client arrivée, UN | 761 406 | 761 406 |
| Quantités livrées aux clients, UN | 721 103 | 721 103 |
| Retard client final, UN | 40 303 | 40 303 |
| Écart de fabrication exécutée ou libérée, par article et unité | — | 0 |
| Écart des stocks et disponibilités comparés, par article et unité | — | 0 |

Les 195 lignes de départs/réceptions sont strictement identiques, y compris
25 départs encore en transit à la fin de la fenêtre. Sur les 54 CSV du cas actif,
41 sont identiques au témoin ; les autres diffèrent ou n'existent que dans le cas
actif. **L'identité des résultats physiques observés ne signifie donc pas
l'identité de tous les calculs.**

Les 46 incidents appliqués sont 43 effets de disponibilité et trois de capacité,
décrits par 116 lignes. Exemple :
`state_stock_stock_cover_zero_SDC_VD0901566A_item_338928_d0` applique à J1 un
coefficient de disponibilité de 0,7. La capacité passe de 62 500 à 43 750 UN ;
le lot reste de 25 000 UN et une commande passe de 50 000 à 25 000 UN. La
réception correspondante est prévue à J71, le 13 mars, puis la disponibilité à
J79, le 21 mars : toutes deux sont hors de l'essai arrêté à J55. Cela explique
ce cas de modification d'engagement sans variation des flux observés dans
la fenêtre, sans prouver un effet client ultérieur.

Pour l'article 338928, les commandes promises diminuent au total de
1 050 000 UN, toutes hors fenêtre. Le coût d'approvisionnement externe reconnu
à la commande diminue de 295 312,50 unités monétaires du modèle ; le coût
opérationnel dans la fenêtre reste identique. Cette diminution d'engagement
**n'est pas un gain opérationnel démontré**. Aucune somme de quantités KG, G,
UN et mètres n'est utilisée pour mesurer un effet.

Preuves : `compatibility/control56/manifest.json`,
`compatibility/comparison56/manifest.json` et
`compatibility/comparison56/applied_risks_followup.json`. Le prochain essai
temporel discriminant doit inclure ces réceptions et disponibilités de mars,
après résolution des refus de qualification ci-dessous ; une année complète
n'est pas nécessaire pour examiner d'abord ce mécanisme.

La contre-comparaison indépendante confirme notamment l'identité de dix CSV
physiques (service, demande, consommation et départs compris) et de trois
initialisations. Elle ventile la baisse d'engagement externe en 146 937 de
transport et 148 375,50 d'achat. Ces valeurs restent distinctes des coûts
opérationnels effectivement reconnus dans la fenêtre.

## Limites conservées

La qualification globale de ce calcul est **refusée**, même si les contrôles
locaux de quantités et de couverture client passent. Ses échecs concernent les
disponibilités de transferts sans ordre associé, la déclaration du mode de
rapprochement des usages partagés et leur provenance/quantité journalière. L'audit
automatique de lots est explicitement non exécuté dans ce périmètre et reste
signalé comme manquant ; il ne devient pas un contrôle réussi.

La carte courante est donc une exploration descriptive de cet essai court.
Ni la causalité de chaque incident sur le service client, ni l'efficacité du V3,
ni une nouvelle référence industrielle ne sont validées. Aucun calcul annuel
supplémentaire n'est exécuté sur cette base. L'archive annuelle originale reste
accessible et conserve ses résultats propres.

Preuves principales sous
`etudecas/artifacts/testing/demonstration_01_etat_20261113/` :

- témoin nominal : `compatibility/nominal14_comparison.json` et
  `validator/compatibility/nominal14_review.json` ;
- tests moteur :
  `compatibility/toolbox/tests-f34ded3306064da38e1baef60b5ca28a/manifest.json` ;
- tests carte :
  `map/unique_counts_tests/tests-7b876d3f2648452f9ffe9f1ab179006b/manifest.json` ;
- essai courant : `compatibility/v3/control_d56/execution_manifest.json` ;
- contre-validation locale : `validator/compatibility/native56/manifest.json` ;
- audit des observations : `compatibility/observer_audit/observer_audit.json` ;
- contre-audit de ce drapeau : `validator/observer_audit/manifest.json` ;
- qualification globale refusée :
  `qualification/qualify-d9384bded6274dddb21cf8ff0c1dacae/manifest.json`.

Le contrôle documentaire global est également refusé : plusieurs registres
générés attendent une revue de leurs références (boucle moteur, comparaisons,
oracle CSV, parcours matière et sémantique). Leurs empreintes ne sont pas
réapprouvées automatiquement. Preuve :
`documentation/docs-51ae579d26c44a3eb6c1750db6210478/manifest.json`.

Le gate limité au diagnostic d'environnement et aux tests ciblés passe
(`limited_gate/gate-89b8f3b717834f5799d4ee18bf6d05bb/manifest.json`). Il ne demande
pas de qualification globale ni de navigateur et ne les certifie donc pas.
Les deux correctifs de code reçoivent chacun un handoff limité à leurs tests,
dans `integration/`. Ces contrats d'intégration sont établis après exécution ;
les déclarations initiales de mission restent conservées. Leur champ
`required_evidence` vide ne satisfaisait pas le parseur strict et n'avait pas
constitué un contrôle exécutable de livraison.

Le registre physique de lots reste requis par le moteur : il est utilisé par
les campagnes, réceptions et consommations. Le drapeau `--no-lot-trace` ne peut
donc pas être employé comme simple économie de journalisation. Aucun essai
connu invalide n'est exécuté ; l'audit automatique de lots peut être exclu sans
changer la physique, et cette exclusion ne compte pas comme un contrôle réussi.

Les preuves et plans sont dans
`etudecas/artifacts/testing/demonstration_01_etat_20261113/`. Le suivi commun
porte le ticket `DEMO01-ETAT-20261113`. Les refus de sécurité navigateur antérieurs
restent respectés : pas de navigateur, Node ou Word relancé, pas de test global
ni de mutation de fichiers pour éprouver l'intégrité.
