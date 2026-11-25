| Sujet | Pièce consultée | Acquis | Complément utile réalisé | Format |
| --- | --- | --- | --- | --- |
| 01 Cinq dossiers fournisseurs | Cahier lignes 7–11 ; cas et CSV fournisseurs | 25,21 % de listes sans cas au hasard ; 9,09 % en 4+1 | Veille achats, recomptage des plans, distinction entre détecter un cas et couvrir tous les cas | [Note](theme-01-revues.md) et [Excel](Calculs-revues-et-alertes.xlsx) |
| 02 Quantité de dépannage | Cahier lignes 13–17 | 46/60 configurations sans rupture ; besoin 800→900 kg avec libération partielle | Veille MOQ et qualité ; exemple simple où le multiple de commande absorbe l'écart | [Amorce achats](themes-02-04.md#02-quelle-quantité-acheter-à-la-source-de-dépannage) |
| 03 Information décisive pour un audit | Cahier lignes 19–23 | 16 cotations sur 84 peuvent modifier trois visites | ISO 19011:2026, justificatifs prioritaires ; petit exemple de deux incertitudes simultanées | [Amorce audits](themes-02-04.md) |
| 04 Jours de service du dépôt | Cahier lignes 27–31 | 4 jours au dépôt ; cinquième jour conditionnel au transfert | Veille promesse ERP ; solde daté montrant la différence entre quantité et continuité | [Amorce stock](themes-02-04.md) |
| 05 Reprise et service quotidien | Cahier lignes 33–37 | Meilleur volume total ne garantit pas le plancher quotidien | Lectures métier et recherche appliquée ; grille journal/jour et calculs partiels permis | [Amorce planification](themes-05-08.md) |
| 06 Commande à servir d'abord | Cahier lignes 39–43 | Urgence : retard maximal 7→4 jours ; retard pondéré 28→32 unités-jours | Clarification du contrat, calcul des écarts et de leur arbitrage | [Amorce allocation](themes-05-08.md) |
| 07 Départs et fermeture de quai | Cahier lignes 47–51 | 80 unités dépassent un chargement de 60 ; 0/21 regroupements faisables | Vérification de capacité, distinction rotations/véhicules ; variantes laissées à départager sur horaires | [Amorce transport](themes-05-08.md) |
| 08 Justificatifs transport | Cahier lignes 53–57 | À trois demandes : 47,6 % contre 42,0 % des tonnes-kilomètres | GLEC 3.3, sensibilité simple au rendement de collecte et format de demande | [Amorce collecte](themes-05-08.md) |
| 09 Relance du transitaire | Cahier lignes 59–63 ; cas et CSV fret | 4,14 est le seuil de deux règles seulement | Recalcul des cinq règles, charge de revue, coûts modifiables et lectures sur les expéditions | [Note](theme-09-alertes.md) et [Excel](Calculs-revues-et-alertes.xlsx) |
| 10 Jeu complet pour le montage | Cahier lignes 67–71 | 163 bilans composants ; stock physique et jeux livrables divergent | Veille libération/traçabilité ; exemple à trois références, 6 jeux utilisables contre 10 physiques | [Amorce montage](themes-10-12.md) |
| 11 Retouche et recontrôle | Cahier lignes 73–77 | Seuil public 3/6 acceptations ou 4/6 avec trajet dédié | Périmètre carbone, étude réparation 2026 ; exemple nouveau distinct et questions terrain | [Amorce retouche](themes-10-12.md) |
| 12 Pondération en conception | Cahier lignes 79–83 | 8 impacts améliorés, 8 dégradés ; inversion à 7,294 % | Veille EF, vérification d'une plage traversant le seuil ; inventaire demandé avant nouveau classement | [Amorce conception](themes-10-12.md) |
| 13 Plafond des urgences | Cahier lignes 87–91 | Risque comparé 15,0→40,4 % selon regroupement | Lecture des clauses et coûts ; exemple simple : plafond valant 5,47 ou 50 €/lot selon regroupement | [Amorce contrôle de gestion](themes-13-14.md) |
| 14 Accélérer ou combiner | Cahier lignes 93–97 | Accélérer seul suffit dans un incident ; seuil 2,49 dans un autre | Coûts différentiels ; exemple nouveau de seuil et maintien de l'option simple à efficacité égale | [Amorce décision](themes-13-14.md) |

# Compléments pour les quatorze cahiers métier

