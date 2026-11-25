# Compléments pour la planification et le transport

Complément produit le 25 novembre 2026 par l’assistant pour la supervision. Référence du dépôt : `REV-0415`, branche `partage/cahiers-ic-anonymes`. Les calculs ci-dessous prolongent les cahiers publics. Ils ne décrivent ni un travail individuel antérieur ni une observation industrielle.

## 05 La reprise des volumes et le service quotidien

**Question à trancher.** L’équipe doit-elle garantir une quantité chaque jour, ou un total livré avant une échéance ? Cette réponse détermine l’indicateur de comparaison et l’usage de la réserve.

**Acquis exact.** [Cahiers-metier.md, lignes 33 à 37](../Cahiers-metier.md#la-reprise-des-volumes-garantit-elle-le-service-chaque-jour-) compare deux trajectoires à 90 % et 84 % sur cinq jours. Avec deux unités de réserve avant J1 puis deux avant J3, la seconde atteint neuf livraisons chaque jour. La première manque encore une unité à J2. La pièce suffit pour constater que le meilleur total ne garantit pas le meilleur jour. Les séries quotidiennes et les règles de report ne sont pas publiées : on ne peut pas rejouer les trajectoires.

**Lecture métier à faire en premier.** Microsoft, [Calculate order promising dates](https://learn.microsoft.com/en-us/dynamics365/business-central/sales-how-to-calculate-order-promising-dates), mise à jour du **16 novembre 2026**, sections « Available to promise » et « Calculations », explique la promesse à partir des quantités non réservées et de leur date de disponibilité, puis des délais de préparation et de transport. En revue, fixer le point mesuré : départ du dépôt ou réception client. Une réserve arrivée à J3 ne peut pas garantir J2. Cette lecture décrit une pratique d’ERP, sans démontrer que son installation est nécessaire ici.

**Méthode à essayer.** Un tableau journalier suffit : engagement, livraison prévue, réserve libérée avant la coupure, réserve affectée, livraison totale, manque et solde de réserve. Comparer le volume cumulé à échéance et le nombre de jours sous le plancher. Ne pas additionner deux fois une même unité de réserve. Documenter si l’on autorise à rationner une livraison déjà promise pour protéger le lendemain.

**Calcul exécuté.** Le classement en volume présente un écart de **90 − 84 = 6 points**. La réserve totale est **2 + 2 = 4 unités**, dont seulement deux sont mobilisables avant J3. Le manque publié à J2 vaut **1 unité**, soit une livraison de **9 − 1 = 8 unités** après la réserve selon le résultat du cahier. Cela ne donne ni la série complète ni le nombre exact de jours déficitaires du premier scénario. Le JSON conserve ces calculs partiels, sans inventer une trajectoire.

**Lecture de recherche facultative.** Ivanov, *When is the supply chain resilient? Customer and operational perspectives*, publication en ligne **21 janvier 2025**, [DOI](https://doi.org/10.1080/00207543.2025.2454331), [résumé ouvert sur le site du projet auteur ACCURATE, rubrique du même titre](https://accurateproject.eu/publications/). Trois réseaux simulés sont comparés avec livraison à l’heure, taux de satisfaction des volumes et temps de reprise. L’étude distingue le regard client du regard opérationnel. Elle justifie de conserver deux indicateurs, sans apporter un gain chiffré transférable au cahier.

**Données à demander.** Vue « article × point de livraison × jour » sur les cinq jours et le délai amont : besoins et engagements datés, arrivages utilisables, réserve disponible horodatée, allocations et report autorisé. L’essai terrain reste proposé. Si l’engagement est quotidien, conserver la seconde trajectoire dans ce cas publié ; s’il est uniquement hebdomadaire, comparer les volumes à l’échéance et le coût de réserve.

## 06 L’ordre de service de deux commandes

**Question à trancher.** Le contrat limite-t-il le retard maximal de chaque commande ou facture-t-il la quantité en retard multipliée par sa durée ? La priorité « urgent » doit correspondre à une règle explicite.

**Acquis exact.** [Cahiers-metier.md, lignes 39 à 43](../Cahiers-metier.md#un-lot-disponible-deux-commandes-en-attente--laquelle-servir-) : servir la commande urgente en premier ramène le retard maximal de sept à quatre jours, mais augmente le retard pondéré par les quantités de 28 à 32 unités-jours. Ces deux bilans sont connus ; quantités individuelles, échéances et dates des arrivages suivants ne le sont pas. On peut comparer les objectifs, pas reconstruire les commandes.

**Lecture métier.** Microsoft, [Priority-based planning](https://learn.microsoft.com/en-us/dynamics365/supply-chain/master-planning/planning-optimization/priority-based-planning), mise à jour du **17 juin 2025**, sections « Where and how planning priorities are assigned » et « View and maintain planning priority », documente des priorités portées par les lignes d’offre et de demande et le fractionnement possible des approvisionnements. Pour l’entretien avec le planificateur, demander qui affecte la priorité et comment elle est propagée entre commandes liées. La priorité de réapprovisionnement décrite par cet ERP ne prouve pas l’optimalité d’une affectation de lots à des commandes clients.

**Méthode accessible.** Dans un tableau à deux lignes, conserver les deux résultats déjà disponibles. Le témoin est l’autre ordre de service ; la variante sert l’urgence. Le critère doit être écrit avant le choix. Si le maximum autorisé est quatre jours, la variante est la seule des deux à respecter ce plafond. Si la pénalité est strictement linéaire en unités-jours, avec même tarif pour toutes les pièces et sans autre clause, le témoin coûte moins cher.

**Calcul exécuté.** La variante évite **7 − 4 = 3 jours** de retard maximal, mais ajoute **32 − 28 = 4 unités-jours**, soit **14,29 %** du niveau témoin. À titre de sensibilité contractuelle, pour un coût `a × retard maximal + b × unités-jours`, elle devient préférable si `3a > 4b`. Le rapport `a/b` doit dépasser **4/3 unité** : `a` est en unités monétaires par jour de retard maximal et `b` en unités monétaires par unité-jour. Ce seuil ne s’applique pas à une pénalité par commande avec franchise, plafond ou rupture non linéaire. Aucun tarif industriel n’est supposé.

**Pour aller vers la recherche.** La publication d’Ivanov citée au thème 05 aide à expliquer pourquoi les deux classements diffèrent. Il n’est pas utile d’introduire un algorithme d’ordonnancement sur deux options dont les résultats sont déjà connus. L’approfondissement utile serait de tester la même règle sur plusieurs arrivages et plusieurs commandes, avec l’aide de la supervision.

**Données à demander.** Vue « commande et ligne × lot affectable » au moment de la décision : quantité, date promise, lot libéré, quantité déjà réservée, possibilité de fractionner la livraison, prochain réapprovisionnement et clause de pénalité. Geler les informations connues à cet instant pour éviter de donner à une règle une livraison future inconnue. Le complément livré est une grille d’arbitrage ; le rejeu des commandes reste proposé.

## 07 Les départs après une fermeture de quai

**Question à trancher.** Peut-on avancer une tournée, ajouter une rotation ou mobiliser un deuxième véhicule tout en respectant les créneaux et la livraison ?

**Acquis exact.** [Cahiers-metier.md, lignes 47 à 51](../Cahiers-metier.md#peut-on-regrouper-deux-départs-après-une-fermeture-de-quai-) : deux tournées de 40 unités pour une capacité de 60 ne peuvent pas être regroupées dans un seul chargement. Le cahier indique zéro regroupement faisable sur 21 fermetures examinées. Les 21 calendriers ne sont pas publiés : ce dénombrement est cité et n’est pas recalculé ici.

**Pratique à lire.** Microsoft, [Set up an appointment for a load](https://learn.microsoft.com/en-us/dynamics365/supply-chain/transportation/tasks/set-up-appointment-load), mise à jour du **17 février 2025**, décrit un rendez-vous lié au quai, à une charge, à une heure locale et à une durée. En revue transport, demander le temps complet qui immobilise le quai, puis la disponibilité du véhicule et du chauffeur. Un créneau ajouté ne crée pas automatiquement une rotation réalisable.

**Recherche appliquée à parcourir ensuite.** Huang et al., [Optimization of external container delivery and pickup scheduling based on appointment mechanism](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0318606), **21 février 2025**, sections « Assumptions » et « Experimental design and results ». Une simulation d’un terminal et de six dépôts sur 24 heures combine quotas de rendez-vous, rotations et fenêtres horaires. Le meilleur coût annoncé est inférieur de **4,89 %** au planning manuel de leur comparaison. C’est un résultat des auteurs dans leur cas portuaire ; il ne mesure pas le gain de notre quai et ne justifie pas de commencer par leur algorithme.

**Calcul exécuté.** Le témoin est le regroupement en un chargement : **40 + 40 = 80 unités**, soit **133,33 %** de la capacité. Le dépassement est **20 unités**. Sous l’hypothèse de charges fractionnables et sans contrainte supplémentaire, il faut au moins `arrondi supérieur(80/60) = 2` chargements. Ce minimum ne signifie pas deux véhicules : un véhicule peut effectuer deux rotations si le temps de cycle le permet.

| Variante à examiner | Condition de faisabilité à confirmer | État avec les pièces publiques |
| --- | --- | --- |
| Avancer la première tournée | Marchandise prête, quai et client disponibles | Non départagée |
| Ajouter un créneau et une rotation | Véhicule de retour avant ce créneau | Non départagée |
| Deuxième véhicule | Deux opérations de quai compatibles, chauffeur et capacité disponibles | Non départagée |

**Essai terrain proposé.** Écarter les options dépassant l’échéance ou les ressources, puis comparer coût supplémentaire, heures travaillées et émissions sur les mouvements réellement déclenchés, y compris les retours. Ne pas supposer qu’un véhicule de plus double mécaniquement les émissions. La méthode actuelle [GLEC v3.3, octobre 2026](https://smartfreightcentre.org/news/13311209/), développée au thème 08, fournit le périmètre transport.

**Données à demander.** Vue « tournée × chargement × rendez-vous » sur une fermeture et ses deux tournées voisines : quantités en unités et en tonnes, capacité poids/volume/palettes, heure de disponibilité, heures de quai et client, durée de manutention, temps aller-retour, chauffeurs, kilomètres et énergie. La vérification de capacité suffit déjà à rejeter le regroupement témoin ; aucun classement environnemental n’est possible à ce stade.

## 08 Les justificatifs à demander au transporteur

**Question à trancher.** Cherche-t-on à documenter un maximum d’activité transport ou à obtenir des parcours complets, avec un budget de demandes et de réponses exploitables ?

**Acquis exact.** [Cahiers-metier.md, lignes 53 à 57](../Cahiers-metier.md#quels-relevés-demander-en-priorité-au-transporteur-) : trois parcours complets couvrent 47,6 % des tonnes-kilomètres, contre 42,0 % pour trois liaisons. À dix demandes, les liaisons gagnent environ 13,6 points. La carte des parcours, leur chevauchement et les pièces reçues ne sont pas fournis. Aucun optimum de collecte ni seuil entre trois et dix demandes n’est identifiable.

**Référence actuelle ouverte.** Smart Freight Centre a publié [GLEC v3.3](https://smartfreightcentre.org/news/13311209/) le **27 octobre 2026**. Le [PDF v3.3](https://d1c2gz5q23tkk0.cloudfront.net/shrine_store/uploads/networks/3660/communication_news/13311209/07d62a17997083e294953d425e69d86c.pdf), section 1 chapitre 1 et section 2 chapitre 1, décompose les parcours en opérations de transport et de plateforme, puis additionne leurs émissions. La qualité et l’origine des données doivent être explicites. En entretien, demander une pièce rattachable à chaque tronçon et plateforme, et marquer les postes estimés ; une forte couverture en tonnes-kilomètres ne démontre pas une empreinte complète.

**Ce qui a changé récemment.** Le [Crosswalk, édition 4 du 26 octobre 2026](https://d1c2gz5q23tkk0.cloudfront.net/shrine_store/uploads/networks/3660/communication_news/13311209/3b754d52417445123e4d321e33d4a3ab.pdf), pages 3 à 5, détaille notamment de nouvelles valeurs aériennes et des tableaux distinguant l’inclusion ou non du supplément de distance de 95 km. Dans la demande au transporteur, enregistrer version du facteur, type de distance et correction déjà incluse, pour éviter un double ajustement. Changer de version ne prouve pas une amélioration réelle de l’exploitation.

**Calcul exécuté et essai proposé.** Avec un budget de trois demandes, supposées d’abord toutes exploitables, l’avantage publié des parcours vaut **47,6 − 42,0 = 5,6 points** du total des tonnes-kilomètres. Une sensibilité pédagogique, distincte du cahier, suppose que chaque demande aboutit avec une probabilité homogène par méthode, sans double compte de l’activité. Avec **80 %** de réponses exploitables aux demandes de parcours et **95 %** aux demandes de liaisons, les couvertures attendues deviennent `47,6 % × 80 % = 38,08 %` et `42,0 % × 95 % = 39,90 %`. Les liaisons passent devant. Ces taux de réponse sont hypothétiques. Le seuil est `p_parcours/p_liaisons > 42/47,6 = 0,8824`. Ce calcul justifie de relever l’effort et le résultat de chaque demande avant de choisir une méthode.

**Recherche utile.** Kallionpää et al., [Development of logistics emissions reporting](https://researchportal.tuni.fi/en/publications/development-of-logistics-emissions-reporting-shippers-and-logisti/), en ligne **novembre 2025**, numéro de **janvier 2026**, rapporte 17 entretiens d’experts et des pratiques de reporting hétérogènes. La notice universitaire ouverte suffit ici pour justifier un format de collecte commun ; elle ne prouve pas la supériorité d’une stratégie de sélection.

**Données à demander.** Vue « expédition × tronçon et plateforme » sur un mois représentatif : identifiants anonymes, séquence du parcours, tonnes, kilomètres et méthode de distance, mode/énergie, facteur et version, périmètre des émissions, justificatif et réponse obtenue. Calculer deux sorties séparées : tonnes-kilomètres documentées/total, et parcours entièrement renseignés/total. Le recalcul complet du classement reste proposé après fourniture de cette vue.
