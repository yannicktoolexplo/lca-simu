# Suite de l’audit MRP — essais discriminants du 14 novembre 2026

L’audit est étendu à 51 règles et mécanismes. Les essais confirment la conservation au changement de mois et plusieurs règles de calcul, mais révèlent aussi des hypothèses actives et des défauts techniques. Aucun moteur ni paramètre nominal n’a été modifié.

[Rapport avec les 51 règles](../../resultats/audit_regles_tests_20261114.html) · [Preuves et limites](../../artifacts/testing/audit_regles_suite_20261114/final_manifest.json) · [Audit initial conservé](2026-11-14-audit-regles-mrp.md)

## Conclusions éprouvées

### Le reset mensuel conserve les obligations physiques

Dans le cas synthétique v5 utilisant le contrat commercial courant, le 31 janvier puis le 1er février : prévision restante 0→535, retard client 515→520, encours 60→62, composants utilisables 940→938 et 50 toujours retenus. La réception initiale reste identifiable et n’est libérée qu’au jour 35. Ces résultats ne mesurent pas une amélioration du réel 268967.

### Une petite différence de transfert peut faire prévoir un lot entier

Avec besoin de 1 190 kg et stock source de 590 kg, la commande arrondie à 1 200 kg fait prévoir deux fabrications de 600 kg ; une commande de 1 190 kg n’en demande qu’une. À stock source 600 kg, les deux variantes prévoient 600 kg : l’effet dépend de l’état, il n’est pas systématique. Ce cas exerce le planificateur réseau, pas l’exécution physique.

### Une protection hebdomadaire supplémentaire était insuffisamment explicitée

Pour 693055 à Avène, current applique la protection à la clôture du samedi, puis relâche le plancher. Le cas synthétique conserve les besoins physiques mais décale une réception planifiée de 50 g du jour 6 au jour 10. Cette règle active n’est pas une pratique ERP confirmée. Les jours de sécurité source restent inchangés en valeur.

### Le gel industriel n’est toujours pas implémenté

Le calcul conserve une réception ferme de 50 tout en autorisant 50 supplémentaires immédiatement. Conserver les engagements n’interdit donc pas les nouveaux ordres dans les 4 ou 8 semaines. Les modifications permises et exceptions industrielles restent à préciser.

### Le mode générique peut utiliser de la demande future

Dans v4, besoin au jour 30 = 590 de retard + 337×20 de prévisions connues + 27×9 999 hors couverture, soit 277 303. Modifier uniquement un point physique futur de 9 999 à 1 abaisse ce besoin à 7 357. Le contrat commercial courant utilise une autre branche : son API ignore ce remplacement brut et reprend une prévision connue.

## Complément commercial

Le contrat commercial source a été exécuté séparément en v5 : les prévisions au-delà de leur couverture reprennent 10 ou 20 unités issues de versions connues, pas les 9 999 unités du futur physique. Un point de calendrier apparaît : le budget de février vaut 540, soit 2 jours à 10 issus de l’ancienne semaine et 26 jours à 20, et non les 560 initialement attendus. Cette attente initiale incorrecte est conservée ; aucune donnée n’a été modifiée pour la faire passer. Le réemploi de la semaine en cours au début du mois doit être confronté à la pratique industrielle avant activation du mensuel.

## Défauts techniques et contrôles

**Export incomplet.** Une configuration acceptée calcule 40 jours, puis échoue à l’export : trois champs de protection existent dans les lignes mais pas dans les colonnes. Échec v3 conservé ; activer d’autres politiques pour v4 ne corrige pas ce défaut.

**Stock ajouté hors du graphe.** La configuration data_poc.json ajoute 107 800 unités de M-1430/EX-344135 dans le mini-réseau. Ce stock constant est conservé dans les sorties et isolé dans nos bilans, pas effacé. Les totaux globaux du mini-réseau ne doivent donc pas être interprétés comme ceux des seuls articles déclarés.

**Contrôles incomplets ou corrigés.** Le premier bilan omettait une vraie réception de 750 composants dans le témoin hebdomadaire ; il a été corrigé à partir de tous les événements, sans rejouer le moteur. La première qualification refusée faute d’audit des lots est conservée ; les audits natifs ont ensuite été réellement exécutés. Les erreurs de préparation et de script restent dans les preuves.

