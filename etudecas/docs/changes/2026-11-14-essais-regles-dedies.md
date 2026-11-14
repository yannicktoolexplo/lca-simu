# Essais dédiés aux règles MRP — 14 novembre 2026

Référence testée : `REV-0366`, bundle `mrp_reference_20261013`. Moteur, paramètres nominaux et données industrielles conservés. Ce travail éprouve les 12 règles encore seulement relues dans la [suite précédente](2026-11-14-tests-regles-mrp.md), sans relancer l’année industrielle.

[Rapport interactif local](../../resultats/essais_regles_dedies_20261114.html) · [Manifeste final](../../artifacts/testing/essais_regles_dedies_20261114/final_manifest.json) · [Couverture et limites](../../artifacts/testing/essais_regles_dedies_20261114/coverage.json)

## Résultats décisifs

- Les autres usages s’ajoutent une seule fois aux besoins ; les stocks bloqués restent indisponibles. Le surplus d’un lot d’achat couvre correctement les besoins suivants.
- **Défaut de provenance reproduit** : 10 kg observés + 75 kg reconstruits reçoivent l’étiquette quotidienne « observé ». Les allocations détaillées restent correctement distinguées ; les quantités sont conservées.
- **Règle absente pour 338929** : la promesse agrégée ne déduit pas le stock fournisseur. Passer simplement à 14 jours ne représente pas une voie courte conditionnée au stock prêt.
- **Le lissage agit sur le signal, sans effet physique dans ce cas**. À la date du 11 janvier, 7 → 1 jour change le signal 22,857 → 5 et la commande corrigée 26,965 → 10. Les fichiers de fabrication, achats et service restent identiques.
- **La marge de planification agit sur les lancements** : 1 → 5 jours donne 100 unités finies supplémentaires, sans livraison supplémentaire. Chaque lot achevé de 100 nécessite quatre jours à 25 unités/jour ; cette marge n’est pas une durée physique.

## Comparaison courte

| Essai synthétique de 28 jours | Produits finis achevés | Production en cours | Livré aux clients | Demandé | En transit à la clôture |
|---|---|---|---|---|---|
| Témoin | 300 | 50 | 270 | 290 | 20 |
| Lissage 7 → 1 jour | 300 | 50 | 270 | 290 | 20 |
| Marge de planification 1 → 5 jours | 400 | 0 | 270 | 290 | 20 |

Quantités en unités physiques. Les 50 unités en cours ne sont pas comptées comme produits finis achevés. Les 20 unités en transit sont deux départs dépôt→client de 10 aux jours26/27, avec arrivée28/29, après la clôture : elles expliquent les20 en retard final. Le stock disponible au dépôt passe de30 à130 avec la marge5, sans raccourcir ces transports. Le mini-réseau a une nomenclature simple et des sécurités nulles explicitement synthétiques : aucun gain sur les courbes industrielles n’en est déduit.

## Essai et portée de chaque règle

### A09 — Besoin de D1920 sans lot usine

**Exécution synthétique.** Le dépôt porte des besoins et propositions de 5 ou 30 unités ; la fabrication reste lotifiée à 100 unités.

Limite : Séparation des niveaux exercée dans le mini-réseau. Cela ne valide pas les paramètres du dépôt industriel.

### A10 — Correcteur et lissage du programme

**Calcul et consommateur natifs.** Cas mémoire : commande brute 35 ; lissage 0,20 → commande 30 ; lissage 0,95 → 11,25. Dans les deux cas, le lotificateur produit un signal de 25 unités.

Limite : Consommateur réellement observé dans les trois simulations. Pas de simulation complète supplémentaire avec le coefficient 0,95 ; gains industriels non validés.

### ACH03 — Autres usages sur le même stock

**Calcul et registre natifs.** 10 produits finis × 2 composants + 5 unités pour les autres usages = 25 ; puis 25 × 3 = 75 unités de matière. Le cas physique ne consomme que les 3 unités disponibles, conserve les 10 bloquées et reporte 4 unités.

Limite : Aucun produit fini inventé par une consommation externe. La répartition réelle entre références reste une donnée à identifier.

### ACH05 — Lissage des besoins sur sept jours

**Exécution synthétique.** Le 11 janvier, passer de 7 à 1 jour change le signal du programme de 22,857 à 5 unités/jour et sa commande corrigée de 26,965 à 10. Les fichiers de fabrication, achats et service restent identiques.

Limite : Le paramètre est actif dans le signal préparatoire ; les lots et la décision datée absorbent ici son effet physique. Le signal matière du programme cumule 675 unités, contre 350 de travail exécuté dans le témoin : ce signal n’est pas une consommation physique additionnelle. Aucun gain industriel démontré.

### ACH11 — Standards fournisseurs et multiples

**Calcul natif.** Besoin 305, multiple contraignant 300 : commande 600, surplus 295. Un second besoin de 295 ne crée aucune commande. Standard non contraignant : 305 ; avec un multiple physique distinct de 20 : 320.

Limite : Le standard source ne doit pas devenir automatiquement un minimum. Les quantités en unités restent entières.

### ACH17 — Complément du carnet initial

**Résolution native du contrat.** 150 entrées prévues − 50 déjà représentées = complément 100. Connu le 5 janvier, reçu le 16, disponible le 24 après six jours ouvrés. Les incohérences documentaires sélectionnées sont refusées.

