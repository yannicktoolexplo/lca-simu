# Contre-vérification numérique de la carte corrigée

Le contrôle indépendant de la carte nominale `audited_corrections_20260920`, avec le scénario associé `state_dependent_full`, ne détecte aucun écart dans les valeurs rapprochées : **8 627 contrôles, 2 176 246 valeurs recalculées, zéro échec**. L'horizon exécuté comporte 1 825 jours. Le graphe de référence est celui désigné par `run_manifest.json`, et non le graphe source brut.

Les scripts de preuve n'importent aucun producteur de carte ni fonction de calcul du moteur. Ils relisent les CSV du scénario, le graphe manifesté et les paramètres descriptifs publiés, puis recomposent les séries. Cela vérifie la cohérence des affichages avec ces sources ; cela ne valide pas la calibration industrielle de toutes les hypothèses.

## Inventaire et couverture

L'inventaire contient **567 figures de contenu distinct**, ainsi que **1 370 séries temporelles représentant 2 040 037 points embarqués**. Les 1 370 séries ont un rapprochement numérique ; aucune ne reste limitée à un contrôle de structure. Les 567 figures ont un rapprochement de leurs données numériques principales, y compris barres, radars, histogrammes et données du Gantt. Les coordonnées d'habillage, positions de légendes, tailles de marqueurs et textes libres ne constituent pas des résultats numériques certifiés par cette preuve.

| Famille | Figures inventoriées | Séries temporelles | Points temporels |
| --- | ---: | ---: | ---: |
| Usines, graphiques | 55 | 188 | 343 089 |
| Usines, données de suivi | — | 28 | 51 100 |
| Fournisseurs | 54 | 132 | 481 800 |
| Dépôts | 3 | 8 | 14 395 |
| Modèle, nœuds et flux | 353 | 926 | 963 514 |
| Risques simulés | 4 | 16 | 40 150 |
| Comparaison de scénarios | 8 | 10 | 32 850 |
| Clients | 3 | 7 | 12 764 |
| Arbre KPI et scores descriptifs | — | 55 | 100 375 |
| Radars fournisseurs | 87 | — | — |

Les radars et barres ne sont pas inclus dans le dénominateur des séries temporelles. Les contrôles supplémentaires portent notamment sur les bilans annuels, les valeurs des radars, le calendrier et les qualifications métier ; ils expliquent le nombre de valeurs recalculées supérieur au nombre de points temporels.

Chaque chemin de figure et de série, son empreinte, sa source de rapprochement et son statut figurent dans [figure_inventory.json](../../artifacts/testing/audit_corrections_20260920/payload/final-map/figure_inventory.json) et [series_inventory.json](../../artifacts/testing/audit_corrections_20260920/payload/final-map/series_inventory.json). Le détail des assertions est dans [reconciliation.json](../../artifacts/testing/audit_corrections_20260920/payload/final-map/reconciliation.json).

## Contrats métier effectivement contrôlés

- **Matières** : les 24 lignes d'intrants sont rapprochées sur cinq années, avec stock d'ouverture, réceptions datées, consommations physiques, autres sorties, ajustements et clôture indépendante. Les 120 bilans annuels sont rapprochés. Les PF/PFI sont explicitement hors bilan d'intrants.
- **Exécution transport** : réservations et arrivées futures sont exclues des courbes physiques. Les statistiques de délai sont calculées seulement sur les réceptions observées. Une contre-sonde séparée a rapproché les 10 711 lignes d'expédition nominales : 10 366 reçues, 176 en transit, 169 réservées avant départ.
- **MRP et unités** : les besoins prévisionnels, stocks et ordres sont rapprochés par unité. Les réceptions prévues suivent le contrat réel des dates d'ordre. La conversion des jours source de sécurité suit une énumération indépendante du calendrier lundi–vendredi.
- **Production** : la concordance avec le besoin et l'adhérence au plan lotifié sont recalculées séparément ; les blocages intrants proviennent des contraintes physiques effectives. Un stock nul sur une référence inactive n'est pas une preuve de blocage.
- **Coûts** : opérationnel, approvisionnement externe et exposition économique restent séparés. Les deux scénarios sont partiellement valorisés ; aucun classement économique ni composante monétaire du score ne leur est accordé. Le panneau Données qualifie aussi les prix historiques rejetés, sans modifier le JSON source brut.
- **Risques** : séries d'exposition, service et événements rapprochées ; les rapprochements aval restent des associations. Aucune perte client n'est attribuée par simple proximité temporelle ou connexion réseau.

Exemples du nouveau nominal : `042342` consomme **435 826 157 UN** dans le registre, contre **435 826 129,2** dans le calcul théorique ; `338929` consomme **16 070 400 UN** et reçoit **17 537 600 UN**. Ces valeurs sont propres au nouveau scénario et ne remplacent pas les preuves historiques.

## Tolérances, provenance et limites

Le contrôle des points utilise une tolérance absolue habituelle de `2e-5` et relative de `1e-10` pour la sérialisation numérique. Les coûts journaliers tolèrent `2e-4`, et certains agrégats de résumés arrondis `0,1`. Les bilans physiques annuels utilisent le seuil explicite de `1e-5` unité ; leur somme sur cinq années peut accumuler un écart numérique de quelques cent-millièmes sans cacher un écart d'une unité. Le fichier de rapprochement donne le fondement de chaque contrôle.

Le SHA-256 de l'HTML au moment du calcul est `8092cb476b72e6ade38f752e6481cacd339a25f3abbcd78b66850b81843d8397`. [numeric_summary.json](../../artifacts/testing/audit_corrections_20260920/payload/final-map/numeric_summary.json) conserve les empreintes des sources et scripts. Le rafraîchissement du panneau Données est tracé dans [data-panel-refresh.json](../../artifacts/testing/audit_corrections_20260920/payload/data-panel-refresh.json) : tous les autres chunks compressés et tous les octets hors panneau sont conservés.

Après ajout du lien de navigation, l'HTML final a le SHA-256 `51a019257f42ae3909ee17d87a3943d3a0b87f6da0f65e41325cf9d5a210a10f`. La [liaison finale indépendante](../../artifacts/testing/audit_corrections_20260920/payload/final-map/final_html_binding.json) vérifie que ses **47 chunks DATA sont identiques** à ceux de l'HTML audité, au niveau des octets gzip et des listes encodées. Les mêmes valeurs numériques sont donc couvertes. Cette liaison ne se substitue pas au test navigateur du lien ajouté.

La preuve couvre les valeurs publiées des courbes inventoriées, pas toutes les phrases de chaque panneau ni une observation réelle d'usine. Les radars estimés sont rapprochés de leurs critères et regroupements publiés, sans transformer leurs coefficients en mesures industrielles. Les poids des scores, les durées indicatives du Gantt, les prix inconnus et la causalité d'incidents restent qualifiés comme tels. Les tests de navigation et les deux suivis de lots relèvent des preuves navigateur et traçabilité distinctes.
