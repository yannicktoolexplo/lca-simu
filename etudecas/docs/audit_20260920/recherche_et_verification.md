# Recherche, traçabilité des chiffres et critères de qualification

Cette proposition répond au public retenu : le planificateur doit pouvoir agir sur une information vérifiable ; le chercheur doit pouvoir expliquer et reproduire les résultats. Une même carte peut servir aux deux, avec des niveaux de lecture distincts.

## Ce que démontre une preuve

Quatre niveaux doivent rester séparés :

1. **Provenance** : le fichier, la version et la transformation utilisés sont identifiés.
2. **Vérification logicielle** : la règle programmée respecte ses propriétés, ses dimensions et ses cas calculables à la main.
3. **Validation industrielle** : la règle, ses paramètres et ses résultats décrivent suffisamment le système réel pour l'usage choisi.
4. **Inférence** : l'expérience permet d'attribuer un effet, de comparer une politique ou d'estimer une incertitude avec ses limites.

Le projet a beaucoup progressé sur les deux premiers niveaux. L'audit montre aussi pourquoi ils ne suffisent pas : la courbe peut recopier exactement un CSV dont la demande a été déplacée par une transformation ; un total peut additionner exactement des coûts dont la base de valorisation est invalide ; un événement peut être affiché correctement sans preuve qu'il a causé le retard voisin.

## Fiche de preuve pour chaque indicateur

Chaque famille de courbes, chiffre de synthèse ou diagnostic devrait avoir un identifiant stable et le contrat suivant :

| Champ | Contenu nécessaire |
|---|---|
| Question métier | Exemple : quelle quantité pourra être livrée avant l'échéance ? |
| Population | Article(s), site(s), ordres, lots, scénario |
| Grandeur et unité | Quantité, durée, coût, taux, score ; unité/dénominateur explicites |
| Temps | Date de décision, date d'événement, période sélectionnée, prévision ou exécution |
| Donnée source | Fichier, feuille/colonne ou champ, empreinte et transformation |
| Formule | Calcul, agrégation, lissage, normalisation, convention d'arrondi |
| Statut de la valeur | Source observée, estimation, paramètre de scénario, résultat simulé, inconnu |
| Oracle indépendant | Calcul de contrôle distinct du constructeur de la figure |
| Domaine de validité | Limites, données manquantes, calibration et exclusions |
| Preuve navigateur | Figure visible, légende/unités, filtres, erreurs et capture liée au hash HTML |

L'inventaire numérique produit par cet audit est un point de départ. Il faut transformer ses chemins techniques en contrats maintenables par famille, puis développer les occurrences article/site automatiquement. Compter deux copies d'une même série comme deux confirmations indépendantes gonflerait artificiellement la preuve.

Statuts recommandés : `rapproché`, `cohérent avec le calcul mais contrat métier à corriger`, `structure vérifiée seulement`, `source manquante`, `non disponible`, `non vérifié`. Un état absent ne vaut ni zéro ni réussite.

## Essais négatifs et propriétés qui auraient détecté les défauts

| Propriété indépendante | Défaut ciblé |
|---|---|
| Changer le lissage prévisionnel ne change pas la demande réalisée source | Demande déplacée par l'option MRP |
| Représenter une masse en G ou KG laisse sa valeur économique inchangée | Repli global de prix hétérogènes |
| Un tarif €/UN × quantité donne un montant, quel que soit le découpage en lots | Base de transport unité/lot |
| Un incident non appliqué ne produit pas une preuve positive d'effet physique | Causalité inférée par fenêtre de backlog |
| Changer uniquement des réalisations futures ne change pas une décision passée | Contrat d'information des alertes et politique réactive |
| L'horizon d'exécution reste celui du manifeste malgré des engagements futurs | Expéditions au-delà de J1824 |
| Une référence inactive à stock nul n'est pas une rupture de composant requis | Signal de stock nul permanent |
| Un filtre année 1 change tous les indicateurs annoncés comme annuels | Diagnostic cinq ans laissé dans une fiche filtrée |
| Une entrée externe contenant plusieurs sous-vues donne des boutons accessibles | Radars et critères masqués |
| Un run propre sans anciens outputs donne le même verdict de test | Test du pack satisfait par fichier périmé |

Ces propriétés doivent rester distinctes d'un test qui recalcule la même formule avec les mêmes helpers. Les contre-exemples de cet audit sont conservés ; les intégrer comme régressions lors des corrections, après clarification des conventions concernées.

## Une étude exploitable pour la recherche

Les recommandations STRESS structurent le compte rendu d'une simulation autour de ses objectifs, sa logique, ses données, son expérimentation, son implémentation et son partage. Elles servent ici de repère documentaire ; elles ne certifient pas notre modèle. [Application des recommandations STRESS, Winter Simulation Conference](https://www.informs-sim.org/wsc18papers/includes/files/061.pdf).

