# Supplier Risk Campaign

- Generated: 2026-06-01T17:37:20.718089+00:00
- Horizon: 365 days
- Suppliers tested: 29
- Families tested: capacity, stock, lead, reliability, quality, upstream, cost
- Cases: 203 stress cases + 1 baseline

## Top supplier decision scores

| Rank | Supplier | Worst risk | Decision score | Main observed KPI | Observed reading |
|---:|---|---|---:|---|---|
| 1 | SDC-VD1096202A | Stock fournisseur | 8.0% | Flux fournisseur expedies | disponibilite -0.1 pts ; adherence -5.0 pts ; jours stock MP zero +1 ; flux expedies -33005701 |
| 2 | SDC-VD0914320A | Stock fournisseur | 7.5% | Flux fournisseur expedies | adherence -5.0 pts ; jours stock MP zero +1 ; flux expedies -33102451 |
| 3 | SDC-VD0951020A | Stock fournisseur | 7.5% | Flux fournisseur expedies | adherence -5.0 pts ; jours stock MP zero +1 ; flux expedies -33102451 |
| 4 | SDC-VD0964290A | Stock fournisseur | 7.5% | Flux fournisseur expedies | adherence -5.0 pts ; jours stock MP zero +1 ; flux expedies -33102451 |
| 5 | SDC-VD0505677A | Stock fournisseur | 7.5% | Flux fournisseur expedies | adherence -5.0 pts ; jours stock MP zero +1 ; flux expedies -33082974 |
| 6 | SDC-VD0514881A | Stock fournisseur | 7.5% | Flux fournisseur expedies | adherence -5.0 pts ; jours stock MP zero +1 ; flux expedies -33079874 |
| 7 | SDC-VD1095770A | Stock fournisseur | 7.5% | Flux fournisseur expedies | adherence -5.0 pts ; jours stock MP zero +1 ; flux expedies -32962466 |
| 8 | SDC-VD0520115A | Stock fournisseur | 7.5% | Flux fournisseur expedies | adherence -5.0 pts ; jours stock MP zero +1 ; flux expedies -32570223 |
| 9 | SDC-VD0508918A | Delai fournisseur | 6.5% | Stock MP a zero | adherence -0.0 pts ; replanifications +25 ; jours stock MP zero +25 ; cout +1.8% |
| 10 | SDC-VD0525412A | Delai fournisseur | 4.9% | Stock MP a zero | adherence -0.6 pts ; replanifications +12 ; nervosite +1 ; jours stock MP zero +12 ; cout +5.3% |
| 11 | SDC-VD0914690A | Fiabilite fournisseur | 3.5% | Volume utile perdu par fiabilite | volume utile perdu par fiabilite -36000000 ; flux expedies -36000000 |
| 12 | SDC-VD0914360C | Delai fournisseur | 2.0% | Cout total | cout +7.9% |
| 13 | SDC-VD0519670A | Stock fournisseur | 0.7% | Stock MP a zero | disponibilite -0.1 pts ; adherence -0.0 pts ; replanifications +1 ; jours stock MP zero +1 ; flux expedies -406890 |
| 14 | SDC-VD0520132A | Cout achat / transport | 0.6% | Cout total | cout +2.6% |
| 15 | SDC-VD0910216A | Qualite / release | 0.3% | Cout total | adherence -0.0 pts ; cout +1.2% |
| 16 | SDC-VD0901566A | Cout achat / transport | 0.3% | Cout total | cout +1.1% |
| 17 | SDC-VD0975221A | Cout achat / transport | 0.2% | Cout total | cout +0.8% |
| 18 | SDC-VD0972460A | Cout achat / transport | 0.2% | Cout total | cout +0.7% |
| 19 | SDC-VD0949099A | Cout achat / transport | 0.2% | Cout total | cout +0.6% |
| 20 | SDC-VD0960508A | Cout achat / transport | 0.2% | Cout total | cout +0.6% |

## Lecture

Cette campagne active un seul risque a la fois sur un seul fournisseur.

- Impact metier observe: KPI bruts qui bougent dans le modele (service, disponibilite, adherence, backlog, nervosite, cout, flux).
- Score decisionnel modele: synthese ponderee provisoire des degradations normalisees, a calibrer avec les industriels.
- Ce n'est pas une probabilite terrain et ce n'est pas un risque reel sans probabilite d'occurrence.

Les familles testees sont: capacite, stock, delai, fiabilite, qualite, appro amont et cout.
