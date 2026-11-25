# Compléments achats et disponibilité

Complément du 25 novembre 2026. Origine : lecture des pièces publiques de `ICs/` au commit `REV-0415`, veille primaire consultée le 25 novembre 2026 et calculs complémentaires exécutés. Destinataires : ingénieurs et gestionnaires de projet en achats, qualité et planification, accompagnés par la supervision. Ces notes sont des amorces : lire les pratiques, reprendre le mini-essai, puis choisir avec la supervision si la lecture scientifique mérite un prolongement. Les exemples ajoutés ci-dessous sont pédagogiques. Ils ne constituent ni les données originales des simulations ni une validation industrielle.

## 02 Quelle quantité acheter à la source de dépannage

**Question à trancher.** Quel est le plus petit ordre réellement achetable et utilisable avant le besoin, et quelle action déclencher si ce volume dépasse la capacité de la source courte ?

**Acquis exact.** [Cahiers métier, lignes 13 à 17](https://github.com/yannicktoolexplo/lca-simu/blob/partage/cahiers-ic-anonymes/ICs/Cahiers-metier.md#L13-L17) : 46 configurations sur 60 évitent une rupture grâce à une répartition entre deux sources ; le besoin court publié passe de 800 à 900 kg lorsque la première livraison n’est utilisable qu’à 90 %. Le premier rapport est recalculé à **76,67 % des configurations examinées**, sans l’interpréter comme une probabilité de succès en exploitation. Le cahier établit déjà l’effet de la réception qualité. Les ordres, dates et contraintes des 60 configurations ne sont pas fournis.

**Lectures métier et effet concret.**

- Microsoft, [Default order settings for dimensions and product variants](https://learn.microsoft.com/en-us/dynamics365/supply-chain/production-control/default-order-settings), mise à jour du **10 juillet 2025** : minimum, multiple de commande, maximum, site et délai constituent des paramètres de l’ordre. En entretien achats, demander le conditionnement réellement accepté pour cette référence et ce site, plutôt qu’un seul « minimum fournisseur ».
- Microsoft, [Quality orders](https://learn.microsoft.com/en-us/dynamics365/supply-chain/inventory/quality-orders), mise à jour du **26 octobre 2026** : le contrôle peut bloquer la quantité testée ou l’ensemble reçu selon le paramétrage. En revue réception, demander quelle quantité est libérée, par quelle preuve et à quelle date. La documentation récente décrit aussi les ordres en transit et précise leurs conditions de version ; cette capacité ne doit pas être supposée disponible dans l’ERP local.

**Lecture scientifique facultative.** Akkerman et al., [Solving Dual Sourcing Problems with Supply Mode Dependent Failure Rates](https://arxiv.org/html/2410.03887v2), version auteur du **11 avril 2025**, [publication IJPR](https://doi.org/10.1080/00207543.2025.2489755). Dans leur étude de pièces de rechange du secteur énergétique, des politiques évaluées par simulation font mieux que leur témoin dans **91,1 % des instances**, avec des économies moyennes allant jusqu’à **22,6 %** selon la politique. Résultat des auteurs, non reproduit ici. Ce cas concerne la fiabilité des pièces en service, pas leur rendement à réception : il invite à demander si la source courte change aussi les remplacements futurs, sans justifier une méthode d’apprentissage pour le présent calcul simple.

**Essai exécuté sur un nouvel exemple pédagogique.** À l’ouverture de J0, l’acheteur connaît un besoin ferme de **1 850 kg en J10**, **150 kg utilisables non réservés**, un arrivage long de **1 000 kg**, ainsi qu’une source courte libérable en J9. Son minimum est 400 kg, son multiple 200 kg et sa capacité disponible jusqu’à J10 est 800 kg. Le rendement court est supposé de 100 %. Chaque ligne est un scénario d’information disponible à J0.

| Arrivage long utilisable en J10 | Manque net en kg | Plus petite commande courte en kg | Conclusion avec capacité de 800 kg |
| --- | ---: | ---: | --- |
| 1 000 kg soit 100 % | 700 | 800 | Couvre le besoin |
| 900 kg soit 90 % | 800 | 800 | Couvre le besoin sans marge |
| 700 kg soit 70 % | 1 000 | 1 000 | Irréalisable avec cette capacité |
| Libération après J10 donc 0 kg | 1 700 | 1 800 | Irréalisable ; 900 kg restent manquants même après achat de 800 kg |

Calcul exécuté : `manque = max(0, besoin − stock utilisable − arrivage libéré avant échéance)`. Pour un manque positif, `commande = 200 × plafond(max(400, manque) / 200)` ; sinon zéro. **Dans cet exemple**, le passage de 100 % à 90 % modifie le manque, mais pas l’ordre de 800 kg : le multiple absorbe l’écart. On ne peut donc pas transférer mécaniquement le supplément de 100 kg du cahier à toute commande.

**Décision et données à demander.** Appliquer d’abord ce calcul daté simple. La ligne à 70 % impose une dérogation de capacité, une autre source ou une nouvelle promesse. Pour rejouer le cas réel : vue référence–site–échéance, demande ferme et réservations, quantités par lot, dates d’arrivée et de libération connues lors de la décision, MOQ, multiple, plafond réellement disponible, délai et coût du dépannage. Un délai de libération incertain doit rester un scénario, pas une réception certaine.

## 03 Quel renseignement manque réellement pour décider d’un audit

**Question à trancher.** Quel justificatif peut modifier les trois visites retenues, notamment lorsque plusieurs cotations sont incertaines en même temps ?

**Acquis exact.** [Cahiers métier, lignes 19 à 23](https://github.com/yannicktoolexplo/lca-simu/blob/partage/cahiers-ic-anonymes/ICs/Cahiers-metier.md#L19-L23) : l’exercice contient 84 cotations ; 16 peuvent changer la sélection lorsqu’on les laisse successivement inconnues. Le calcul exécuté `16 / 84` donne **19,05 % des cotations**, pas 19,05 % des fournisseurs ni une probabilité de défaillance. La grille, ses poids, ses bornes et les règles d’ex æquo ne sont pas publiés : les 16 résultats individuels ne sont pas reproductibles avec ces seules lignes.

**Lectures métier et effet concret.**

- ISO, [ISO 19011 édition 2026](https://www.iso.org/standard/19011), **mai 2026**, publication enregistrée au **27 mai 2026** : la référence courante pour organiser les audits est désormais la quatrième édition. La [communication ISO TC176 du 9 juin 2026](https://committee.iso.org/sites/tc176/home/news/content-left-area/news-and-updates/iso-19011-2026-released.html) souligne les risques et les environnements numériques. Pour préparer une visite, consigner l’objectif, les preuves recherchées et les possibilités de collecte à distance. Ces pages publiques ne décrivent pas une formule obligatoire de sélection ; aucune règle chiffrée ne leur est attribuée ici.
- Commission européenne JRC, [Step 8 Sensitivity analysis](https://knowledge-for-policy.ec.europa.eu/composite-indicators/toolkit_en/navigation-page/10-step-guide_en/step-8-sensitivity-analysis_en), mise à jour du **1er décembre 2020** : la robustesse d’un classement dépend aussi des hypothèses de données, pondération et agrégation. L’application à la grille fournisseurs est une adaptation proposée : figer les poids pour tester les preuves, puis examiner séparément la sensibilité aux choix de méthode. C’est une référence méthodologique durable, pas une nouveauté 2026.

**Lecture scientifique facultative.** Saisana, Saltelli et Tarantola, [Uncertainty and Sensitivity Analysis Techniques as Tools for the Quality Assessment of Composite Indicators](https://publications.jrc.ec.europa.eu/repository/handle/JRC31318), **2005**, notice JRC datée du 1er décembre : application à l’indice de réalisation technologique des Nations unies pour examiner la fiabilité des classements. Le terrain est différent des audits fournisseurs. Le résultat utile est une façon de vérifier la stabilité du message d’un classement, pas un gain de performance annoncé pour notre grille.

**Essai exécuté sur une nouvelle grille pédagogique.** Trois visites sont disponibles pour quatre dossiers anonymes. Les scores élevés passent d’abord. À la décision, les deux premiers scores sont certains : A = 90, B = 80 points. C vaut `70 + x`, avec `x` entre −2 et 0 point ; D vaut `65 + y`, avec `y` entre 0 et 4 points. Les poids sont déjà intégrés à ces points et restent constants.

| Valeurs testées en points | Score C | Score D | Troisième visite possible |
| --- | ---: | ---: | --- |
| Témoin x = 0, y = 0 | 70 | 65 | C |
| x = −2 seul | 68 | 65 | C |
| y = 4 seul | 70 | 69 | C |
| x = −2 et y = 4 ensemble | 68 | 69 | D |
| x = −2 et y = 3 | 68 | 68 | C ou D ; ex æquo à conserver |

Ce contre-exemple ne remet pas en cause les 16 cotations du cahier. Il montre pourquoi **une analyse cotation par cotation ne prouve pas la stabilité face aux incertitudes simultanées**. Ici, aucun changement isolé depuis le témoin ne suffit ; les deux réunis font changer la visite. Le résultat qui ferait basculer la décision est la disparition de toute configuration plausible qui échange C et D.

**Décision et données à demander.** Conserver la méthode simple du cahier comme premier filtre, puis tester les combinaisons des quelques dossiers proches du seuil. Demander la grille versionnée référence–critère, sens des échelles, poids, bornes plausibles justifiées, document attendu, dépendances entre cotations, contraintes de visite et traitement des ex æquo. Sans probabilités et coût de collecte, on peut identifier une information décisive ; on ne peut pas chiffrer sa valeur économique ni affirmer quel justificatif est rentable à obtenir.

## 04 Combien de jours le dépôt peut il encore servir

**Question à trancher.** Le dépôt peut-il tenir chaque échéance sans interruption, compte tenu du transfert, des réservations et de la libération qualité ?

**Acquis exact.** [Cahiers métier, lignes 27 à 31](https://github.com/yannicktoolexplo/lca-simu/blob/partage/cahiers-ic-anonymes/ICs/Cahiers-metier.md#L27-L31) : le dépôt couvre quatre jours ; ajouter le stock amont donne cinq jours de quantité, sous condition d’arrivée à temps. Cette distinction suffit déjà pour exclure une promesse fondée uniquement sur le stock physique total. Le solde journalier des flux originaux n’est pas disponible.

**Lectures métier et effet concret.**

- Oracle, [Promise Only After You Release Holds On Lots](https://docs.oracle.com/en/cloud/saas/supply-chain-and-manufacturing/26a/fascp/promise-only-after-you-release-holds-on-lots.html), documentation **version 26A de 2026**, page sans date propre affichée : la disponibilité d’un lot est datée ; l’exemple de transfert combine levée de blocage et trajet entre sites. Pour la promesse client, demander la première arrivée utilisable au dépôt, avec calendrier et préparation, plutôt que la seule date de sortie usine. Cette lecture confirme une pratique opérationnelle ; elle n’impose pas d’acheter ce logiciel et n’établit pas la date d’introduction de la fonction.
- Microsoft, [Net requirements and pegging information](https://learn.microsoft.com/en-us/dynamics365/supply-chain/master-planning/planning-optimization/net-requirements), mise à jour du **21 juillet 2025** : les besoins nets rapprochent réceptions et consommations datées et permettent de remonter aux demandes couvertes. Une modification d’ordre peut nécessiter un nouveau calcul avant d’apparaître dans la vue. En revue planification, relever l’horodatage du calcul et le plan retenu. C’est la vérification récente à apporter à l’usage de la vue, plutôt que de supposer son actualisation immédiate.

**Lecture scientifique facultative.** Simchi-Levi et al., [Identifying Risks and Mitigating Disruptions in the Automotive Supply Chain](https://dspace.mit.edu/entities/publication/d44ef29a-78b6-4ec5-a537-d6e4c4f3f55a), *Interfaces*, **2015**, dépôt auteur daté d’octobre : l’application automobile identifie des expositions jusque-là peu reconnues et compare des actions avant et après perturbation. Le prolongement proposé est de relier la première date de manque à un scénario d’arrêt amont ; notre calcul de six jours ne reproduit pas cette étude de réseau.

**Essai exécuté sur un nouveau cas pédagogique.** À J0, le stock libre et libéré du dépôt est **40 unités**, la demande ferme vaut **10 unités par jour**, et le stock amont transférable vaut **10 unités**. Aucun autre arrivage ni remplacement n’intervient. Deux options connues à J0 sont comparées : arrivée utilisable à l’ouverture de J5 ou à l’ouverture de J6. Les jours sont des jours du modèle sans fermeture. Le seuil de décision est le premier solde projeté négatif, ce qui interdit de masquer un manque antérieur par un arrivage tardif.

| Jour après consommation | Besoin cumulé en unités | Solde avec arrivée J5 en unités | Solde avec arrivée J6 en unités |
| --- | ---: | ---: | ---: |
| J1 | 10 | 30 | 30 |
| J2 | 20 | 20 | 20 |
| J3 | 30 | 10 | 10 |
| J4 | 40 | 0 | 0 |
| J5 | 50 | 0 | −10 |
| J6 | 60 | −10 | −10 |

Calcul exécuté : `solde projeté(j) = 40 + réceptions utilisables cumulées(j) − 10 × j`. Le dénominateur du ratio statique est 10 unités/jour : `(40 + 10) / 10 = 5 jours de quantité`. Pourtant l’option tardive ne permet que **quatre jours consécutifs complets** avant le manque de 10 unités en J5 ; l’option avancée en permet cinq. Un solde négatif représente un besoin non couvert, jamais un stock physique négatif.

**Décision et données à demander.** Si l’engagement porte sur J5, retenir l’arrivée avancée sous réserve de sa faisabilité et de son coût ; si aucune option ne la permet, modifier la promesse. La somme des stocks ne départage pas ces options. Pour le cas réel, demander une vue dépôt–référence–jour ou heure selon les échéances : stock libre par statut, réservations et commandes avec échéances, quantité transférée, départ et arrivée, délai de réception, libération qualité, calendrier et date de connaissance de chaque événement. La réception ne doit être comptée qu’une fois, au lieu où elle peut servir la demande.

## Reproduction

Les résultats numériques et les références sont structurés dans [themes-02-04.json](themes-02-04.json). Le script [calculs-02-04.py](calculs-02-04.py) recalcule ces exemples sans dépendance extérieure. Il ne lit aucune donnée industrielle et ne rejoue pas les simulations originales.
