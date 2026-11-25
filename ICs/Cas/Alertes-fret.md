# Quand faut-il rouvrir le dossier de fret express ?

L’essai compare des règles qu’un gestionnaire peut appliquer à la fin du mois. Le service est jugé insuffisant lorsque la masse servie représente strictement moins de 99 % de la masse demandée. Le signal utilise exclusivement les informations du mois précédent.

## De l’envoi urgent à la revue mensuelle

Sur un envoi particulier, le suivi Cargo iQ distingue le chargement, l’arrivée et la remise au destinataire. Pour expliquer une urgence, demander au transitaire l’heure prévue, l’heure effective et le premier départ de remplacement. Pour juger une alerte, noter également quand le report a été annoncé. [Jalons de transport Cargo iQ](https://iata-cargo.github.io/ONE-Record/2025-07/Orchestration/orchestration-mop/)

Le jeu de test mesure des masses mensuelles. Il permet de dimensionner une revue périodique. Expliquer le retard d’un envoi demanderait des horaires par expédition.

## Comparaison sur les mêmes mois

Quatre trajectoires simulées comportent chacune 240 mois. Le premier mois initialise l’alerte de chaque trajectoire. Les 956 couples restants contiennent 273 mois sous l’objectif de service et 683 mois au niveau attendu ou au-dessus. Les trois seuils de saturation représentent la part du plafond de fret express consommée le mois précédent. Un seuil atteint déclenche une alerte. La règle de persistance déclenche l’alerte lorsque le service du mois précédent était déjà insuffisant.

| Règle | Alertes justes | Fausses alertes | Mois manqués | Mois calmes sans alerte |
| --- | ---: | ---: | ---: | ---: |
| Saturation ≥ 90 % | 257 | 622 | 16 | 61 |
| Saturation ≥ 95 % | 251 | 616 | 22 | 67 |
| Saturation ≥ 99 % | 247 | 611 | 26 | 72 |
| Persistance du service insuffisant | 136 | 140 | 137 | 543 |
| Aucune alerte | 0 | 0 | 273 | 683 |

À 95 % de saturation, 251 des 273 mois dégradés sont détectés, mais seuls 251 des 867 dossiers ouverts concernent un mois effectivement dégradé. La persistance déclenche 276 revues, dont 136 justifiées. Il est donc utile de chiffrer le temps d’une relance et la conséquence d’un mois passé sous l’objectif.

## Le coût qui ferait changer de règle

Entre la saturation à 95 % et la persistance, l’exploitation accepte 476 fausses alertes supplémentaires pour manquer 115 mois de moins. Si chaque fausse alerte a le même coût, et si chaque mois manqué a lui aussi un coût constant, la saturation à 95 % devient préférable à la persistance lorsque le rapport de ces deux coûts, mois manqué sur fausse alerte, dépasse 476 / 115, soit environ **4,14**. Cette bascule compare uniquement les deux règles indiquées. Le coût d’une revue justifiée et le montant d’une perte industrielle ne sont pas mesurés ici.

Les mois 2 à 120 comptent 90 mois dégradés sur 476 décisions. Les mois 121 à 240 en comptent 183 sur 480. Pour reprendre le [comptage détaillé](alertes-fret.csv), additionner les deux périodes pour chaque règle, puis diviser les alertes justes par le nombre de mois dégradés pour obtenir le rappel. La précision divise les alertes justes par toutes les alertes déclenchées. Elle reste indéfinie pour une règle qui ne déclenche aucune alerte. Les quatre trajectoires partagent des hypothèses de simulation et ne constituent pas quatre observations industrielles indépendantes.