## Couverture réelle

25 cas pytest ciblés réussis, oracles séparés et expériences natives. Les compteurs d’assertions ne représentent ni autant de scénarios indépendants ni autant de règles industrielles validées.

| Règle | Niveau | Portée |
|---|---|---|
| A01 — Stock initial physique et utilisable | Calcul natif ciblé | États utilisable/retenu éprouvés ; l’initialisation depuis les photos industrielles reste une reconstruction. |
| A02 — Commandes et fabrications en cours au démarrage | Calcul natif ciblé | Commande initiale de 50 composants réellement reçue puis libérée. Statut des OF industriels initiaux non validé. |
| A03 — Demande réelle entière et service client | Exécution physique synthétique | Demande, service et retard conservés dans quatre exécutions natives de 40 jours, dont deux sous contrat commercial source. |
| A04 — Dernière prévision connue à la décision | Calcul natif ciblé | Versions connues et budget du mois exercés ; pas de certification de toute la chaîne par ce seul contrôle. |
| A05 — Prévision manquante | Calcul natif ciblé | Prévision absente testée ; fuite du futur reproduite dans le mode générique, distinct du contrat commercial current. |
| A06 — Consommation mensuelle et répartition du reliquat | Exécution physique synthétique | Consommation mensuelle réellement active dans le moteur du mini-réseau ; nominal current toujours hebdomadaire. |
| A07 — Reset du mois et demande après2025 | Exécution physique synthétique | Passage janvier/février : budget renouvelé, encours, commande, stock et retard conservés. |
| A08 — Besoins datés et retard compté une fois | Calcul natif ciblé | Retard net des engagements vérifié ; le besoin énorme du mode générique est expliqué par sa fin de prévision, pas par un retard ajouté plusieurs fois. |
| A09 — Besoin non lotifié de Muret | Lu / configuré | Règle relue ; aucun essai spécifique supplémentaire exécuté ici. |
| A10 — Correcteur local et lissage du programme | Lu / configuré | Règle relue ; aucun essai spécifique supplémentaire exécuté ici. |
| A11 — Déduction des stocks, commandes et surplus | Calcul natif ciblé | Preuve ciblée de l’audit précédent, sans nouvel essai spécifique. |
| A12 — Plan du soir et exécution le lendemain | Calcul natif ciblé | J0 sans lancement, snapshot de veille et revalidation avec stock/campagne exercés. |
| A13 — Ordre proposé, ferme, commencé et horizon figé | Calcul natif ciblé | Ferme 50 conservé, nouvel ordre 50 autorisé à J1 : ce comportement ne réalise pas un gel interdisant les nouveaux ordres. |
| A14 — Lot de fabrication268967 | Calcul natif ciblé | Mécanisme générique minimum/multiple/maximum éprouvé ; le paramètre industriel de 107 800 unités est relu, pas qualifié par ces petits cas. |
| A15 — Minimum, multiple et maximum268091 | Calcul natif ciblé | Mécanisme générique de lots éprouvé ; paramètres PF 28 800/14 400/142 485 relus et distincts des quantités des oracles. |
| A16 — Campagne et travail en cours | Exécution physique synthétique | Encours réellement continu 60→62 au changement de mois ; cas de restant BOM sans recompter le travail passé. |
| ACH01 — Exploser les composants depuis les fabrications proposées | Calcul natif ciblé | Explosion multi-niveaux et composants partagés : stock affecté une fois, besoin depuis les nouveaux lots. |
| ACH02 — Ne réexploser que le travail restant des campagnes engagées | Calcul natif ciblé | Campagne de 10, dont 7 déjà travaillés, ratio 2 : besoin restant 6, pas 20. |
| ACH03 — Ajouter les autres usages sur le même stock | Lu / configuré | Règle relue ; aucun essai spécifique supplémentaire exécuté ici. |
| ACH04 — Remplacer des besoins calculés par les sorties prévues des plans industriels | Calcul natif ciblé | Mode actif source_weekly_with_committed_floor_v1 : engagé conservé, total industriel non ajouté deux fois, absence distincte de zéro. |
| ACH05 — Lisser les taux de besoin sur sept jours | Lu / configuré | Règle relue ; aucun essai spécifique supplémentaire exécuté ici. |
| ACH06 — Anticiper les achats par la sécurité source et garder un stock fixe | Calcul natif ciblé | Preuve ciblée de l’audit précédent, sans nouvel essai spécifique. |
| ACH07 — Maintenir une protection de stock pour fabrications, transferts et dépôt | Calcul natif ciblé | Adaptateur current réellement installé : plancher hebdomadaire 693055. Voir X01, absent de la première matrice détaillée. |
| ACH08 — Déduire une seule fois stock, réceptions fermes et surplus, même tardifs | Calcul natif ciblé | Preuve ciblée de l’audit précédent, sans nouvel essai spécifique. |
| ACH09 — Choisir fabriquer, transférer ou acheter par article/site | Calcul natif ciblé | Réseau natif de besoins transfert→fabrication→composant éprouvé, avec stocks source explicites. |
| ACH10 — Regrouper les besoins et autoriser les commandes à certaines dates | Calcul natif ciblé | Preuve ciblée de l’audit précédent, sans nouvel essai spécifique. |
| ACH11 — Transformer les quantités standard FIA en minimum et multiple | Lu / configuré | Règle relue ; aucun essai spécifique supplémentaire exécuté ici. |
| ACH12 — Arrondir les unités physiques et la précision des achats massiques | Calcul natif ciblé | Preuve ciblée de l’audit précédent, sans nouvel essai spécifique. |
| ACH13 — Garder les propositions révocables puis appliquer le lot réel à l'engagement | Calcul natif ciblé | Transfert partiel et reliquat ferme suivis sans seconde commande ; pas toutes les transitions d’achat du current. |
| ACH14 — Choisir un fournisseur principal et un secours daté | Calcul natif ciblé | Preuve ciblée de l’audit précédent, sans nouvel essai spécifique. |
| ACH15 — Répartir les commandes multi-fournisseurs par quotas70/30 etc. | Calcul natif ciblé | Partage 70/30 avec lots 80/50 : achat 130 ; retard conservé si une offre est plus lente. Choix industriel encore à confirmer. |
| ACH16 — Distinguer commande, réception physique, contrôle et disponibilité | Exécution physique synthétique | Réception physique, retenue puis disponibilité exercées dans le mini-réseau, calendrier ouvré également contrôlé en mémoire. |
| ACH17 — Compléter le carnet initial avec des entrées prévues du premierMRP | Lu / configuré | Règle relue ; aucun essai spécifique supplémentaire exécuté ici. |
| ACH18 — Reporter des promesses fournisseurs encore supposées modifiables | Calcul natif ciblé | Report de promesse met à jour calendrier et engagement sans changer stock/quantité ; permission expirée ou ordre déjà parti bloque le report. |
| P01 — Départ usine vers Muret après fabrication | Lu / configuré | Règle relue ; aucun essai spécifique supplémentaire exécuté ici. |
| P02 — Libération des PF à Muret | Calcul natif ciblé | Cas natifs de contrôle PF 10/15 jours ouvrés ; localisation industrielle attribuée aux sources, pas démontrée par ces calculs. |
| P03 — Libération des semi-finis à Gaillac | Lu / configuré | Règle relue ; aucun essai spécifique supplémentaire exécuté ici. |
| P04 — Commande de transfert693055 fractionnable | Calcul natif ciblé | 4 couples de plans réseau : l’arrondi du transfert peut créer un lot supplémentaire à Gaillac ; contrôle frontière sans effet fabrication conservé. |
| P05 — Transfert773474 imposé par lots de3200 kg | Calcul natif ciblé | Adaptateur de consolidation 300→3 200 kg éprouvé dans l’audit précédent ; pas de départ physique natif 773474 exercé ici. |
| P06 — Transport et traitement à destination | Calcul natif ciblé | Séparation réception/contrôle/disponibilité éprouvée sur le cas synthétique ; durées industrielles de Gaillac toujours à confirmer. |
| P07 — Marge de production tau_process | Lu / configuré | Règle relue ; aucun essai spécifique supplémentaire exécuté ici. |
| P08 — Calendriers et arrondi des délais | Calcul natif ciblé | Réception vendredi + 2 jours ouvrés = mardi, ou mercredi si lundi explicitement fermé. Arrondi du transit de 2,5 jours non exercé ici. |
| P09 — Délai court du packaging338929 | Lu / configuré | Règle relue ; aucun essai spécifique supplémentaire exécuté ici. |
| P10 — Consommation physique, réservation et suivi des lots | Calcul natif ciblé | 30 présents → 19 libres + 11 réservés ; départ des 11 sans second débit. Bilans et audits de lots des essais natifs contrôlés. |
| P11 — Étiquette observé ou reconstruit des autres usages | Lu / configuré | Règle relue ; aucun essai spécifique supplémentaire exécuté ici. |
| P12 — Aléas, coûts et indicateurs de service | Lu / configuré | Règle relue ; aucun essai spécifique supplémentaire exécuté ici. |
| X01 — Protection 693055 à la clôture du samedi | Calcul natif ciblé | Même besoin de 100 g et plancher de 100 g : réception planifiée de 50 g à J6 en protection quotidienne, à J10 avec l’adaptateur hebdomadaire. Stock projeté temporaire 50 g au lieu de 100 g, sans déficit physique dans ce calcul. |
| X02 — Expédition client limitée à la demande connue | Calcul natif ciblé | Les prévisions ne remplissent pas le stock client ; les engagements ouverts sont déduits, y compris tardifs. Deux jours de transport laissent un retard visible sans doubler les expéditions. |
| X03 — Délais et lots propres à chaque offre fournisseur | Calcul natif ciblé | Les fractions de quotas héritent de leur offre. Ce choix peut augmenter la quantité et laisser du retard ; il ne garantit pas l’optimisation du service. |
| X04 — Plafond des lots engagés et poursuite dans la journée | Calcul natif ciblé | Plafond current 20 par bloc de 7 jours depuis J0 pour trois fabrications. Poursuite intrajournalière et capacité restante testées ; le plafond réel industriel n’est pas identifié. |
| X05 — Priorité des modes statique, dynamique et lissé | Calcul natif ciblé | Vrai parseur current : 0 paire statique finale, 23 dynamiques et lissées, 2 standards d’achat non contraignants ; table des 69 couples disponible. |

