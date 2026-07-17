# Audit donnees source 268091

- Stock composant immobilise reel moyen: 930,695 EUR.
- Cout BOM valorise: 0.471 EUR/unite PF.
- Valeur des ordres ouverts initiaux composants 268091: 491,674 EUR.
- Valeur avec fournisseur en-cours absent de la FIA: 290,070 EUR (12 lignes).
- CA potentiel reel 268091: 22,605,420 EUR ; service CA: 92.9%.

## Principaux ordres ouverts

| Source row | Item | Fournisseur | Quantite | UOM | Valeur EUR | Fournisseurs FIA |
|---:|---|---|---:|---|---:|---|
| 14 | item:002612 | SDC-VD0910216A | 22,500.0 | KG | 28,350 | SDC-VD0500655A,SDC-VD0910216A,SDC-VD0990780A,SDC-VD1091642A |
| 15 | item:002612 | SDC-VD0910216A | 22,500.0 | KG | 28,350 | SDC-VD0500655A,SDC-VD0910216A,SDC-VD0990780A,SDC-VD1091642A |
| 58 | item:049371 | SDC-VD0518550B | 1,800,000.0 | G | 26,370 | SDC-VD0520132A |
| 59 | item:049371 | SDC-VD0518550B | 1,800,000.0 | G | 26,370 | SDC-VD0520132A |
| 60 | item:049371 | SDC-VD0518550B | 1,800,000.0 | G | 26,370 | SDC-VD0520132A |
| 61 | item:049371 | SDC-VD0518550B | 1,800,000.0 | G | 26,370 | SDC-VD0520132A |
| 62 | item:049371 | SDC-VD0518550B | 1,800,000.0 | G | 26,370 | SDC-VD0520132A |
| 63 | item:049371 | SDC-VD0518550B | 1,800,000.0 | G | 26,370 | SDC-VD0520132A |

## Fournisseurs en-cours absents de la FIA

| Source row | Item | Fournisseur en-cours | Quantite | UOM | Valeur EUR | Fournisseurs FIA |
|---:|---|---|---:|---|---:|---|
| 58 | item:049371 | SDC-VD0518550B | 1,800,000.0 | G | 26,370 | SDC-VD0520132A |
| 59 | item:049371 | SDC-VD0518550B | 1,800,000.0 | G | 26,370 | SDC-VD0520132A |
| 60 | item:049371 | SDC-VD0518550B | 1,800,000.0 | G | 26,370 | SDC-VD0520132A |
| 61 | item:049371 | SDC-VD0518550B | 1,800,000.0 | G | 26,370 | SDC-VD0520132A |
| 62 | item:049371 | SDC-VD0518550B | 1,800,000.0 | G | 26,370 | SDC-VD0520132A |
| 63 | item:049371 | SDC-VD0518550B | 1,800,000.0 | G | 26,370 | SDC-VD0520132A |
| 64 | item:049371 | SDC-VD0518550B | 1,800,000.0 | G | 26,370 | SDC-VD0520132A |
| 65 | item:049371 | SDC-VD0518550B | 1,800,000.0 | G | 26,370 | SDC-VD0520132A |

## Lecture

- Le probleme le plus probable est un ecart entre la FIA et le carnet d'ordres initial, surtout sur `item:049371`.
- Si les ordres ouverts `049371` appartiennent bien a `VD0518550B`, il manque une voie FIA pour ce fournisseur; si ce fournisseur est obsolete, ces ordres ne doivent peut-etre pas etre injectes tels quels.
- Le KPI reel est agrege: il ne permet pas de verifier composant par composant quelle partie du stock est incluse dans `stock immobilise Cos`.