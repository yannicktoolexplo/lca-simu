# Estimation avec taux de service reel

Objectif: tester si l'ecart entre simulation et stock composants immobilise reel peut venir du fait que la simulation sert 100% de la demande, alors que les taux reels indiques sont:

- Cos / PF 268091: 93%
- Pharma / PF 268967: 80%

Regle testee:

```text
stock utile ajuste = stock utile estime a 100% * taux de service reel
stock immobilise ajuste = stock composants initial - stock utile ajuste
```

Interpretation: si le taux de service reel est plus bas, une part plus faible du stock composants est consideree utile pour satisfaire la demande effective; l'immobilise estime augmente donc.

## Photo 06/01

| PF | Famille | Variante | Taux service | Stock initial EUR | Stock utile avant EUR | Stock utile ajuste EUR | Immobilise avant EUR | Immobilise ajuste EUR | Immobilise reel EUR | Ecart avant EUR | Ecart ajuste EUR |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 268091 | Cos | brut | 93% | 726887 | 253514 | 235768 | 473373 | 491119 | 656922 | -183549 | -165803 |
| 268091 | Cos | net | 93% | 726887 | 183226 | 170400 | 543662 | 556487 | 656922 | -113260 | -100434 |
| 268967 | Pharma | brut | 80% | 422500 | 156865 | 125492 | 265636 | 297009 | 220644 | 44991 | 76364 |
| 268967 | Pharma | net | 80% | 422500 | 37233 | 29786 | 385267 | 392714 | 220644 | 164623 | 172069 |

## Comparaison hebdomadaire 2025

| PF | Famille | Variante | Taux service | Semaines | Reel moyen EUR | Sim avant EUR | Sim ajuste EUR | Biais avant EUR | Biais ajuste EUR | MAE avant EUR | MAE ajuste EUR |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 268091 | Cos | net | 93% | 52 | 930695 | 615781 | 648802 | -314914 | -281894 | 314914 | 281894 |
| 268091 | Cos | brut | 93% | 52 | 930695 | 605631 | 639362 | -325064 | -291333 | 325064 | 291333 |
| 268967 | Pharma | net | 80% | 52 | 259678 | 756450 | 789182 | 496771 | 529504 | 496771 | 529504 |
| 268967 | Pharma | brut | 80% | 52 | 259678 | 652887 | 706332 | 393208 | 446653 | 393208 | 446653 |

## Lecture

La correction par taux de service ameliore legerement Cos, mais elle n'explique pas l'ecart. Sur l'annee, le biais net passe de -315 kEUR a -282 kEUR.

Pour Pharma, la correction deteriore l'estimation: comme le taux de service reel est seulement 80%, le stock utile ajuste baisse et l'immobilise estime monte, alors que l'immobilise reel est deja beaucoup plus bas que la simulation. L'ecart Pharma ne vient donc pas principalement du fait que la simulation sert 100% de la demande.

Conclusion: le taux de service doit etre garde comme facteur de lecture, mais il ne suffit pas a expliquer la difference de stock immobilise. La cause principale reste probablement une regle de perimetre ou de valorisation du stock immobilise reel: stock reserve/utile, horizon industriel, statuts qualite/libre, ordres fermes ou exclusion de certains composants.
