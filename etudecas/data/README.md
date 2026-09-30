# Donnees du cas Etudecas

Ce dossier contient les donnees actives du cas.

- `source/` : fichiers metier source et graphe JSON de base.
- `geocoded/` : graphe geocode et rapports de geocodage.
- `reports/` : rapports d'enrichissement de donnees.
- `MANIFEST.json` : inventaire court des donnees canoniques et des anciens chemins remplaces.
- `profile_source_files.py` : controle leger des sources canoniques et generation
  de `reports/source_data_profile.json` / `.md`.

L'[analyse des deux classeurs Flow](reports/mrp_source_rules.md) recense les
sécurités, lots et délais, vérifie les projections MRP sur 52 semaines et les
rapproche des stocks hebdomadaires. L'objectif confirmé est de reproduire le
comportement réel de la supply chain. Pour 268967 (Permixon), la couverture
visée est d'un an sur l'ensemble Gaillac → Gien → dépôt, en équivalent produit
fini. Les quantités « Stock_physique » du MRP positionnées dans le futur sont
du stock déjà présent, disponible plus tard (qualité, etc.), selon confirmation
utilisateur ; elles ne sont pas de nouvelles réceptions. Ces confirmations
complètent les règles sources. Les contradictions entre anciens et nouveaux
paramètres restent à dater avant application ; aucune baisse de sécurité ni
nouvelle simulation à zéro jour n'est autorisée par cette analyse.

Les fichiers CSV `CA_Perdu_Réel.csv`, `Dispo_PF_Projeté.csv`,
`Stock_Composants_Immobilisé_*.csv` et `Stock_PF_Immobilisé.csv` sont traites
comme references metier de validation. Ils servent a comparer la simulation aux
indicateurs reels/projetes: disponibilite produit, CA perdu, stock immobilise et
cout de stockage. Ils ne modifient pas directement la simulation tant qu'une
etape d'integration explicite ne les transforme pas en parametres ou cibles.

Pour les stocks composants immobilises, le suffixe porte le perimetre produit:
`Cos` correspond aux composants du produit fini `268967`; `Pharma` correspond
aux composants du produit fini `268091`. Ces CSV portent aujourd'hui une valeur
de stock immobilise. Les prix composants existent dans le graphe enrichi,
principalement sur les liens fournisseur-usine (`sell_price`, `price_base`,
`quantity_unit`). La comparaison pertinente consiste donc a valoriser les stocks
simules avec ces prix, en documentant les cas multi-sources, les prix a zero et
les composants internes produits par une autre usine.

Les scripts doivent pointer vers ces dossiers plutot que vers les anciens
chemins `donnees/` ou `result_geocodage/`.

Le dossier historique `etudecas/donnees/` n'est plus une source canonique. S'il
reste visible localement, c'est uniquement parce qu'un fichier Excel peut encore
etre ouvert par un processus externe. Fermer Excel permet de le supprimer
localement sans perte, puisque `source/Extract_En_cours.xlsx` est la copie active.
