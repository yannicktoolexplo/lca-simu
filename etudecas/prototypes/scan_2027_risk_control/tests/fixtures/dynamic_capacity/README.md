# Entrées conservées pour les tests du couplage besoins/capacités

Ces deux CSV sont des copies exactes d'exports locaux existants, conservées pour
rendre les tests reproductibles sans les dossiers de campagnes externes.
`provenance.json` enregistre leurs origines, tailles et empreintes SHA-256.
`.gitattributes` préserve leurs octets, y compris les fins de ligne.

- `supplier_nominal_parameters.csv` : 33 lignes de paramètres fournisseurs.
- `prepared_physical_supplier_floors.csv` : deux planchers de capacité identifiés.

Ce sont des données de régression conservées, pas de nouveaux résultats de
simulation ni une validation de performances réelles. Leurs chemins d'origine
sont informatifs : les tests ne les ouvrent pas.

`tests/dynamic_capacity_fixture.py` vérifie les empreintes, copie ces fichiers
et le graphe ainsi que les profils versionnés dans un dossier temporaire.
Le vrai constructeur d'audit calcule ensuite les tables et les empreintes pour
ces chemins temporaires. Le validateur d'audit et celui du protocole sont exécutés.
Une évolution incompatible du graphe ou des profils doit donc faire échouer
la fixture ; elle ne réaccepte pas automatiquement de nouvelles preuves.

## Sens métier du contrôle

Le passage d'un besoin statique à un besoin calculé depuis le programme de
production et la nomenclature peut aussi modifier les capacités fournisseurs
calculées et les besoins d'approvisionnement amont. Dans ces données de
régression, l'audit retrouve 27 liaisons fournisseurs dans le périmètre modifié,
22 capacités directes modifiées et 21 capacités amont modifiées, sur 33 lignes.

La comparaison ne permet donc pas d'attribuer les effets au seul calcul MRP.
Les tests conservent le refus de cette attribution et ne lancent pas le moteur.
Le checkpoint V3 utilisé par les tests du runner reste une petite fixture dont
la validation profonde est substituée explicitement : ces tests ne certifient
pas les 634 fichiers d'une livraison V3 historique.
