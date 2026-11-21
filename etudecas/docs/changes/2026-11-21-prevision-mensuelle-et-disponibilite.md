# Pics de lancement, prévision mensuelle et disponibilités à Muret

Les deux causes testées contribuent aux pics du 268091. La première
semaine de prévision remonte brusquement dans certaines versions et
le recalcul mensuel concentre le reliquat sur les derniers jours.
Les besoins de la première semaine du MRP industriel portent un
signal distinct, plus large que la seule demande historique.
[Comparaison par produit et par date](../../resultats/prevision_mensuelle_20261121.html) ·
[Preuves](../../artifacts/testing/prevision_mensuelle_20261121/final_manifest.json)

## 1. Isoler les deux effets en simulation

Le témoin utilise les besoins connus à la clôture. Chaque variante
reprend les mêmes commandes déjà publiées, stocks, engagements,
dates de contrôle, tailles de lot et gels de 4 et 8 semaines.
Les 20 et 25 jours ouvrés de sécurité sont conservés. Chaque plan
recalcule leur équivalent en volume avec sa propre prévision.
L’évaluation garde aussi la demande et la protection du témoin afin
de mesurer la couverture réellement retirée par chaque variante.

- **Première semaine** · reprendre la valeur de la version précédente
  pour la même semaine cible lorsqu’elle existe. Les autres semaines
  utilisent la dernière version connue.
- **Rythme mensuel** · faire le bilan hebdomadaire de la demande connue
  mais limiter le rythme prévisionnel au rythme d’ouverture du mois.
  Le reliquat non affecté s’éteint en fin de mois. C’est un essai sur la
  prévision, sans plafond de fabrication.
- **Les deux** · appliquer ensemble les deux interventions.

Les 44 plans hebdomadaires retrouvent les propositions archivées
du client et du dépôt. Le plan de l’usine concorde pour 42 de ces
revues et pour les deux clôtures ciblées du 268091. Le 6 avril et le
4 mai à Gien sont écartés des comparaisons. Sur les **44 cas comparables**,
les interventions réduisent respectivement **13, 11 et 16 pics**.
Dans chaque cas où le pic baisse, le plan dégrade la couverture de
la demande prévue à date, la marge de sécurité, ou les deux.

| Clôture du 268091 | Variante | Pic journalier proposé après le gel | Manque supplémentaire maximal à Muret | Écart maximal ajouté à la cible de sécurité |
| --- | --- | ---: | ---: | ---: |
| 27 janvier | Témoin | 259 200 | 0 | 0 |
| 27 janvier | Première semaine | 100 800 | 216 000 | 216 000 |
| 27 janvier | Rythme mensuel | 72 000 | 590 400 | 590 400 |
| 27 janvier | Les deux | 28 800 | 777 600 | 777 600 |
| 28 avril | Témoin | 345 600 | 0 | 0 |
| 28 avril | Première semaine | 72 000 | 0 | 367 892 |
| 28 avril | Rythme mensuel | 86 400 | 0 | 278 257 |
| 28 avril | Les deux | 43 200 | 5 002 | 574 801 |

Les valeurs sont des unités. Le pic porte sur les 28 premiers jours
révisables. Les écarts sont mesurés par rapport au témoin et à ses
besoins, avec les disponibilités simulées de l’usine et du dépôt.
Les quantités présentées sont des propositions de lancement.
[184 plans](../../artifacts/testing/prevision_mensuelle_20261121/replan.json) ·
[Vérification indépendante](../../artifacts/testing/prevision_mensuelle_20261121/validator/coverage_oracle.json)

## 2. Mesurer la couverture de la demande observée ensuite

J’ai gardé les plans calculés à l’époque simulée et utilisé la demande
historique uniquement pour les évaluer après coup. Je l’ai répartie
sur les jours auxquels elle se rapporte, puis regroupée le lundi qui
suit la clôture, faute de dates individuelles de commande. Sur les 44 cas
comparables, les quatre variantes couvrent cette demande avec les deux
calendriers, **si les réceptions projetées se réalisent aux dates prévues**.
En janvier, la variante combinée réduit le stock projeté moyen à Muret
de 491 047 à 272 088 unités sur la fenêtre et le premier calendrier.
[Évaluation rétrospective](../../artifacts/testing/prevision_mensuelle_20261121/retrospective_score.json)

| Périmètre de couverture simulée, sans nouveau lancement | 268091, revues avec un manque | 268967, revues avec un manque |
| --- | ---: | ---: |
| Stock utilisable déjà à Muret | 18 ou 19 sur 24 selon le calendrier | 0 sur 20 |
| Avec les lots déjà attendus ou en contrôle à Muret | 10 sur 24 | 0 sur 20 |
| Avec aussi le stock et les engagements déjà présents en usine | 0 sur 24 | 0 sur 20 |