**Date : 25 novembre 2026.** Origine : lecture de `ICs/` sur `partage/cahiers-ic-anonymes`, commit de départ `REV-0415`, veille primaire et calculs complémentaires de ce jour. Le tableau renvoie aux lignes du [cahier de référence](../Cahiers-metier.md). Les deux cas et leurs CSV ont été ouverts. Aucun document source n'est remplacé.

Ces amorces sont destinées aux ingénieurs, gestionnaires de projet et contrôleurs de gestion accompagnés par la supervision. La progression est : recherches internet sur les pratiques et standards, méthodes nouvelles, puis bibliographie scientifique avec résultats utiles. Un tableau de quelques lignes ou des questions d'entretien peuvent suffire. Aucun travail de recherche avancé ni aucune durée historique ne sont attribués à une personne.

## Utiliser les livrables

- [Amorces-14-themes.docx](Amorces-14-themes.docx) : synthèse de supervision, fiches courtes et suite accessible pour chaque thème.
- [Calculs-revues-et-alertes.xlsx](Calculs-revues-et-alertes.xlsx) : formules fournisseurs et fret. Dans « Coûts des alertes », renseigner B5 (coût d'un mois manqué rapporté à une fausse alerte) et E5 (coût d'une revue justifiée rapporté à une fausse alerte). Les valeurs initiales sont illustratives.
- [Cadrage-et-gabarit.md](Cadrage-et-gabarit.md) : progression réaliste et repère Frascati. Une veille prépare un éventuel projet ; elle ne suffit pas à qualifier une activité de R&D.
- Les notes thématiques du tableau : acquis localisés, lectures datées et ouvertes, effet sur la décision, calcul et données à demander. [Bibliographie complémentaire du fret](bibliographie-recherche.md).

## Ce qui a été vérifié et ce qui reste à demander

Les probabilités des plans de tirage fournisseurs et les indicateurs des alertes fret sont recalculés à partir des CSV publics. Les listes nominatives des règles fixes ne sont pas reconstructibles : leur cohérence comptable seule est vérifiée. Pour les autres thèmes, les résultats du cahier restent des résultats documentés. Les exemples nouveaux sont explicitement pédagogiques ; aucun essai sur des expéditions, commandes ou inventaires industriels individuels n'est annoncé.

Les notes demandent les vues utiles : lignes article–site–jour pour le stock, ordre–référence–lot pour les jeux complets, commande–lot pour l'allocation, tournée–créneau pour les quais, expédition–tronçon pour les justificatifs, lot parent–sous-lot pour les plafonds, et vecteurs d'impacts avec facteurs/version pour la conception. Les champs et périmètres précis sont indiqués dans chaque fiche.

Deux enseignements méritent l'attention de la supervision. Le plan 4+1 maximise la détection parmi les quotas testés conservant les deux groupes, mais ne couvre en moyenne que 1,61 des six cas. Pour le fret, comparer les cinq règles conduit à des bascules à 1,02941 et 3,98347 ; 4,14 concerne une comparaison deux à deux. Avec l'option ajoutée « toujours alerter » et une revue justifiée gratuite, une nouvelle bascule apparaît à 3,96350 : il faut donc mesurer la charge de revue. Aucun de ces calculs ne prouve qu'une relance empêche la dégradation du service.

## Reproduire les vérifications

Depuis la racine du dépôt, Python 3 et sa bibliothèque standard suffisent pour les calculs publics et les exemples achats/stock :

```bash
python3 ICs/Complements-2026-11-25/verifier-cas.py
python3 ICs/Complements-2026-11-25/calculs-02-04.py
```

[verification-cas.json](verification-cas.json) conserve les recomptages, les bornes exactes des comparaisons de coût et les empreintes SHA-256 des deux CSV. Les JSON par groupe conservent entrées, résultats et registre des sources. [build-workbook.mjs](build-workbook.mjs) et [build-note.py](build-note.py) conservent les scripts de création ; le premier nécessite la bibliothèque `@oai/artifact-tool`, le second `python-docx`.

Le classeur a été recalculé, soumis à 128 contrôles et rendu pour vérification des cinq onglets ; aucune erreur de formule n'a été trouvée. Les coûts ont été modifiés pour vérifier les choix et les ex æquo. L'ouverture dans Excel desktop n'a pas été effectuée. La note Word a été rendue et contrôlée visuellement avant livraison.
