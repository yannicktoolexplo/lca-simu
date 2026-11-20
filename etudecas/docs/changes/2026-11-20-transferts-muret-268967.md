# Apports à Muret et engagements d’avril pour 268967

Entre le 17 mars et le 27 avril 2025, le bilan physique à Muret impose
**au moins 112 695 unités d’apports**, soit **4 895 de plus** que le lot
simulé de 107 800 unités, même si celui-ci est entièrement fractionné.
Ce minimum découle des relevés de stock et des ajustements déclarés.
Il suppose que les autres variations relèvent d’entrées et sorties du
périmètre suivi. Le chiffre reste valable sans hypothèse de service client.
[Contrôle indépendant sur les classeurs](../../artifacts/testing/transferts_muret_268967_20261120/validator/receipt_lower_bound.json)

| Semaine commençant le | Stock à l’ouverture → relevé suivant | Apport minimal | Apport si la demande de la semaine a été livrée | Réception du lot simulé |
| --- | ---: | ---: | ---: | ---: |
| 17 mars | 735 467 → 743 556 | 8 089 | 40 824 | 0 |
| 24 mars | 743 556 → 775 542 | 31 986 | 63 504 | 107 800 |
| 31 mars | 775 542 → 747 609 | 0 | 5 920 | 0 |
| 7 avril | 747 609 → 709 197 | 0 | 0 | 0 |
| 14 avril | 709 197 → 742 819 | 33 622 | 34 881 | 0 |
| 21 avril | 742 819 → 781 817 | 38 998 | 38 998 | 0 |
| Total des apports | | **112 695** | **184 127** | **107 800** |

Le calcul soustrait les ajustements signés de la variation de stock, puis
retient les hausses positives semaine par semaine. Pour les six lignes,
les ajustements sont nuls et les variations recoupent exactement le
mouvement net enregistré dans `Flow_Data_Inventory_movements.xlsx`,
`Feuille1!I808:I813`. Les photos viennent de l’onglet `Stocks`, cellules
`E83, E72, E28, E61, E102, E22, E104`. L’estimation à 184 127 ajoute la
demande hebdomadaire comme hypothèse de sorties clients. Au relevé du
5 mai, le minimum cumulé monte à 123 899 unités. Cette dernière semaine
dépasse la fenêtre commune avec le calcul natif.

## Essais de fractionnement

- **Départ après achèvement de tout le lot.** Le lot simulé finit le
  28 mars et arrive le 30 mars. Tout découpage réalisé après la fin
  échoue à expliquer la hausse déjà présente le 24 mars. Si on conserve
  l’arrivée du 30 mars, les trois autres semaines positives nécessitent
  au minimum 80 709 unités d’apports hors de cette livraison.
- **Départs dès la fin de chaque tranche journalière.** En accordant aux
  dix tranches de travail la capacité hypothétique de devenir des produits
  finis aussitôt, 53 900 unités pourraient arriver avant le relevé du
  24 mars. Le calendrier de la première hausse devient compatible.
  Jusqu’au relevé du 7 avril, les minima physiques peuvent tenir dans
  107 800 unités. En supposant la demande entièrement livrée, le bilan
  exige déjà 110 248 unités sur ces trois semaines. Jusqu’au 28 avril,
  les constats de stock réclament à eux seuls au moins 4 895 unités de plus,
  même en accordant une liberté totale sur les dates de fractionnement.

Le MRP contient 40 824, 99 792, puis 110 248 unités déjà physiques à
disponibilité future dans les versions du 23 mars, 30 mars et 6 avril
(`Flow_Data_MRP_results.xlsx`, `Feuille1!J11614,J12634,J13635`).
Les versions photographient un état et les entrées planifiées ne sont
pas des réceptions exécutées. L’égalité à 110 248 avec le bilan
conditionnel de mars est une concordance. L’augmentation des quantités
déclarées ne permet pas de dater les réceptions. Le carnet partiel ne
contient aucune ligne 268967. Il manque toujours les identifiants d’ordre
et de lot sur les départs usine et les entrées dépôt.
[Comparaison des quantités et des dates](../../artifacts/testing/transferts_muret_268967_20261120/comparison.json)

## Une piste de planification antérieure à avril

Le MRP du **12 janvier** porte simultanément trois besoins à l’usine
1430, aux repères des **16 mars, 30 mars et 13 avril**. Chaque repère
indique 110 495 étuis et 23 424,94 mètres de l’autre emballage au ratio
exact de la nomenclature (`Feuille1!I1605,I1607,I1608,I1856:I1858`).
Le MRP du 9 février montre un besoin au repère du 6 avril, connu 57 jours
avant le lundi 7 avril. Le 16 février, deux besoins coexistent aux repères
du 6 et du 20 avril. Le besoin du 20 avril est visible 64 jours avant le
lundi 21 avril. Ils soutiennent plusieurs créneaux de conditionnement.
Ces valeurs de besoin restent des observations de planification et les
ordres qui les auraient couverts ne sont pas identifiés.

En avril, les prélèvements de deux emballages corroborent une reprise du
travail. Les semaines du 14 et du 21 avril cumulent **165 920 étuis** et
**33 920 mètres**, soit **160 000 unités équivalentes** pour le second
emballage d’après la nomenclature (`Inventory_movements`,
`Feuille1!J858:J859,J1165:J1166`). Ce rapprochement ne date pas la fin du
travail ni l’entrée à Muret et ne dénombre pas les lots.

Dans le calcul natif, les deux ordres 268967 suivants sont figés le
1er avril pour lancement le **26 mai**. Aux 7, 14 et 21 avril, 1430
dispose de **12 200 unités utilisables** du composant 344135 pour **107 800
requises** par un nouveau lot standard. Avancer un ordre à stock et
approvisionnements inchangés est donc insuffisant dans ce calcul.
La prochaine expérience doit tester un engagement usine supplémentaire
connu avant le gel, avec le recalcul de ses achats. Elle devra vérifier
l’entrée et la libération du 344135 à temps, puis le départ, la réception
et la disponibilité du produit fini. Le nombre de lots ou de fractions
reste subordonné à un journal de transferts exécutés.

Le contre-exemple 268091 invite à conserver cette prudence. La semaine
du 14 avril, l’apport minimal de 186 447 unités dépasse la taille maximale
de lot de 142 485 unités, sans permettre de compter les départs. L’essai
268967 réutilise les traces natives déjà qualifiées. Aucune nouvelle
simulation n’a été nécessaire pour établir les bornes et tester le stock
de composants à programme d’achat constant.
[Manifeste](../../artifacts/testing/transferts_muret_268967_20261120/final_manifest.json)
