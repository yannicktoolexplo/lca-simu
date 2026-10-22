# Faire évoluer le simulateur avec une preuve adaptée

Ce guide fixe des critères de travail, pas une déclaration de conformité du
moteur. L'appliquer lors d'un changement de données, de règle, de mécanisme,
d'expérience ou de performance. Une retouche documentaire ne déclenche pas une
campagne de simulation. Le [bilan daté](quality/AUDIT_INSTRUCTIONS_20261021.md)
conserve les constats et le backlog de la mise à niveau des instructions.

## Partir de l'existant et qualifier la conclusion

Lire les sections utiles des [règles MRP](REGLES_MRP.md), de la
[référence courante](MRP_REFERENCE_20261014.md), des
[données sources](DONNEES_SOURCES.md) et du contrat concerné. Vérifier les chemins,
versions et empreintes avant de réutiliser une preuve. Une référence de demande
client, un nominal MRP et une archive de comparaison peuvent avoir des périmètres
différents : ne pas les choisir par le seul nom « current ».

Pour chaque capacité ou conclusion, distinguer :

| Statut | Preuve ou action requise |
|---|---|
| Vérifié sur un périmètre | Nommer scénario, sources, date, oracle, résultat et preuve compatible. |
| Existant, insuffisamment éprouvé | Citer code ou contrat et ce que la preuve ne couvre pas. |
| Proposé | Décrire problème reproductible, intervention, alternative existante et critère d'acceptation. |
| Inconnu ou contradictoire | Garder la valeur inconnue et désigner l'information discriminante. |

Une procédure décrit ce qui est exigé ; une présence de code décrit ce qui
existe ; seuls les contrôles réalisés décrivent ce qui a été vérifié. Garder
l'état temporaire et les apprentissages dans le suivi existant, avec les preuves
volumineuses dans les artefacts locaux.

## Contrat des données, du temps et des unités

Pour chaque donnée déterminante, relever fichier/version/empreinte et
onglet/cellules ou colonnes, article/site/étape/périmètre, unité et conversion,
date d'effet, date de connaissance, et statut observé, estimé, hypothétique ou
simulé. Une reconstruction indique en plus son équation, ses entrées et ses
limites. Une date de connaissance absente reste inconnue ; elle n'est pas
remplacée silencieusement par la date de l'événement.

Avant une transformation, distinguer absence et zéro confirmé, photo et
mouvement, sortie brute et solde net, réception prévue et engagement ferme.
Examiner valeurs négatives, doublons et ruptures de périmètre avant tout
écrêtage ou imputation. Conserver les sources ; enregistrer séparément la
transformation réversible, son motif et son effet quantifié.

Une décision prise à `t` n'utilise que l'information connue à `t`. Une prévision
future publiée avant `t` est admissible ; une réception réalisée connue après
`t` ne l'est pas dans un rejeu autonome. Une cible de calibration ne doit pas
être réinjectée comme réponse dans son propre calcul.

Pour une BOM, expliciter quantité composant / quantité parent de base, unités,
conversion, rendement et étape. Le besoin théorique et le prélèvement du registre
matière ont des sens distincts. Un bilan fermé ne démontre pas la correspondance
produit/vrac/étape. Ne pas sommer des kg et des UN ; comparer les périmètres
monétaires selon [le contrat de comparaison](SCENARIO_COMPARISON.md).

Chaque délai précise événement de départ, événement d'arrivée, unité, calendrier,
règle d'arrondi et ce qu'il inclut déjà. Distinguer décision, commande,
lancement administratif, premier travail physique, fin de fabrication, départ,
réception physique, contrôle et disponibilité. Vérifier semaines, bornes incluses,
première période partielle et ordre intrajournalier avant de conclure à un retard.

Conserver les décisions confirmées : UN physiques entières, sécurité source
lundi–vendredi, protection dépôt à 100 % des jours source, nominal séparé des
sensibilités, références antérieures conservées. `tau_process` reste une marge
de planification jusqu'à confirmation de son sens physique. Ne pas lui ajouter
une durée d'exécution supposée ni compter deux fois un contrôle déjà inclus.

## De la planification à l'exécution physique

Les équations actives et leurs variables restent dans [REGLES_MRP.md](REGLES_MRP.md).
Pour toute correction, identifier la couche qui change et tracer ses entrées et
sorties :