Limite : Promesse documentaire candidate, pas preuve de commande ferme industrielle. Le nouveau cas ne simule pas sa réception effective.

### P01 — Produit fini de l’usine au dépôt

**Exécution synthétique avec lots.** Un lot de 100 unités est achevé et expédié le 5 janvier, puis reçu au dépôt le 7 janvier. Le suivi des lots et la consommation de composants sont conservés.

Limite : Transport synthétique de deux jours. Le contrôle qualité au dépôt est exclu de cette version du mini-cas, après un défaut de résumé reproduit.

### P03 — Libération des semi-finis à D1450

**Calendrier et registre natifs.** Un lot achevé le 3 janvier devient disponible le 12 février avec 28 jours ouvrés, ou le 19 février avec 33. Départ anticipé refusé ; une seule identité de lot après libération.

Limite : Durées configurées des références 693055 et 773474. Le calcul des dates est vérifié ; leur origine et leur réalisme industriel restent à confirmer.

### P07 — Marge de planification tau_process

**Exécution synthétique.** Passer la marge de 1 à 5 jours avance les lancements et porte les lots achevés de 300 à 400 unités. Les quantités livrées aux clients restent à 270. Chaque lot achevé de 100 nécessite toujours quatre jours de travail à 25 unités/jour.

Limite : Marge d’anticipation, pas durée physique. Le premier lancement est borné par le début du calcul ; aucune calibration industrielle déduite.

### P09 — Délai court du packaging 338929

**Mécanisme conditionnel absent.** La promesse fournisseur agrégée ne retire pas la quantité promise du stock physique fournisseur. Une constante de 14 jours ne reproduit pas le délai court tant que le stock fournisseur suffit.

Limite : Prochain oracle proposé : stock 100, demande 80 puis 80 → voie courte 80 puis 20, reste 60 à réapprovisionner. Cette ventilation est une spécification manuelle, pas un résultat simulé.

### P11 — Observé, reconstruit et estimé

**Défaut courant reproduit.** Le vrai adaptateur conserve au détail 10 kg observés et 75 kg reconstruits. Son étiquette quotidienne indique pourtant « observé » pour l’agrégat de 85 kg. Sans observation ce jour-là, 75 kg reconstruits reçoivent « estimé ».

Limite : Défaut de provenance agrégée, pas défaut de conservation des quantités. Reproduit en mémoire avec le wrapper courant et le registre natif ; non corrigé dans le moteur.

### P12 — Risques, coûts et service

**Trois sous-règles seulement.** Risque capacité : utilisation strictement supérieure à 75 % pendant cinq jours → événement le lendemain, sept jours à capacité × 0,97. Coût : 10 unités disponibles + 25 bloquées sont valorisées ; encours et transit absents du bloc éprouvé. Service : 100 % des unités rattrapées peut coexister avec seulement 50 % de jours sans retard.

Limite : Blocs risque et coût extraits sans réécriture, pas cascade complète. Le partage de coût est synthétique. Le ratio financier de l’exemple (83,33 %) n’est pas une mesure observée des livraisons.

## Contrôles réellement exécutés et limites

- 24 cas pytest exacts passés : 22 achats/usages/contrats, 2 complémentaires libération/service financier. Cas et fixtures relus ; aucune suite globale.
- 34 contrôles du parent, 60 contrôles libération/risques/coûts/service ; contre-revues indépendantes séparées. Les comptages de contrôles ne sont pas des nombres de règles industrielles validées.
- Trois exécutions natives de 28 jours terminées, sur quatre lancements ; audits de lots et rapprochements indépendants. Qualification finale et empreintes : voir le manifeste.
- Premier lancement arrêté au résumé après 28 jours : `KeyError: internal_component_policy`. Le contrôle qualité synthétique au dépôt a été retiré du témoin et des deux variantes. Ce défaut du moteur est reproduit, non corrigé ; ce contrôle aval n’est pas validé par ces trois exécutions.
- Erreurs d’oracle conservées : calendrier observé vide non autorisé, confusion initiale entre stock physique et utilisable, lignes informatives d’audit comptées comme erreurs. Elles ont été diagnostiquées avant correction des seules expériences.
- Le stock hors graphe de 107 800 unités injecté par le cas global reste constant, déclaré et exclu des bilans du mini-réseau. Les sorties natives sont conservées.
- P12 couvre trois sous-règles ; les blocs risque/coût sont extraits du code sans réécriture. Pas de cascade complète éprouvée, pas de validation des paramètres industriels, pas de comparaison à Mines Albi ni de nouvelle calibration 2025.
- Aucun navigateur, Node, Word, test d’altération de fichiers ou contrôle interdit par AGENTS.md. Les refus documentaires éventuels sont consignés, jamais comptés comme succès.

## Prochaine étape

Corriger séparément la provenance quotidienne et le résumé avec contrôle aval, puis rejouer les cas exacts. Pour 338929, représenter d’abord le stock fournisseur prêt et son épuisement : stock 100, demandes successives 80 et 80 donnent au maximum 80 puis 20 servis par cette voie, les 60 restants exigeant un réapprovisionnement. Cet exemple est un oracle proposé, pas une simulation exécutée. Clarifier si les 14 jours se terminent à la réception ou à la disponibilité.

Les horizons figés de 4/8 semaines, la consommation mensuelle et les transferts restent les priorités métier identifiées précédemment avant de reprendre le calendrier industriel de 268967. Aucune référence promue.