Exemple du 27 janvier pour le 268091. Pour la demande reconstruite au
jour effectif, le manque maximal est de 551 266 unités avec le seul
stock utilisable à Muret, puis de 411 606 avec ses engagements locaux.
Il est résorbé par les engagements existants d’Avène aux dates simulées.
La confirmation des dates de disponibilité devient donc le contrôle
le plus important avant toute réduction de protection.
[Décomposition du stock](../../artifacts/testing/prevision_mensuelle_20261121/stock_buffer.json)

Un retard hypothétique de 7 jours sur les réceptions déjà engagées
reste absorbé. Avec 14 jours de retard sur les engagements d’Avène,
trois revues sur 24 du 268091 font apparaître un manque lorsque la
demande est répartie sur ses jours d’effet. Elles couvrent surtout
le même épisode de début mars. Pour la revue du 27 janvier, le
manque atteint 28 713 unités et commence le 4 mars. Le regroupement
des commandes le lundi suivant masque ce manque. À Gien, le stock
initialement disponible couvre les cas testés. Ce stress conserve
toutes les quantités et décale seulement les disponibilités.
[Essai de retard](../../artifacts/testing/prevision_mensuelle_20261121/delays/staged_delays.json)

## 3. Repartir des données industrielles

- **Prévision commerciale.** Le premier point vise toujours le lundi
  suivant le repère de version. Le classeur fournit des valeurs
  exportées. En remplaçant ce point par l’ancienne valeur de la même
  date, l’écart à la demande historique baisse dans 11 cas sur 11
  pour le 268091 et augmente dans 8 sur 11 pour le 268967. Le signe
  s’inverse pour le 268091 au premier point de 2026, sans historique
  de demande comparable. [Cellules et comparaisons](../../artifacts/testing/prevision_mensuelle_20261121/source/forecast_semantics.json)
- **Reconstruction mensuelle.** Le budget d’ouverture du 268091
  dépasse la demande reconstituée dans les 12 mois de 2025. En janvier,
  il atteint 1 079 096 unités pour 231 419 demandées. Les cinq jours
  imputés représentent 235 380 unités. En avril, le budget est
  de 750 999 pour 268 860 demandées, sans imputation. Les publications
  tardives expliquent 51 677 unités du reliquat de janvier et 13 153
  de celui d’avril. L’écart existait donc pour l’essentiel dès
  l’ouverture du mois. [Décomposition](../../artifacts/testing/prevision_mensuelle_20261121/validator/monthly_bias.json)
- **Besoins au MRP de Muret.** Pour une même semaine cible, le
  besoin augmente quand elle devient la première ligne dans 50 revues
  sur 50 pour le 268091 et 44 sur 50 pour le 268967. Comparer le saut
  au reliquat supposé de la semaine précédente donne un écart absolu
  moyen de 95 350 et 36 242 unités respectivement. Le 16 juin, le plan
  du 268091 passe de 73 218 à 874 805 unités avec 563 066 prévues
  en stock de fin de semaine précédente. [Versions MRP](../../artifacts/testing/prevision_mensuelle_20261121/buckets/mrp_bucket_comparison.json) ·
  [Contrôle du reliquat](../../artifacts/testing/prevision_mensuelle_20261121/buckets/mrp_bucket_persistence.json)
- **Stock et clients.** Le stock physique de début couvre la demande
  hebdomadaire dans les 102 semaines-produit renseignées. Les dates
  de libération, les réservations et les départs imputés aux commandes
  restent inconnus. Le 17 mars, le MRP du 268091 indique 717 587
  unités de sortie prévue pour 81 108 demandées. Le besoin de sortie
  MRP et la demande historique doivent rester distincts.
  [Stocks et couverture](../../artifacts/testing/prevision_mensuelle_20261121/muret/muret_coverage.json) ·
  [Lignes MRP](../../artifacts/testing/prevision_mensuelle_20261121/muret/plan_scope_check.json)

## Prochaine décision

Rapprocher deux familles de lignes ERP sur les cas du 27 janvier, du
28 avril et du 16 juin. Il faut d’une part le type de besoin du MRP,
sa quantité, sa version, sa date d’échéance initiale et son statut.
Il faut d’autre part les lots utilisables à Muret, leur date de
libération et la commande à laquelle un départ a été affecté. Les cas
du 268967 servent de contrôle avant d’appliquer une règle commune.
Quatre tests ciblés et un oracle indépendant vérifient les calculs.
La référence active est conservée. Les essais utilisent les plans
archivés et des recalculs locaux, sans nouvelle exécution physique
du moteur sur l’année.