Pour Etudecas, le dossier d'expérience devrait contenir : question et décision étudiées ; variable de résultat ; graphe et dictionnaire de données ; hypothèses de calendrier, capacité, stock, coût et information ; règles d'amorçage et de fin d'horizon ; protocole de tirage ; scripts ; résultats avec leur population exacte ; limites et tentatives de réfutation.

Avant de mesurer l'efficacité d'une action, corriger les conventions ayant un effet sur l'estimand. Une réduction de coût non dimensionné ne peut pas valider une politique. Une mesure de service cumulé ne suffit pas à soutenir une conclusion de ponctualité. Si les dates de commandes promises ne sont pas disponibles, le dire et utiliser une mesure compatible avec les données.

Le cas actuel réutilise un profil annuel pendant cinq ans, avec prévision identique à la demande dans la source. Ce n'est pas une validation prédictive sur cinq années indépendantes. Il faut réserver des observations non utilisées pour le paramétrage, examiner les erreurs par semaine/article, et documenter les conditions dans lesquelles les données sont représentatives.

Les comparaisons nominal/risques/actions actuelles emploient une seule graine par calcul ; elles constituent des études de scénario. Pour estimer un effet moyen ou la robustesse d'un classement, prévoir des répétitions, présenter les différences et leur dispersion, et vérifier l'appariement des tirages. Une graine identique ne suffit pas quand le scénario change l'ordre ou le nombre des appels aléatoires. Les dépendances entre risques et les interactions doivent être explicites.

La bande P10–P90 entre deux scénarios peut être un dessin descriptif, comme le précise déjà la carte ; elle ne devient pas une probabilité ni un intervalle de confiance. Pour le planificateur, deux lignes avec leur écart sont généralement plus directes. Pour le chercheur, garder le protocole, la population et les méthodes d'incertitude visibles à côté du graphique.

Les indices pondérés, y compris « Physics of Decision », doivent être présentés comme exploratoires : expliquer leurs cibles, poids, saturations et périodes exclues ; vérifier qu'une référence dormante ne domine pas le score ; tester la stabilité des conclusions aux choix de normalisation. Le mot « catastrophe » ne décrit pas une fréquence d'incident mesurée.

## Du suivi de lot à la simulation d'incident

GS1 distingue les événements de suivi — réception, conditionnement, expédition, transport — et les informations qui décrivent chaque événement. Ce cadre conforte une organisation par objets et événements, avec identités et états explicites. [Présentation officielle du standard de traçabilité GS1](https://support.gs1.org/support/solutions/articles/43000734535-what-is-the-gs1-traceability-standard-).

Application proposée au simulateur : ne pas confondre lot fabricant, lot de production, occurrence de stock, unité logistique, commande, expédition et moyen de transport. Pour chaque événement, conserver la quantité/unité, les sites, les dates prévues et réalisées, la provenance et les objets parents/enfants. Un identifiant interne simulé ne remplace pas un numéro fabricant absent.

Le suivi actuel prépare cette structure et traite prudemment les mélanges. Avant une quarantaine physique, il reste à définir le jour d'application, les quantités encore accessibles, le sort des réservations et transports partis, les consommations déjà exécutées, les autorisations de libération et le périmètre d'un rappel. Les informations fabricant, péremption, qualité, palette/SSCC et véhicule doivent rester inconnues quand elles manquent. Les estimer exige un statut explicite et ne les transforme pas en observations industrielles.

Le choix utilisateur reste **compléter le suivi d'abord, incidents physiques ensuite**. L'audit n'ajoute aucun incident ni effet matériel au moteur. Une analyse d'exposition généalogique répond « quels lots peuvent être concernés » ; un rejeu d'incident répond « quels résultats changent sous la règle choisie ».

## Ordre de livraison et rôle du multi-agent

La correction doit conserver la référence actuelle, produire une nouvelle variante, puis rapprocher ancien et nouveau résultat avec un journal expliquant chaque différence. Les stocks de sécurité sources restent distincts des scénarios de sensibilité. Les valeurs manquantes, calendriers et conventions comptables doivent être décidés ou signalés, jamais remplis silencieusement.

Le multi-agent doit appliquer cette chaîne : un agent établit la transformation et son contrat ; un agent réalise le changement dans son périmètre ; un validateur utilise les données gelées et un oracle distinct ; un agent carte contrôle les interactions et le vocabulaire. Le parent intègre uniquement les preuves compatibles avec le même état du code et des données. Le nombre d'agents n'est pas un critère de confiance ; la traçabilité et l'indépendance des vérifications le sont.

L'[architecture proposée](multiagent.md) réutilise les commandes existantes. Son critère de réussite sera une tâche réellement déléguée, un échec volontaire correctement remonté, des fichiers de preuve attribués au bon run et un résultat global refusé si une preuve attendue manque. La configuration native et la toolbox restent à construire après cet audit ; le pack actuel ne doit pas être présenté comme une orchestration installée.