| Couche | Questions et preuve attendue |
|---|---|
| Demande | Séparer commandes, demande indépendante, prévisions et consommation des prévisions ; conserver le millésime connu à la décision. |
| Besoins | Séparer explosion BOM, autres usages d'une matière partagée et protection de sécurité ; expliquer toute affectation au même stock. |
| Netting | Affecter stock utilisable, engagements et surplus une seule fois ; conserver la couverture tardive et son retard. |
| Proposition | Définir minimum, multiple, maximum par lot, fractionnement et réutilisation du surplus ; une proposition reste révisable. |
| Engagement | Définir la politique autorisant commande, OF ou transfert, les priorités et les identifiants conservés lors d'une replanification. |
| Exécution | Vérifier composants, capacité restante partagée, ressources, calendrier, qualité et transport à la date du travail réel. |

Une réception ferme tardive n'est ni du stock disponible à l'échéance ni une
raison automatique de commander la même quantité une seconde fois. Documenter
séparément une éventuelle politique d'accélération ou de remplacement.

Définir les états physiques nécessaires : disponible, réservé, bloqué, transit,
encours. Préciser s'ils sont exclusifs et comment ils se rapprochent du stock
physique. Un lot commencé reste un encours jusqu'à sa fin ; un produit terminé
en contrôle n'est pas encore utilisable. Fermer les bilans de matière adaptés
aux transformations, rendements, rebuts et reprises, avec les unités et origines.
Interdire double réservation, réception ou consommation.

Déclarer réservation, priorisation, substitution, partage de capacité, transport
et libération. Une même capacité n'est pas disponible intégralement pour chaque
article qui la partage. Principal/secours, parts et alternatives fournisseurs
doivent correspondre à des possibilités documentées ; aucune solution de secours
implicite. Préserver les deux vues indépendantes, **Suivi de lots** et
**Parcours simplifié des lots**, leurs sélections et leurs bilans, selon
[le contrat des parcours](PARCOURS_DES_LOTS.md). Distinguer contribution du PF
suivi, occurrence entière et matière effectivement consommée. Les identifiants
simulés ne deviennent pas des numéros industriels observés ; voir
[matières, lots et incidents](MATIERES_LOTS_ET_INCIDENTS.md).

## États, mémoire, risques et ordre des événements

Avant d'ajouter un couplage, décrire l'état, l'information observable, la décision,
l'événement exogène et la transition. Écrire l'ordre des opérations d'un pas et
la règle de synchronisation des événements simultanés. Une décision ne doit pas
accéder à l'état de fin de pas avant sa transition.

Pour chaque mécanisme, fournir relation, unités, bornes, délai de propagation,
récupération, domaine d'application, paramètres sourcés et statut de preuve.
Si l'effet dépend du passé, définir la mémoire : durée de surcharge, âge du
retard, vieillissement ou historique utile, avec initialisation, mise à jour et
oubli. Une valeur instantanée ne représente pas une durée accumulée.

La chaîne « perte de capacité → retard → rattrapage → heures supplémentaires →
baisse de qualité » est une hypothèse à tester sur son périmètre. Ne pas l'activer
par défaut chez tous les fournisseurs. Séparer événements imposés, risques
exogènes et risques dépendant de l'état, et conserver l'identité de l'incident
pour éviter son application en double par plusieurs mécanismes.

Une intensité conditionnelle `lambda` en `1/jour` n'est pas une probabilité par
pas. Sous intensité constante sur un intervalle de durée `delta_t` en jours,
`p = 1 - exp(-lambda * delta_t)` ; si elle varie, intégrer l'intensité sur
l'intervalle. Déclarer l'approximation et l'état utilisé. Cette formule concerne
la survenue d'au moins un événement ; elle ne décrit pas à elle seule son nombre,
sa gravité ni les dépendances entre incidents. Contrôler les bornes et l'influence
du pas et de l'ordre des événements sur un cas ciblé.

## Calibration et reconstruction scientifique

Déclarer l'usage avant calcul : rapprochement historique avec événements imposés
ou assimilation explicite ; rejeu autonome limité aux informations connues à
chaque date ; prospective avec hypothèses futures déclarées. Les observations
industrielles restent limitées à 2025 dans la référence actuelle. Reconduction
saisonnière et croissance de 5 % sont des hypothèses prospectives.

Avant ajustement, vérifier périmètres, unités, calendriers, stocks et ordres
initiaux, correspondances BOM et politiques. La
[procédure de calibration](CALIBRATION_EXECUTION.md) distingue protocole
scientifique et reprise technique. Consigner dans le suivi existant :

1. Écart visé, témoin, hypothèses concurrentes, intervention, paramètres conservés
   et résultat attendu ou contradictoire, avec dates, unités et tolérances.
2. Paramètres interprétables, bornes et origine ; sensibilité, compensations et
   identifiabilité. Si plusieurs réglages sont indiscernables avec les données,
   conserver cette indétermination et la mesure qui permettrait de la lever.
3. Fenêtres chronologiques distinctes de calibration et validation, et si possible
   articles, sites ou régimes non utilisés pour l'ajustement. Ne pas choisir la
   fenêtre ou les critères après observation d'une amélioration.
