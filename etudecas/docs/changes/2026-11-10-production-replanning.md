# Révisions du programme de production — 10 novembre 2026

Le taux de révision du programme prévisionnel simulé est maintenant mesurable
dans le nominal courant, les sensibilités et leurs consommateurs cartographiques.
Il ne s'agit pas du taux industriel de révision des ordres de fabrication.

## Définition et correction

> **Taux = comparaisons modifiées / comparaisons actives identifiées.**
> Une comparaison rapproche les publications de deux jours consécutifs du même
> programme site/article/semaine, sur les mêmes dates couvertes. « Modifiée »
> signifie qu'une quantité ou une date cible change, une seule fois par
> comparaison. « Active » signifie qu'au moins une des deux cibles est positive.

La première cible positive crée un programme ; elle est exclue. L'exécution
normale conserve la cible totale grâce au crédit de campagne et ne devient pas
une révision. Les publications nulles inactives et les changements de couverture
sont exclus. Un journal incomplet ou un dénominateur nul restent inconnus.
Les programmes ont un poids égal ; on n'additionne pas les KG et les UN.
Les recommandations échues conservent leur date brute : le suivi ne les décale
pas au lendemain. Les changements annulés avant la clôture ne sont pas observés.

Deux erreurs de l'ancien calcul ont été reproduites en mémoire : une date cible
entrant dans l'identité masquait les déplacements de date ; un dénominateur en
journées pouvait donner 200 % pour deux programmes modifiés. Le nouveau calcul
est borné entre 0 et 100 %. Les attentes de matière et les passages physiques
ne remplacent plus les révisions inconnues dans les vues modifiées de la carte.

Le nominal actuel engage une campagne lors de sa création, parfois avant tout
travail physique. Son journal utilise donc la base distincte
`simulated_weekly_launch_programme_authorization_v1` : un engagement ne prouve
aucune fabrication ou consommation. Le mode optionnel d'engagement au premier
travail conserve `simulated_weekly_launch_programme_v1`. Ces bases ne sont pas
mélangées. Aucune politique physique, donnée source ou règle MRP n'a été changée.

## Résultats bornés et contrôles exécutés

Référence : `coherent-MRP-20261014`, branche de départ `dev_yannick`, commit
`49bf3ecc5a833e206ada46cae1999b9ae9210717` et modifications identifiées par les
empreintes des preuves. Le témoin de préparation est
`artifacts/testing/cc20261109/nominal/run_manifest.json`. Les copies historiques
préservent les données physiques et ne reconduisent pas implicitement les
hypothèses prospectives.

Trois essais de 21 jours, sur les mêmes sources gelées : suivi désactivé,
suivi activé, puis demande globale multipliée par deux. Les décisions observées
vont du 1er au 21 janvier 2025 ; les programmes prévisionnels incluent également
les semaines futures de l'horizon MRP de 364 jours.

| Cas | Comparaisons modifiées / actives | Taux |
| --- | ---: | ---: |
| Nominal | 418 / 1 482 | 28,2051 % |
| Demande ×2 | 735 / 2 319 | 31,6947 % |
| Même population de comparaisons, nominal | 361 / 1 315 | 27,4525 % |
| Même population de comparaisons, demande ×2 | 390 / 1 315 | 29,6578 % |

L'effet subsiste sur les comparaisons communes : +2,2053 points. Le changement
du taux usuel inclut aussi un changement de population active. La demande
effective vaut 215 001 puis 430 001 UN : les 106 lignes hebdomadaires sont
exactement doublées ; l'écart d'une unité avec le double du total nominal
provient de l'allocation entière de la première semaine partielle. Chaque jour
a été reconstruit indépendamment, sans tolérance ajoutée pour faire passer le
contrôle.

Les neuf fichiers physiques comparés, dont les campagnes et les deux suivis
de lots, ainsi que dix KPI de quantités et coûts sont identiques entre suivi
activé et désactivé. Les crédits de campagnes sont rapprochés indépendamment
du registre de campagnes. Cela démontre l'absence d'effet physique du suivi
sur ce cas court, pas sur tous les horizons.

- 93 cas pytest ciblés : réussis, après relecture des cas et hooks ; aucune
  suite globale ni injection d'intégrité. Deux avertissements préexistants
  d'échappement dans le gabarit HTML restent présents.
- 99 contrôles indépendants en mémoire et 51 contrôles de lecture native :
  réussis. Calculs Decimal/Fraction distincts des helpers de production.
- Environnement toolbox : vérifié. JavaScript réellement extrait du gabarit
  exécuté en mémoire V8 : inconnues, zéro, bornes et classement de même base.
- Qualification globale ON/stress : **refusée**, sur déclaration/provenance F3
  et, dans le stress, disponibilités sans transfert correspondant. Aucun
  contrôle déterministe n'a été affaibli. La référence n'est pas promue.
- Vérification documentaire : refus d'obsolescence de références générées
  conservé. Navigateur/Node non exécutés, conformément à la restriction issue
  du refus antérieur ; aucune certification du rendu ou du DOM.

Un premier essai de 56 jours avait publié un taux inconnu car le suivi exigeait
un autre mode d'engagement. Ses preuves sont conservées et ne comptent pas comme
qualification du taux. Le correctif observe le mode existant, au lieu d'imposer
une autre règle au nominal. L'essai court ci-dessus vérifie l'activation réelle.

## Livraison et reprise

- [Règles de mesure et commandes](../../OPERATIONS.md#mesure-des-révisions-de-production).
- [Bilan court, exemples de versions cliquables](../../resultats/replanification_production_20261110/bilan.html).
- [Manifeste des preuves locales](../../artifacts/testing/replanification_production_20261110/final_manifest.json) : `artifacts/testing/replanification_production_20261110/`
  (manifeste final et reçus des contrôles), sorties natives sous
  `artifacts/testing/rp20261110_native21_21b619fa/`.

Le journal `data/production_programme_snapshots.csv` et son contrat dans le
résumé restent conservés par les sensibilités. Le runner adaptatif recalcule
un témoin au même horizon quand l'ancien nominal n'a pas ce journal, puis
refuse les variantes si un indicateur requis demeure inconnu.

Prochain essai : sensibilité séparée aux capacités et aux stocks de production
sur 2025, avec suivi des taux et de leur population comparable. Ne pas exiger
qu'un coût de possession seul change les décisions physiques. Le traitement
des refus F3/transferts reste un chantier distinct avant toute qualification
globale ou reprise de la campagne complète. Aucune nouvelle campagne Monte
Carlo, annuelle ou de cinq ans n'a été exécutée pour ce correctif.
