# Point de reprise MRP — 30 septembre 2026

Ce dossier conserve la **reconstitution analytique MRP** validée : quatre articles à Avène, 52 versions de plan chacun, huit règles candidates au total. Il ne remplace pas le moteur de simulation physique et ne prétend pas identifier complètement les règles de l'industriel.

Il contient quatre fichiers : cette notice, la commande de reproduction, le manifeste et une archive compressée d'environ 3 Mo. L'archive conserve les scripts exacts, les quatre Excel nécessaires, deux catalogues de données précédents, les résultats chiffrés et les rapports de vérification. Les fichiers restent dans leur arborescence d'origine à l'intérieur de l'archive ; aucune modification des sources industrielles n'est nécessaire.

## Reproduire depuis ce commit

Depuis la racine du dépôt, avec Python 3.11 et `openpyxl` :

```powershell
python -B etudecas/config/mrp_reconstruction_20260930/reproduce.py
```

Cette commande crée un nouveau dossier sous `etudecas/artifacts/testing`, recalcule tous les plans depuis les Excel figés, compare tous les résultats à la référence, exécute l'oracle indépendant et génère `comparaison_mrp.html`. Elle affiche les chemins produits. Aucun fichier existant n'est écrasé. La comparaison autonome est entièrement reproductible avec les éléments de ce dossier.

Pour reconstruire également **la carte complète**, avec tous les onglets historiques :

```powershell
python -B etudecas/config/mrp_reconstruction_20260930/reproduce.py --with-map
```

Cette option exige les deux grandes cartes de référence conservées **localement** :

- `etudecas/resultats/regroupement_001757_20260929/carte.html`
- `etudecas/resultats/mrp_source_driven_20260928/carte_corrigee.html`

Leurs empreintes doivent correspondre au manifeste. Elles ne sont pas incluses dans Git : leur compression reste supérieure à 70 Mo. La commande reconstruit la carte dans le nouveau dossier et exige une identité exacte avec le HTML livré. Un clone dépourvu de ces deux références peut reconstruire la comparaison autonome, mais pas tous les onglets de la carte historique.

La carte de travail conservée sur ce poste est `etudecas/resultats/regroupement_001757_20260929/carte_reconstitution_mrp.html`. Son bouton « Reconstitution MRP » ouvre le panneau ajouté ; les anciens onglets restent ceux de la carte de regroupement.

## Résultats et limites à conserver pour la suite

- 001757 : couverture de sept semaines et arrondi à 1 000 kg plus proches des propositions que quatre ou six semaines ; standard FIA de 100 kg inchangé dans le moteur.
- 002612 : couverture de six semaines et standard de 22 500 kg reproduisent les sept réceptions positives comparables du premier semestre ; d'autres propositions correspondent à 23 750 kg.
- 338929 : couverture de trois semaines utile, avec des décalages résiduels de dates.
- 001848 : le standard principal de 6 000 kg ne suffit pas à reproduire les propositions terminales et celles de 4 000 kg.

Les entrées initiales sont reprises comme engagements **supposés** et exclues des scores. Les semaines absentes de l'export sont signalées et leurs besoins/disponibilités sont supposés nuls. Les projections restent distinctes des mouvements réalisés et du stock physique. Ni les sécurités sources ni le nominal ne sont modifiés par cette étude.

Les preuves historiques archivées documentent le recalcul indépendant et les contrôles navigateur déjà exécutés. Les manifestes natifs portent sur le dépôt de l'époque et sur des captures locales non toutes embarquées ; ils ne constituent pas une nouvelle qualification d'un clone. La commande ci-dessus effectue une nouvelle vérification numérique, sans relancer de navigateur ni de simulation physique.

Les autres modifications locales du dépôt (simplification, campagnes, moteur, POC2026) sont hors de ce point de reprise. Les prochaines investigations portent sur le maintien/révision des engagements, le choix fournisseur et le calendrier de réception, sans réglage différent par morceau de courbe.