4. Comparaison stocks physiques/utilisables, encours, achats, fabrications,
   transferts, délais, ruptures et service ; erreurs de volumes et de dates,
   biais, états de fin d'horizon et incertitudes.
5. Gains, dégradations et limites à l'échelle de la chaîne, oracle indépendant et
   décision explicite avant toute promotion de référence.

Définir dénominateurs et agrégations avant calcul : ratio d'unités livrées,
ponctualité et part de CA livré ne sont pas interchangeables. Près de zéro,
préférer une erreur absolue et un taux déclaré non défini à un pourcentage
instable. Une somme annuelle peut masquer retards et rattrapages.

Monter progressivement en coût : calcul manuel ou en mémoire, scénario ciblé,
année, puis cinq ans ou campagne si une nouvelle question l'exige. Si les sorties
ne changent pas, vérifier activation et propagation du paramètre dans les traces,
puis stocks tampons et compensations avant de multiplier les variantes.

## Recherche de causes racines

Utiliser le skill `etudecas-supply-diagnose` et le registre commun défini dans
[le fonctionnement multi-agent](MULTI_AGENT_OPERATIONNEL.md). Quantifier symptôme,
période et périmètre ; localiser première divergence et premier bilan incohérent ;
remonter événements, ordres, lots et contraintes. Comparer les hypothèses données,
périmètre, initialisation, code, règle, paramètre et événement externe.

Construire le plus petit cas reproductible utile puis une intervention
discriminante ; vérifier témoins, robustesse et interactions. L'explication suit
une chronologie quantifiée : événement → contrainte → ordre/lot affecté → réception
décalée → stock → production → service client. Chiffrer ce qui est absorbé par
les stocks et le rattrapage entre fournisseur/Gaillac, Avène/Gien, Muret et client.
Une tension amont ne prouve pas une non-livraison aval.

Séparer causalité programmée, association statistique et causalité industrielle
établie. Corrélation, importance SHAP ou indice de sensibilité ne démontrent pas
une cause réelle. Une contrainte immédiate peut être prouvée tandis que son
origine reste inconnue ; conserver les alternatives réfutées et indécidables.

## Sobriété du code et performance

Auditer six responsabilités : lecture/normalisation ; modèle et contrats ;
planification/politiques ; transitions physiques ; expériences/calibration/
optimisation ; indicateurs/restitution. Un écart à ce découpage justifie une
extraction progressive seulement s'il gêne une correction, un oracle, la lecture
ou une mesure. Préserver noms métier, types utiles, équations traçables et
commentaires expliquant les décisions délicates. Éviter les abstractions sans
consommateur et mesurer leur coût.

La généricité repose sur données et politiques configurables. Une exception
article/site doit être explicite, sourcée, bornée et vérifiable ; ne pas cacher
une règle industrielle dans une branche isolée. Toute réécriture, dépendance ou
migration est un item de backlog motivé, avec alternative actuelle, compatibilité,
maintenance et preuve attendue. Le noyau doit fonctionner sans réponses LLM.

Avant optimisation, figer cas représentatif, entrées, code, politique de cache,
environnement et budget de temps/mémoire/stockage. Mesurer temps, mémoire,
entrées-sorties et taille des artefacts ; identifier le point chaud. Comparer
avant/après à critères métier et tolérances explicites, en tenant compte du bruit
de mesure. Une réduction du volume de preuve ou une modification de sémantique
ne constitue pas une accélération équivalente.

## Incertitude et comparaison de politiques

Séparer variabilité aléatoire, incertitude des paramètres et ignorance des données
ou de la structure. Pour Monte-Carlo, documenter générateur, version, graines et
flux par mécanisme ou entité avec identifiants stables. Une graine globale ne
garantit pas l'appariement lorsque les branches d'exécution changent.

Lorsque pertinent, apparier les événements exogènes entre politiques et vérifier
cet appariement dans les traces ; laisser les réactions endogènes dépendre de
l'état de chaque politique. Définir répétitions, convergence, précision attendue,
intervalles et arrêt avant campagne. Distinguer intervalle de confiance sur une
statistique et dispersion des réalisations. L'absence d'événement rare dans peu
de répétitions ne démontre pas un risque nul.

Choisir la sensibilité selon ses hypothèses, notamment indépendance ou corrélation
des entrées ; ne pas permuter librement des combinaisons physiquement impossibles.
Examiner dépendances entre risques et événements communs. Livrer résultats
agrégés, exclusions et limites avec le budget consommé ; les contrôles et oracles
requis sont définis dans [TEST_VALIDATION.md](TEST_VALIDATION.md).
