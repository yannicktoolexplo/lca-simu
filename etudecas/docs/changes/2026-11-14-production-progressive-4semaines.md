# Production progressive et besoin sur quatre semaines — 14 novembre 2026

Référence du code : `900c06dcb8e74a955bdd4cf3fbed92258b70bea2`. Aucun changement du moteur, des données sources ou du nominal. La question est celle de l’utilisateur : une répartition du besoin mensuel sur quatre semaines expliquerait-elle une production réelle plus progressive ?

[Rapport avec courbes hebdomadaires](../../resultats/production_progressive_4sem_20261114.html) · [Preuves finales](../../artifacts/testing/production_progressive_4sem_20261114/final_manifest.json)

## Ce qui est établi

Pour 268967, sur 36 semaines complètes communes connues de 2025, la production estimée depuis les étuis est positive 24 semaines ; l’archive simulée du 9 novembre contient 9 semaines de travail et 8 semaines de nouveaux lots achevés. La part du volume concentrée sur les quatre semaines consécutives les plus chargées est respectivement 23,08 %, 38,57 % et 33,33 %. Les trous interrompent les fenêtres ; les sommes ne sont pas des totaux annuels certifiés. Le récent témoin hebdomadaire 135 jours donne aussi un écart, sur 11 semaines comparables : 6 positives réelles estimées contre 1 simulée. Ces archives ne sont pas deux variantes appariées.

L’écart dépasse donc l’affichage par lots. Pour 268091, il est moins marqué : 32 semaines positives réelles contre 29 achevées simulées sur 46 semaines communes, ordres initiaux inclus. Ceux-ci apportent 1945715 unités ; ne pas les retirer en assimilant le travail nouveau à toute la production.

Le champ `released_qty` peut représenter une disponibilité différée, notamment après contrôle ou pour un ordre initial. Les événements de lots ont été utilisés pour séparer achèvement physique et disponibilité. Les valeurs réelles restent des estimations à partir des étuis, pas des déclarations d’ordres achevés. Le travail archivé contient des fractions d’unité équivalente, conservées sans les transformer en unités physiques entières.

## Les règles ne sont pas interchangeables

1. **Consommation mensuelle** : prévision connue au début du mois moins demande réelle déjà arrivée, puis répartition du reste sur les jours restants. Un mois n’est pas toujours quatre semaines. Le code courant garde le mode hebdomadaire par défaut ; le mensuel reste candidat explicite.
2. **Moyenne du signal sur 28 jours** : modifie le signal local préparatoire. Le lancement réel repose ensuite sur les besoins datés, les stocks, les engagements et les lots. Ce n’est pas un programme mensuel découpé en quatre ordres.
3. **Nivellement de production sur quatre semaines** : choix d’un programme admissible de travail/lots. Aucun nouveau mécanisme de ce type n’a été installé ici.
4. **Horizon figé 4/8 semaines** : restriction de modification du programme, pas obligation de produire la même quantité chaque semaine.

Exemple sans protection supplémentaire : demande 1000 − stock disponible 300 − réception ferme 200 = nouvelle fabrication 500. Une quantité de 125 par semaine est un programme manuel possible si les 200 arrivent en semaine 3 : stocks de fin 175/50/125/0. Un besoin urgent ne doit pas être étalé arbitrairement ; un lot indivisible doit rester entier.

Oracle natif avec lot 107800, stock 107800 et ferme 107800 à J14 : besoin 431200 concentré à J28 → deux propositions de 107800 lancées J25/J25 ; même besoin réparti en quatre échéances →J18/J25. Le volume 215600 est conservé. `grouping_days=28` regroupe au contraire les deux nouveaux lots vers J18/J18 : ce paramètre ne nivelle pas. Une cadence de 65 unités de travail pendant quatre semaines, avec lots 100, laisse 200 finies + 60 encours ; ce n’est pas 260 produits finis livrables.

## Deux simulations courtes comparées au témoin qualifié

| Essai synthétique | Travail semaines 1 / 2 / 3 / 4 | Produits finis achevés | En cours à la fin | Livré / demandé | Retard cumulé (unités-jours) |
|---|---|---|---|---|---|
| Témoin : consommation hebdomadaire | 100 / 125 / 75 / 50 | 300 | 50 | 270 / 290 | 620 |
| Moyenne du signal sur 28 jours | 100 / 125 / 75 / 50 | 300 | 50 | 270 / 290 | 620 |
| Consommation mensuelle des prévisions | 100 / 100 / 100 / 75 | 300 | 75 | 270 / 290 | 800 |

Cas synthétiques du 1er au 28 janvier, capacité 25 unités/jour, lots 100, demande physique 290 identique. Les semaines du tableau sont des blocs de sept jours depuis le 1er janvier ; les métriques industrielles utilisent lundi–dimanche.

- Signal 28 jours : le consommateur reçoit 11,25 au lieu de 22,857 à J10, mais sept CSV physiques sont identiques au témoin.
- Mensuel : lancements J1/10/16/25 au lieu J1/9/13/26. Travail un peu plus régulier mais + 25 encours ; 300 finis et 270 livrés au total. Le calendrier du service se dégrade : livraisons 20/40/210/0 contre 20/40/160/50, soit 50 unités reportées de la troisième à la quatrième semaine. Somme quotidienne des unités encore attendues : 620→800 unités-jours ( + 180). Ce n’est pas une quantité de ventes perdues. Les 20 unités en retard final sont en transit vers les clients. Le mensuel ne peut pas être déclaré globalement meilleur sur cet essai.
- Budget mensuel 320 = 295 issus des périodes couvertes +25 par repli déclaré sur une prévision connue ; 30 restent après 290 demandées au 28 janvier. Cette reconstruction n’est pas un export mensuel ERP.

## Validation et limites

Deux exécutions nouvelles d’environ 111 secondes chacune ; témoin précédent réutilisé après vérification de compatibilité des 646 empreintes de code, du graphe et des traces. 7 pytest ciblés,21 contrôles mémoire et 33 contrôles auteur sur CSV. Contre-revue indépendante et qualifications référencées dans le manifeste final. Aucun résultat d’archive n’est présenté comme un rejeu courant.

Deux erreurs initiales d’agrégation des archives ont été conservées : interprétation trop étroite de `released_qty` et lecteur indépendant excluant des codes article/site stockés comme texte. 23/138 diagnostics de quantité libérée divergent des nouveaux lots et 31/138 des achèvements totaux ; ces diagnostics ne sont pas 138 tests réussis.

Les mini-réseaux ont des sécurités nulles et une nomenclature simple explicitement synthétiques ; les sécurités industrielles restent intactes. Le contrôle PF au dépôt est exclu et le stock global hors graphe 107800 reste isolé. Pas de nouvelle campagne annuelle, de capacité calibrée, d’aléa ajouté ou de réouverture des formats MP/packaging. Navigateur et tests interdits non exécutés. Le contrôle documentaire généré reste traité séparément ; un refus ne compte pas comme réussite.

## Suite

La répartition mensuelle est une piste, pas encore la cause démontrée du calendrier de 268967. Le prochain essai de programme hebdomadaire doit conserver les volumes, placer des lots entiers, préserver les besoins urgents, les fermes, les sécurités et les disponibilités, puis comparer travail, achèvements, stocks et service. Il faut distinguer effet d’un programme plus régulier et effet d’une capacité machine réellement disponible plus faible. Les dates de lancement/fin des ordres industriels et l’occupation de la machine restent les preuves discriminantes manquantes. Les défauts techniques de provenance/export précédemment identifiés restent au backlog ; cette investigation ne les corrige pas.
