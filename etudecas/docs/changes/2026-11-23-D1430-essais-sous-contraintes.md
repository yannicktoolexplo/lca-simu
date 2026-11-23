# D1430 2025 · retrouver les semaines de fabrication sous contraintes

Le gel du programme et la priorité des ordres déjà engagés ne suffisent pas à faire travailler D1430 en avril. Les tests isolent deux causes supplémentaires. Le modèle confond la sortie de matières pour préparer un lot et leur utilisation lors du conditionnement. Il reçoit aussi trop tard un approvisionnement d’aluminium. Ces deux mécanismes ont été étudiés avec les quantités de lots, les délais et les sécurités d’origine.

| Essai sur le 268967 | Résultat |
| --- | --- |
| Maintenir les seules propositions simulées qui entrent dans le gel de 56 jours | Premier lancement admissible le 7 mai dans le calcul à plans archivés. L’erreur passe de 100 % à 112,55 % sur les semaines documentées du creux d’avril à juin. |
| Réserver les composants aux lots engagés, dans le moteur avec gel et capacité finie | Les deux exécutions commencent le 12 mai. Même erreur de travail de 223,33 % sur 14 semaines documentées, même service à D1920 et 690 475 unités livrées à la clôture. |
| Anticiper la décision sur le même achat d’aluminium 730384 | Erreur du stock physique de 41,11 % à 13,84 % sur les 18 photos du 13 janvier au 12 mai. Le délai de livraison de 56 jours et les 5 jours ouvrés de contrôle sont conservés. |

[Oracle du gel](../../artifacts/testing/D1430_contraintes_20261123/validator/preuve_gel.json) · [Comparaison des exports moteur](../../artifacts/testing/D1430_contraintes_20261123/native/historical/comparison.json) · [Rapprochement de l’aluminium](../../artifacts/testing/D1430_contraintes_20261123/diagnostic/preuve_appro_alu.json) · [Contrôle indépendant](../../artifacts/testing/D1430_contraintes_20261123/validator/preuve_alu_oracle.json)

## Avril · matières prélevées avant les étuis

La semaine du 7 avril, les trois prélèvements de 038005, 042342 et 773474 permettent chacun de couvrir la recette de 107 800 unités. Cette semaine, le relevé des étuis indique zéro. Le 21 avril, les prélèvements de **94 000 étuis** concordent avec deux autres emballages. Le MRP d’avril montre par ailleurs **30 millions d’unités de 042342 encore à disponibilité future**, et seulement **2,125 millions** dans le stock courant. La distinction entre préparation et conditionnement permet d’expliquer cette coexistence. Les identifiants d’ordres industriels manquent pour établir l’identité du lot et la durée entre les étapes.

Dans le nominal, le 13 avril, les trois prélèvements sont affectés aux usages Scan3 non attribués. Le 15 avril, un lot simulé repasse presque les mêmes quantités dans la recette. Le calcul local teste le rattachement au même lot. Il conserve le débit du 13, les vrais autres usages et les surplus résiduels. Il maintient l’intégralité des 30 millions sous contrôle. Ce rapprochement fait apparaître un kit physique le **23 avril**. Avec le stock de sécurité de **23 500 m** d’aluminium, il manque encore **21 725,2 m** pour un second lot entier. [Mouvements et quantités conservées](../../artifacts/testing/D1430_contraintes_20261123/diagnostic/preuve_attribution_trois.json) · [Contre-calcul indépendant](../../artifacts/testing/D1430_contraintes_20261123/validator/preuve_attribution.json)

## Réception d’aluminium et calendrier autorisé

La version MRP du 12 janvier prévoit déjà **87 000 m** en mars. Les mouvements et les relevés attestent une réception de **102 500 m** au plus tard le 10 mars. Le lot simulé de **92 500 m** est commandé le 6 mars et devient utilisable le 8 mai. L’essai garde le volume exact de cet achat et simule ce même engagement au 13 janvier. La date utilisable devient le 17 mars. Ce calendrier est une hypothèse conditionnée par le plan connu en janvier. Le fichier partiel des ordres ne permet pas de rapprocher l’identité du lot acheté.

La combinaison de l’achat anticipé et du rattachement en encours permet de reconstituer le kit du **23 avril tout en gardant la sécurité de chaque composant**. Le calendrier et la capacité restent ceux du nominal évalué. Les deux changements ne rendent disponible aucun ordre en avril dans le carnet simulé. Même avec une répartition libre du travail du seul lot exécuté dans le nominal, le meilleur écart possible sur les trois semaines du 14 avril au 4 mai reste **40,58 %**, car les **181 420 étuis** observés dépassent ce lot de **73 620 unités**. Cette borne utilise les observations après coup.

Le MRP industriel prévoyait une consommation cohérente de trois emballages pour la semaine du 21 avril dès le 16 février. Si l’information est connue le 17, elle arrive 63 jours avant le conditionnement, mais seulement 49 jours avant les prélèvements du 7 avril. Avec un gel ancré au premier travail, il aurait fallu un ordre confirmé ou une préparation habilitée au plus tard le 10 février. À cette date la même intention pour le 21 avril n’est pas documentée. Un calendrier d’atelier peut donc départager un ordre lancé plus tôt, une préparation autorisée séparément ou deux lots distincts.

## Vérification et portée

Les essais moteur conservent le gel à quatre semaines à D1810 et huit à D1430, le plafond de 154 000 unités par jour à D1430, les lots de 107 800, les délais de contrôle et les stocks de sécurité. Les deux séries physiques couvrent 173 jours. Le témoin dépasse sa limite de calcul après les exports physiques et avant les preuves finales. Le candidat à priorité matière se termine et sa qualification passe **345 contrôles**. Leur comparaison est limitée aux exports physiques vérifiés. Le contrôle documentaire signale les registres déjà désynchronisés. Les rapprochements d’avril et de l’aluminium sont des calculs locaux de stock, sans nouveau lancement de PF ni recalcul du service client.

La prochaine preuve décisive est une liaison par identifiant entre le programme ferme de D1430, les prélèvements des trois matières et le conditionnement du lot. Les phases pourront alors être comptées séparément dans le modèle, avec les contraintes de chacune et sans prélever deux fois la même matière.

[Manifeste de l’étude](../../artifacts/testing/D1430_contraintes_20261123/final_manifest.json) · [Qualification du candidat](../../artifacts/testing/D1430_contraintes_20261123/native/qualification/qualify-42f9dc1967b14f808160578aa52038a3/manifest.json)
