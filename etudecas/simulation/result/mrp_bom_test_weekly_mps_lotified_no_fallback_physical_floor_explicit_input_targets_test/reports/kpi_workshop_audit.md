# Audit atelier KPI - carte supply

Objectif: rendre la carte lisible en atelier industriel sans ajouter de nouvelle logique modele avant validation metier.

## Questions metier par onglet

| Onglet | Question metier | Lecture attendue | Statut interface |
|---|---|---|---|
| Simulation | Que s'est-il passe dans le run nominal ? | Stocks, commandes, flux, receptions, MRP, service. | Ajoute dans la synthese metier du panneau. |
| Sensibilite | A partir de quel niveau un parametre fournisseur degrade-t-il la performance ? | Stress tests capacite, stock, delai, fiabilite, appro amont. | Ajoute dans la synthese et les hovers. |
| Risques fournisseurs | Quel fournisseur merite une action ou une surveillance ? | Menace estimee, criticite, sensibilite, incertitude, action recommandee. | Deja nettoye: synthese + raisons principales + methode repliee. |
| Incertitude | Peut-on faire confiance a cette lecture ? | Couverture donnees, variabilite, dispersion, limites. | Nettoye: synthese courte + drivers + methode repliee. |
| Dependances | Ou le reseau est-il fragile par construction ? | Dependances, concentration, alternatives, exposition reseau. | Question ajoutee dans la synthese metier. |
| Arbres KPI | Comment les KPI se degradent-ils ensemble dans le temps ? | Performance globale, contributions, ecarts aux cibles. | Question ajoutee dans le modal + glossaire KPI replie. |

## Parcours de demo court

1. Simulation: montrer que la baseline tourne bien.
   - Fill rate: 100%.
   - Backlog final: 0.
   - Montrer un fournisseur ou une usine: commandes, receptions, stock, carnet MRP.

2. Sensibilite: cliquer un fournisseur.
   - Question a poser: ce fournisseur casse d'abord sur quoi ?
   - Montrer la zone acceptable, le premier niveau degrade, et les KPI qui bougent.
   - Insister: c'est une grille de simulation, pas une vraie capacite fournisseur mesuree.

3. Risques fournisseurs: passer au meme fournisseur.
   - Montrer que le risque n'est pas juste la sensibilite.
   - Il combine menace estimee, criticite, signaux faibles, incertitude et action recommandee.
   - Insister: c'est un score de decision, pas une probabilite historique observee.

4. Incertitude: passer au meme fournisseur.
   - Message cle: on ne dit pas que le fournisseur est dangereux.
   - On dit si la lecture est fiable: delai, capacite, stock, fiabilite.

5. Conclusion atelier.
   - Quels KPI deviennent contractuels ou metier ?
   - Quels seuils sont realistes ?
   - Quelles donnees fournisseur manquent pour remplacer les hypotheses ?

## Glossaire KPI atelier

| KPI | Formule / logique | Sens de lecture | Question a valider |
|---|---|---|---|
| Fill rate | Quantite servie / besoin avec backlog. | Plus haut = mieux. Objectif courant: 100%. | Est-ce le KPI client principal ? |
| Disponibilite produit | Service produit dans le temps, proche du fill rate quand la demande est servie. | Plus haut = mieux. | Doit-elle etre distinguee du fill rate ? |
| Backlog | Demande non servie restante. | Plus bas = mieux. Objectif courant: 0. | Quel backlog acceptable, si aucun ? |
| Adherence ligne | Ecart entre plan lotifie et execution. | Plus haut = mieux. | Quel seuil industriel est acceptable ? |
| Cout stock | Cout ou estimation de cout d'immobilisation stock. | Plus bas = mieux, sous contrainte service. | Quel cout reel ou proxy financier utiliser ? |
| Signal MP usine zero | Jour calendaire ou au moins une MP suivie finit a stock usine nul. | Diagnostic technique uniquement: pas rupture client, pas rupture fournisseur, pas duree de rupture usine. | A garder en detail seulement, ou a remplacer par un indicateur metier plus robuste ? |
| Retard matiere | Arrivee effective - arrivee prevue. | Plus bas = mieux. | Quel retard est significatif en jours ? |
| Sensibilite fournisseur | Degradation observee dans une grille de stress tests. | Plus haut = plus fragile dans le modele. | Quels niveaux de stress tester ? |
| Risque fournisseur | Score de decision combinant menace, criticite, sensibilite, incertitude. | Plus haut = plus d'action. | Quels poids et seuils valider ? |
| Incertitude | Qualite et dispersion de la lecture. | Plus haut = moins de confiance. | Quelles donnees reduisent l'incertitude ? |

## Recommandations de vocabulaire

- Dire "estimation" plutot que "proxy" dans les libelles metier.
- Dire "signal principal" ou "point faible" plutot que "driver".
- Dire "premier niveau degrade" plutot que "refus".
- Dire "score de decision" pour le risque fournisseur.
- Dire "confiance de lecture" pour l'incertitude.
- Garder les noms de colonnes techniques uniquement dans les details repliees.

## Ce qui ne doit pas etre change avant atelier

- Pas de recalibrage des poids risque.
- Pas d'ajout Monte Carlo.
- Pas de nouvelle logique fournisseur.
- Pas de nouveaux scenarios sans validation des seuils metier.