## Suite prioritaire

1. Corriger le contrat d’export et empêcher les stocks hors graphe non explicitement autorisés ; ces défauts techniques sont distincts du modèle industriel.
2. Clarifier les semaines à cheval sur deux mois, puis qualifier le mensuel dans le réseau industriel complet avant de l’exposer ; ne pas promouvoir automatiquement une nouvelle référence.
3. Définir et représenter les ordres fermes et le gel 4/8 semaines.
4. Comparer les transferts sans multiple de fabrication et la protection hebdomadaire, une intervention à la fois, avec conservation des lots fabriqués et des engagements.
5. Reprendre le calendrier 268967 avec ces règles explicites avant de calibrer une capacité ou un incident.

## Limites

- Les expériences sont synthétiques et utilisent le moteur natif ; elles ne constituent pas une nouvelle simulation du réseau industriel complet.
- Aucun réglage de capacité, aucun ajustement par référence, aucune promotion du mensuel dans le nominal.
- Le minimum de fabrication reste distinct du minimum de transfert ; les stocks des petits exemples sont des conditions déclarées, pas des stocks industriels observés.
- Le lissage des 23 couples est activé et résolu, mais son effet complet dans current reste à mesurer ; les achats initiaux reconstruits et délais industriels restent à confirmer.
- Les règles classées « lu/configuré » n’ont pas été transformées en succès de tests. Risques, coûts et validation industrielle globale ne sont pas certifiés par cet audit MRP.
- Pas de navigateur ni de JavaScript exécuté. Le contrôle documentaire global précédent reste refusé pour cinq familles désynchronisées.
