# 09 Choisir une règle de relance du transitaire

Complément de veille et de calcul du 25 novembre 2026 pour un gestionnaire transport. Les comptages sources sont des simulations agrégées. Les recalculs de cette note sont des compléments du jour.

## Ce qui est déjà acquis

[Cahiers métier](../Cahiers-metier.md), lignes 59 à 63 ; [cas fret](../Cas/Alertes-fret.md), lignes 3 et 13 à 31. Le service insuffisant est une masse servie strictement inférieure à 99 % de la masse demandée. La règle à la fin du mois précédent utilise seulement ce qui est alors connu. Le CSV fournit 956 décisions mensuelles simulées, 273 mois dégradés et 683 autres, ventilés en deux périodes. Le seuil 4,14 compare **uniquement** saturation 95 % et persistance. Cet acquis est déjà suffisant pour cette comparaison.

**Question à trancher.** Quel volume de dossiers accepte-t-on d'ouvrir, et combien coûte un mois dégradé non signalé par rapport à une relance injustifiée ? Une relance ne supprime pas nécessairement le retard : le jeu mesure la détection, pas l'efficacité de l'action.

## Lectures métier et méthodes nouvelles

IATA/Cargo iQ, *Master Operating Plan*, documentation ONE Record version juillet 2025, [page primaire](https://iata-cargo.github.io/ONE-Record/2025-07/Orchestration/orchestration-mop/), ouverte le 25 novembre 2026. Le plan distingue départ, arrivée et remise au destinataire. En entretien avec le transitaire, demander le jalon manqué, l'horaire prévu, l'horaire effectif et l'heure à laquelle l'information était disponible. L'heure d'un événement et celle de sa notification répondent à deux questions différentes.

Évolution vérifiée : IATA, [note de version ONE Record](https://iata-cargo.github.io/ONE-Record/development/General/release-note/), version annoncée le 25 juillet 2026, ouverte le 25 novembre 2026. L'introduction annonce ontologie 3.3.0 et API 2.3.0, standard privilégié depuis le 1er janvier 2026 ; la page détaille notamment le suivi horodaté des changements de statut d'une demande d'action. Pour un gestionnaire, le complément utile est de demander un export qui conserve les historiques et dates d'annonce. Il n'est pas nécessaire de développer une interface informatique pour commencer. La page est évolutive : conserver la version employée dans tout projet de mise en œuvre.

La recherche sur la prévision d'envois et les données qu'elle nécessite est présentée dans le [complément bibliographique](bibliographie-recherche.md). Elle constitue une piste de lecture, pas un modèle déjà entraîné dans ce travail.

## Essai exécuté et décision qui change

Les données suffisent pour comparer toutes les règles du CSV. On fixe avant calcul `coût = FP × coût d'une fausse alerte + FN × coût d'un mois manqué`. Le coût des revues justifiées est d'abord fixé à zéro pour retrouver la comparaison publiée. Les coûts sont hypothétiques ; aucun coût industriel n'a été mesuré.

| Règle | Rappel TP / 273 mois dégradés | Précision TP / dossiers ouverts | Dossiers ouverts / 956 décisions | FP | FN |
| --- | ---: | ---: | ---: | ---: | ---: |
| Saturation 90 % | 94,14 % | 29,24 % | 879 / 956 | 622 | 16 |
| Saturation 95 % | 91,94 % | 28,95 % | 867 / 956 | 616 | 22 |
| Saturation 99 % | 90,48 % | 28,79 % | 858 / 956 | 611 | 26 |
| Persistance | 49,82 % | 49,28 % | 276 / 956 | 140 | 137 |
| Aucune alerte | 0 % | Indéfinie | 0 / 956 | 0 | 273 |

Recalcul demandé : `(616−140)/(137−22) = 476/115 = 4,13913`. Mais en comparant les **cinq** règles, la meilleure est aucune alerte pour un rapport de coûts inférieur à `140/136 = 1,02941`, puis persistance, puis saturation **90 %** au-delà de `482/121 = 3,98347`. Aux seuils, les deux règles voisines sont à égalité. Les seuils 95 % et 99 % ne sont jamais les moins coûteux dans ce modèle précis.

Exemple de lecture : à un coût de fausse alerte de 1 unité et de mois manqué de 4 unités, persistance vaut `140+137×4=688`, saturation 95 % vaut `616+22×4=704`, saturation 90 % vaut `622+16×4=686`. Le seuil 4,14 ne doit donc pas devenir une recommandation générale de saturation 95 %.

Contrôle de bon sens supplémentaire, dérivé des totaux : ouvrir systématiquement une revue donne TP=273, FP=683 et FN=0. Si une revue justifiée ne coûte rien et si l'équipe peut toutes les traiter, cette option devient la meilleure dès `543/137 = 3,96350` face à la persistance. Ce résultat montre les limites du modèle de coût : renseigner coût de traitement de **tous** les dossiers et capacité de l'équipe avant de recommander un fonctionnement réel. Le tableur permet ce changement d'hypothèse.

La part de mois dégradés passe de 90/476=18,91 % à 183/480=38,125 %. À rapport de coûts égal à 4, persistance est meilleure parmi les cinq règles sur la première période, saturation 90 % sur la seconde. Une règle unique n'est pas validée hors échantillon. Les trajectoires apparentées n'autorisent ni 956 observations indépendantes ni une conclusion causale sur les retards évités.

## Suite réaliste pour l'intervenant

Commencer par un tableau de revue mensuelle et un entretien coût/charge avec l'exploitation. Pour tester l'alerte sur un nouveau périmètre, demander une ligne par mois et scénario ou ligne métier : demande, masse servie, plafond express, consommation, dates de clôture et de connaissance, règle déclenchée et dossier traité. Pour une urgence d'envoi : identifiant anonyme, origine/destination, jalons prévus/réalisés, annonce du report, départ de remplacement, dernier instant d'action possible, action, coût et résultat. Sans ces données, une nouvelle prédiction par expédition reste un essai proposé.
