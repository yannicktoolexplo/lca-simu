# Audit des règles MRP — 14 novembre 2026

Le cœur du MRP a sa place : demande datée, déduction des stocks et engagements, lots à l’usine, besoins composants et disponibilité distincte du physique. Les priorités portent sur la consommation mensuelle, les engagements/horizons figés, les transferts indépendants des lots fabriqués et la séparation du rejeu industriel du calcul autonome. Aucune capacité n’est recalibrée dans cet audit.

**46 règles examinées**, couvrant les 16étapes documentées et leurs transitions. Chaque avis porte sur le code et les sources identifiés; il ne certifie pas une règle industrielle entière.

[Rapport lisible règle par règle](../../resultats/audit_regles_mrp_20261114.html) · [Matrice et preuves](../../artifacts/testing/audit_regles_mrp_20261114/final_manifest.json)

## Priorités

1. **Consommation mensuelle.** Le candidat existe, mais le nominal reste hebdomadaire. Vérifier la répartition hebdomadaire, les changements de mois et l’intégration avant activation.
2. **Ordres fermes et horizons figés.** Représenter quatre semaines à 1810 et huit à 1430 selon un contrat explicite. Conserver les ordres engagés ; préciser ce qui peut être avancé, reporté ou annulé.
3. **Demandes de transfert.** Dissocier la quantité commandée et expédiée des lots de 600/3 200 kg ; les lots de fabrication restent inchangés.
4. **Besoins propres et plans industriels.** Les plans industriels connus remplacent certains besoins du modèle. Conserver ce mode comme rejeu, puis tester séparément le calcul autonome depuis son programme.
5. **Provenance et exceptions.** Corriger observé/reconstruit et rendre explicites reports de commandes, cadence d’achat et critères de secours.

## Règles à préserver

Le besoin de Muret est déjà sans minimum ni multiple de fabrication :100unités restent100au dépôt, tandis que l’usine268967 applique son lot107800. Les sécurités sources restent à100%, en jours lundi–vendredi. Aucune double protection n’est démontrée dans cet audit. Les stocks, réceptions fermes et surplus sont déduits une seule fois; une réception tardive conserve un retard, pas une double commande.

La remise à zéro mensuelle concerne la prévision. Le reste à prévoir doit encore être diminué des stocks et engagements avant de devenir une production. La règle mensuelle n’est pas «produire automatiquement700/3» si des stocks couvrent déjà une partie du besoin.

## Matrice complète

### A01 — Stock initial physique et utilisable

**À confirmer / paramétrer** · Place : Initialisation.

Actif : Stock source à100%, disponibilité initiale active. Les stocks retenus sont présents physiquement mais inutilisables avant leur libération; aucune création générique de stock.

Fondement : Photos industrielles; disponibilité reconstruite avec le premierMRP du5janvier ramené au1erjanvier.

Avis : Conserver les états distincts. La connaissance anticipée de cette photoMRP est une hypothèse historique à déclarer.

Preuves : `etudecas/simulation/engine/run_first_simulation.py:6783`, `etudecas/simulation/engine/run_first_simulation.py:14989`, `etudecas/config/mrp_reference_20261013/engine_arguments.json`.

### A02 — Commandes et fabrications en cours au démarrage

**À confirmer / paramétrer** · Place : Engagements initiaux.

Actif : CarnetExtract; matières initiales traitées comme déjà incorporées. Conserve les échéances après janvier; conditionnement initial séparé des matières déjà supposées en encours.

Fondement : Extract ne donne ni date de création, ni statut de travail, ni identifiant de lot.

Avis : Conserver les engagements, mais préciser ce qui était réellement commencé. Ne pas consommer deux fois les matières ni supprimer les ordres futurs.

Preuves : `etudecas/simulation/engine/run_first_simulation.py:14815`, `etudecas/simulation/engine/run_first_simulation.py:17063`.

### A03 — Demande réelle entière et service client

**À conserver** · Place : Exécution client.

Actif : Historique daté; allocation quotidienne entière. La demande du jour et le retard sont servis avec le stock chez le client, sans effacer le solde.

Fondement : Historique commercial exact; partage uniforme sur septjours est une convention.

Avis : Bonne séparation de la demande et des livraisons; deuxjours de transport ne constituent pas une rupture de Muret.

Preuves : `etudecas/simulation/engine/run_first_simulation.py:4972`, `etudecas/simulation/engine/run_first_simulation.py:18628`.

### A04 — Dernière prévision connue à la décision

**À conserver** · Place : Entrées du MRP.

Actif : Versions connues seulement. Sélectionne le dernier snapshot déjà connu; un zéro explicite reste zéro.

Fondement : Projection industrielle mensuelle; date de connaissance au lundi du snapshot.

Avis : Conserver la causalité temporelle; ne pas choisir une version future parce qu’elle améliore les résultats.

Preuves : `etudecas/simulation/engine/run_first_simulation.py:5184`, `etudecas/simulation/current_reference.py:477`.

### A05 — Prévision manquante

**À confirmer / paramétrer** · Place : Convention d’entrée.

Actif : Dernière période connue puis période la plus proche. Une période jamais connue reprend le taux d’une période voisine dans une version déjà disponible.

Fondement : La première semaine partielle de janvier manque dans Projection.

Avis : Évite le faux zéro mais peut déformer le démarrage. Rendre ce remplacement visible, sans injecter la demande future.

Preuves : `etudecas/simulation/engine/run_first_simulation.py:5315`.

### A06 — Consommation mensuelle et répartition du reliquat

**À corriger** · Place : Besoin indépendant.

Actif : Nominal hebdomadaire; candidat mensuel disponible mais non sélectionnable dans current/regenerate. Le nominal expire le reliquat chaque semaine. Le candidat calcule maximum(prévision du mois−demande connue du mois,0), puis répartit sur les jours futurs.

Fondement : L’industriel confirme un compteur mensuel et une répartition revue chaque semaine.

Avis : Qualifier la variante, clarifier les semaines partielles et l’exposer dans le parcours courant. Le reliquat n’est pas directement une quantité à fabriquer: stocks et engagements restent à déduire.

Preuves : `etudecas/simulation_prep/inject_mrp_seed_data_v2.py:511`, `etudecas/simulation/engine/run_first_simulation.py:5349`, `etudecas/simulation/engine/monthly_forecast.py:34`.

### A07 — Reset du mois et demande après2025

**À conserver** · Place : Prévision / scénario.

Actif : Reset de prévision dans le candidat; croissance prospective5%. La remise à zéro concerne uniquement le compteur prévisionnel. Croissance et reconduction saisonnière sont un scénario déclaré.

Fondement : Reset mensuel confirmé; croissance non observée industriellement.

Avis : Ne jamais effacer commandes, stocks ou retard au changement de mois. Les oracles locaux du compteur ne prouvent pas toute son intégration physique.

Preuves : `etudecas/simulation/engine/monthly_forecast.py:34`, `etudecas/simulation/current_reference.py:489`.

### A08 — Besoins datés et retard compté une fois

**À conserver** · Place : MRP aval.

Actif : Prévisions futures et backlog ajouté une seule fois. Place le retard client courant dans le premier besoin futur; conserve les échéances.

Fondement : Demande réelle et besoin planifié sont deux états distincts.

Avis : Conserver; définir séparément date de commande, date demandée et date promise pour mesurer un service industriel.

Preuves : `etudecas/simulation/engine/run_first_simulation.py:18916`, `etudecas/simulation/engine/run_first_simulation.py:18937`.

### A09 — Besoin non lotifié de Muret

**À conserver** · Place : MRP dépôt.

Actif : LotSizing entier sans minimum/multiple àD1920. Un besoin de100 unités donne100 au dépôt; le fabricant268967 propose107800selon son lot.

Fondement : Retour industriel:D1920 transmet son besoin, l’usine lotifie.

Avis : Déjà conforme: ne pas enlever les lots usine ni confondre besoin et quantité transportée.

Preuves : `etudecas/simulation/engine/run_first_simulation.py:15135`, `etudecas/simulation/engine/run_first_simulation.py:15147`.

### A10 — Correcteur local et lissage du programme

**À isoler / clarifier** · Place : Contrôleur préparatoire.

Actif : Gain0,25 et mémoire0,20; décision finale par plan daté. L’intention locale est calculée mais le plan daté la remplace pour le lancement; des usages de propagation/diagnostic subsistent.

Fondement : Coefficients hérités du modèle, pas une règle ERP confirmée.

Avis : Clarifier et mesurer ses consommateurs avant une éventuelle suppression. Ne pas régler ces gains pour masquer le mauvais calendrier.

Preuves : `etudecas/simulation/engine/run_first_simulation.py:16669`, `etudecas/simulation/engine/run_first_simulation.py:17751`, `etudecas/simulation/engine/run_first_simulation.py:19254`.

### A11 — Déduction des stocks, commandes et surplus

**À conserver** · Place : Besoin net.

Actif : Affectation datée unique; réception tardive conservée. Un besoin10, stock3 et réceptionferme7 tardive ne créent pas un second achat; le retard reste visible.

Fondement : Conservation des ressources et des engagements.

Avis : Cœur utile du MRP. Un retard n’est pas un service satisfait; les accélérations doivent être des actions explicites.

Preuves : `etudecas/simulation/engine/mrp_planning.py:1868`, `etudecas/simulation/engine/run_first_simulation.py:5733`.

### A12 — Plan du soir et exécution le lendemain

**À confirmer / paramétrer** · Place : Interface planification/exécution.

Actif : Snapshot de la veille, revalidation avec état du jour. Autorise uniquement les propositions dues; sans snapshot antérieur, aucune nouvelle campagne àJ0.

Fondement : Convention de pas journalier, pas preuve de l’heureERP.

Avis : Conserver explicitement tant que l’heure de calcul réelle est inconnue. Un seul jour ne suffit pas à expliquer plusieurs semaines de décalage.

Preuves : `etudecas/simulation/engine/run_first_simulation.py:5714`.

### A13 — Ordre proposé, ferme, commencé et horizon figé

**À compléter** · Place : Engagement de fabrication.

Actif : Campagne engagée dès lancement autorisé; aucun gel4/8 semaines. Le30septembre, une campagne268967 de107800 est déjà créée avec travail physique0. La variante ferme au premier travail existe mais est inactive.

Fondement : L’industriel indique4 semaines à1810 et8 semaines à1430; bornes, reports, annulations et exceptions à confirmer.

Avis : Ajouter un véritable contrat de fermeté et de gel par site. Ne pas assimiler un horizon figé à un arrêt de fabrication ni créer les ordres initiaux manquants.

Preuves : `etudecas/simulation/engine/run_first_simulation.py:17908`, `etudecas/simulation/current_reference.py:498`, `etudecas/artifacts/testing/cc20261109/nominal/data/production_plan_events.csv:193`.

### A14 — Lot de fabrication268967

**À conserver** · Place : Usine.

Actif : Minimum=maximum107800. Lot fixe107800; le surplus couvre la suite.

Fondement : Flow_Data_Inventory_and_Replenishment_rules.xlsx, TailedeLot E2:G2.

Avis : Ce lot a sa place à l’usine. Il ne représente ni une capacité journalière ni une obligation de camion complet.

Preuves : `etudecas/simulation/engine/run_first_simulation.py:7127`, `etudecas/simulation/engine/mrp_planning.py:1958`.

### A15 — Minimum, multiple et maximum268091

**À confirmer / paramétrer** · Place : Usine.

Actif : Minimum28800, multiple14400, maximum142485. Le plus grand lot compatible est129600; besoin200000donne129600+72000.

Fondement : Minimum/maximum présents dansFlow. Confirmation antérieure du multiple attribuée dans les métadonnées du bundle.

Avis : Conserver provisoirement: absence d’une colonne multiple ne réfute pas la confirmation antérieure. Retrouver la décision précise; le maximum ne doit pas tronquer le besoin.

Preuves : `etudecas/simulation/engine/mrp_planning.py:1813`, `etudecas/config/mrp_reference_20261013/graph.json.gz#meta.mrp_lot_policy_rebuild`.

### A16 — Campagne et travail en cours

**À conserver** · Place : Exécution / engagement.

Actif : Une campagne active par article, restant et travail distingués. Une campagne active bloque un nouveau lancement pour cet article; un lot n’existe physiquement qu’à son achèvement.

Fondement : Convention de séquencement; conservation matière nécessaire.

Avis : Conserver les comptes. Confirmer séparément le nombre de campagnes préparables en parallèle, sans confondre encours et PF disponibles.

Preuves : `etudecas/simulation/engine/run_first_simulation.py:5729`, `etudecas/simulation/engine/run_first_simulation.py:19031`.

### ACH01 — Exploser les composants depuis les fabrications proposées

**À conserver** · Place : planification MRP.

Actif : mps_lotified; dated_relation_consistent_v1. Chaque proposition de fabrication lotifiée produit un besoin composant à sa date de lancement, multiplié par le coefficient BOM; ordre aval→amont.

Fondement : Retour13novembre: l'usine achète selon son propre programme. Coefficients BOM sourcés; formats confirmés conservés.

Avis : C'est le bon lien entre PF et matières; ne pas remplacer la BOM par un coefficient ajusté aux courbes.

Preuves : `etudecas/simulation/engine/run_first_simulation.py:4376`, `etudecas/simulation/engine/run_first_simulation.py:4664`, `etudecas/docs/REGLES_MRP.md:949`.

### ACH02 — Ne réexploser que le travail restant des campagnes engagées

**À conserver** · Place : planification avec états d'exécution.

Actif : remaining campaign quantity; WIP credited once. La future réception PF vaut restant+encours; les composants portent seulement sur le restant, placé à demain.

Fondement : Une matière déjà consommée ne doit pas être commandée deux fois. La date demain est une convention conservatrice, pas le calendrier atelier réel.

Avis : Préserve engagé/exécuté et évite doubles achats. La datation globale du restant doit être affinée si les consommations sont étalées dans une campagne longue.

Preuves : `etudecas/simulation/engine/run_first_simulation.py:4342`, `etudecas/simulation/engine/run_first_simulation.py:4369`, `etudecas/simulation/engine/run_first_simulation.py:4690`.

### ACH03 — Ajouter les autres usages sur le même stock

**À isoler / clarifier** · Place : entrée de demande partagée puis exécution.

Actif : external_component_calendar; historical Scan3 residuals. Besoins propres et autres usages ont des consommations/backlogs distincts mais prélèvent le même stock.

Fondement : Partage/formats confirmés; attribution et dates des autres usages souvent reconstruites.

Avis : La fonction a sa place. Les profils reconstruits depuis les observations doivent rester des entrées de rapprochement historique, pas des règles universelles ni une validation prédictive indépendante.

Preuves : `etudecas/simulation/engine/mrp_planning.py:983`, `etudecas/simulation/engine/mrp_planning.py:1321`, `etudecas/simulation/engine/run_first_simulation.py:16647`, `etudecas/artifacts/testing/analyse_reel_268967_20261114/control/mechanisms.json`.

### ACH04 — Remplacer des besoins calculés par les sorties prévues des plans industriels

**À isoler / clarifier** · Place : rejeu du planning industriel, hors noyau autonome.

Actif : industrial_purchase_need_policy=source_weekly_with_committed_floor_v1 sur338929/M1810,333362/M1430,042342/M1430. Sur semaines renseignées, les prévisions révocables issues du modèle sont remplacées par le besoin industriel connu, moins les besoins engagés; les engagés restent datés et uniques. Semaine absente conserve le calcul modèle.

Fondement : Les plans industriels datés existent, mais les recopier ne démontre pas que le MRP autonome les reproduit.

Avis : Utile comme témoin de rejeu. Pour tester la chaîne autonome propre programme→matières, séparer explicitement cette injection plutôt que la présenter comme règle industrielle générale.

Preuves : `etudecas/config/mrp_reference_20261013/graph.json.gz:meta.industrial_purchase_need_policy`, `etudecas/simulation/engine/run_first_simulation.py:15743`, `etudecas/simulation/engine/run_first_simulation.py:4492`, `etudecas/simulation/engine/mrp_planning.py:899`.

### ACH05 — Lisser les taux de besoin sur sept jours

**À confirmer / paramétrer** · Place : signal de planification/protection.

Actif : mrp_demand_signal_smoothing_days=7; smoothed_cover_requirement pairs. Lissage des signaux/taux, avec moyenne sur l'horizon de couverture pour certaines cibles; les propositions datées sont ensuite explosées aux dates de lancement, pas physiquement réparties en sept sorties.

Fondement : Pas de confirmation d'un lissage uniforme7 jours; export hebdomadaire ne démontre pas ce comportement.

Avis : Peut stabiliser le pilotage mais doit être paramétré, distingué du calendrier et testé séparément. Ne pas conclure qu'il consomme deux fois un besoin sans trace.

Preuves : `etudecas/config/mrp_reference_20261013/engine_arguments.json`, `etudecas/simulation/engine/run_first_simulation.py:16573`, `etudecas/simulation/engine/run_first_simulation.py:16608`, `etudecas/simulation/engine/run_first_simulation.py:4664`.

### ACH06 — Anticiper les achats par la sécurité source et garder un stock fixe

**À conserver** · Place : planification achat.

Actif : purchase_need_date_policy=source_safety_additive_v2; fixed_floor_mode=additive. Avance les besoins de jours lundi–vendredi; ajoute le stock fixe une seule fois; le besoin physique conserve sa date.

Fondement : Jours et quantités de sécurité sourcés; la combinaison additive est une convention sélectionnée, pas une quantité physique consommée.

Avis : La séparation besoin physique/protection est correcte. Maintenir les valeurs nominales demandées; ne pas compenser un mauvais calendrier par plus de sécurité.

Preuves : `etudecas/simulation/engine/mrp_planning.py:2075`, `etudecas/simulation/engine/run_first_simulation.py:4575`, `etudecas/config/mrp_reference_20261013/graph.json.gz:meta.purchase_need_date_policy`, `etudecas/artifacts/testing/audit_regles_mrp_20261114/achats/oracles.json:fixed_floor_once`.

### ACH07 — Maintenir une protection de stock pour fabrications, transferts et dépôt

**À conserver** · Place : planification.

Actif : source_stock_floor_v1 etrolling_source_workdays_v1. Ciblemax(stockfixe,besoinsdatésdansfenêtresécurité), enveloppe cumulative sans nouvelle consommation; pas addition des protections alternatives.

Fondement : Sécurité dépôt268967=25 JO historique sélectionnée par utilisateur; latestsource60 JO non automatiquement substitué. Régimes/dateeffet industriels à confirmer.

Avis : La sécurité ne doit pas disparaître après une sortie ni être ajoutée comme double demande. Le code refuse les protections concurrentes. Un besoin de100 àJ10, protégé par3 joursouvrés, est couvert par100 àJ7 avec le plancher glissant comme avec le décalage: aucune double protection démontrée. Conserver les paramètres source.

Preuves : `etudecas/simulation/engine/mrp_planning.py:2289`, `etudecas/simulation/engine/run_first_simulation.py:19129`, `etudecas/simulation/engine/run_first_simulation.py:4587`, `etudecas/config/mrp_reference_20261013/graph.json.gz:meta.chain_safety_projection_policy`, `etudecas/artifacts/testing/audit_regles_mrp_20261114/achats/oracles.json:depot_floor_equivalence_example`.

### ACH08 — Déduire une seule fois stock, réceptions fermes et surplus, même tardifs

**À conserver** · Place : netting MRP.

Actif : all_future commitments; FIFO besoins/ressources. Les engagements tardifs couvrent des quantités mais affichent le retard; pas de nouvel achat automatique pour la même quantité. Détenu devient disponible seulement à sa libération.

Fondement : Conservation des engagements indispensable; politique d'expédition urgente/annulation industrielle non identifiée.

Avis : Bonne protection contre doubles comptes. Prévoir des exceptions explicites si l'industriel autorise accélération ou remplacement; ne pas traiter un engagement tardif comme service satisfait.

Preuves : `etudecas/simulation/engine/mrp_planning.py:1839`, `etudecas/simulation/engine/mrp_planning.py:1868`, `etudecas/artifacts/testing/audit_regles_mrp_20261114/achats/oracles.json:firm_late_no_duplicate`, `etudecas/artifacts/testing/audit_regles_mrp_20261114/achats/oracles.json:held_stock_not_available_early`.

### ACH09 — Choisir fabriquer, transférer ou acheter par article/site

**À conserver** · Place : structure MRP.

Actif : unique BOM-or-transport boundary; explicit sourcing split required. Le parcours descend la nomenclature et remonte les ressources; fabrication et achat simultanés sont interdits sans partage explicite. Des stocks gérés localement horsBOM ont leurs politiques candidates.

Fondement : StructureBOM/FIA et sites documentés; politiques001848Gien/001893Gaillac/002612Gaillac candidates.

Avis : La règle a sa place; une route absente doit rester signalée, pas inventée depuis celle d'un autre fournisseur.

Preuves : `etudecas/simulation/engine/run_first_simulation.py:4376`, `etudecas/simulation/engine/run_first_simulation.py:4382`, `etudecas/simulation/engine/run_first_simulation.py:2623`, `etudecas/docs/REGLES_MRP.md:1075`.

### ACH10 — Regrouper les besoins et autoriser les commandes à certaines dates

**À confirmer / paramétrer** · Place : politique de revue achats.

Actif : purchase_grouping_days=1; weekly_calendar_v1 dimanche pour338929/333362. Le regroupement dequantités porte sur une date; la revue hebdomadaire restreint séparément les dates de commande des deux emballages.

Fondement : Revue dimanche déduite expérimentalement des versionsMRP; pas de calendrier réel d'achat confirmé.

Avis : Ces paramètres ont leur place s'ils décrivent la pratique. Ne pas inférer achat une fois par semaine du seul fait que l'exportMRP est hebdomadaire.

Preuves : `etudecas/simulation/engine/mrp_planning.py:1938`, `etudecas/simulation/engine/run_first_simulation.py:2597`, `etudecas/simulation/engine/run_first_simulation.py:15740`, `etudecas/simulation/engine/run_first_simulation.py:20512`, `etudecas/config/mrp_reference_20261013/graph.json.gz:meta.supplier_purchase_review_policy`.

### ACH11 — Transformer les quantités standard FIA en minimum et multiple

**À confirmer / paramétrer** · Place : paramètres d'achat et logistique.

Actif : binding standards for most offers; nonbinding338929/333362. La quantitéstandard est minimum/multiple lorsqu'elle estcontraignante;338929 et333362sont explicitementnoncontraignants.

Fondement : LesFIAportentquantitéstandard,pasunepreuveminimum/multiple; le bundle le reconnaît.

Avis : La lotification fournisseur est pertinente mais sa contrainte exacte doit être sourcée. Éviter de généraliser une exigence minimum à toute quantité standard.

Preuves : `etudecas/simulation/engine/run_first_simulation.py:19206`, `etudecas/simulation/engine/run_first_simulation.py:19214`, `etudecas/simulation/engine/run_first_simulation.py:20966`, `etudecas/config/mrp_reference_20261013/graph.json.gz:meta.sourcing_policy.rows[0].offers`.

### ACH12 — Arrondir les unités physiques et la précision des achats massiques

**À conserver** · Place : unités physiques et précision décisionnelle.

Actif : UN entières; nearest_kg_half_up_v1 pour besoinnetmassique. UNentiersgarantis. Arrondi du besoinnet au kg choisi par utilisateur, reliquat conservé sans falsifier stock/consommation.

Fondement : UNphysiquesentièrescontrat; précisionKGestchoixdéclaréutilisateur, nonobservéeuniversellement.

Avis : Conserver l'intégritédes unités et tracer la précision. Un besoin0,4 kgpeut ne pas déclencher d’achat,avec−0,4 kgprojeté visible: ce n'est pas une suppression physique.

Preuves : `etudecas/simulation/engine/run_first_simulation.py:2243`, `etudecas/simulation/engine/mrp_planning.py:1953`, `etudecas/artifacts/testing/audit_regles_mrp_20261114/achats/oracles.json:rounding_deficit_stays_visible`.

### ACH13 — Garder les propositions révocables puis appliquer le lot réel à l'engagement

**À conserver** · Place : engagement achats.

Actif : minimum_admissible_standard_until_release_v1; execution_standard_for_unambiguous_offer_v1. Propositiondimensionnéeaveclepluspetitstandardadmissiblejusqu'aulancement; fournisseurretenuimposesonlotetleplanestrecalculé; surplusdéduit.

Fondement : Distinctionproposition/commanderequise; choixprovisoireestconventiondeplanification.

Avis : Évite de transformer une proposition en achat ferme et d'acheter deux fois le surplus. Surveiller cohérence du fournisseur prévu et engagé.

Preuves : `etudecas/simulation/engine/mrp_planning.py:2718`, `etudecas/simulation/engine/run_first_simulation.py:20533`, `etudecas/config/mrp_reference_20261013/graph.json.gz:meta.purchase_proposal_lot_policy`, `etudecas/artifacts/testing/audit_regles_mrp_20261114/achats/oracles.json:surplus_reused`.

### ACH14 — Choisir un fournisseur principal et un secours daté

**À confirmer / paramétrer** · Place : politique de sourcing.

Actif : 001848/M1810 primary_backup; additive safety passes protected needs. Rôlesconfirmés;le secourspeutprotégeruneéchéanceanticipée,mêmesileprincipalsatisfaitla date physique. Engagementsfermesprotégéscontrele rachatdansbrancheadditive.

Fondement : Rôlesprincipal/secoursconfirmés, déclencheurindustrielinconnu; codeexperimental.

Avis : Règle pertinente si ses critères sont explicites. Ne pas appeler toute commande secours une rupture physique évitée: oracle10 UNàJ20,principal10 jours,secours5 jours donne0secourssans sécurité et10avec10 JO, service physique à temps dans les deux cas.

Preuves : `etudecas/simulation/engine/mrp_planning.py:2157`, `etudecas/simulation/engine/mrp_planning.py:2517`, `etudecas/simulation/engine/mrp_planning.py:2635`, `etudecas/artifacts/testing/audit_regles_mrp_20261114/achats/oracles.json:backup_trigger_example`.

### ACH15 — Répartir les commandes multi-fournisseurs par quotas70/30 etc.

**À confirmer / paramétrer** · Place : politique sourcing, pasloiMRP.

Actif : legacy shares après tri, horsprincipal/secours. Deuxoffres70/30,trois70/20/10,quatre70/20/5/5,sansquotaERPobservé.

Fondement : Conventiondumodèleexplicitée; aucunjournaldeparts réelles validantcesratios.

Avis : Les multi-sources sont utiles ; conserver les quotas comme hypothèses de scénario tant qu’ils ne sont pas sourcés, et non comme règle industrielle confirmée.

Preuves : `etudecas/simulation/engine/run_first_simulation.py:8314`, `etudecas/simulation/engine/mrp_planning.py:2363`, `etudecas/docs/REGLES_MRP.md:1169`.

### ACH16 — Distinguer commande, réception physique, contrôle et disponibilité

**À conserver** · Place : planification→exécution.

Actif : supplier source delivery days; exact weekday receipt calendar. Choisitdernièrecommandefaisablepourladisponibilitéprotégée;siimpossibleretardexplicite,pascommandedanslepassé. Le stockretenu n'estpasutilisable.

Fondement : DélaisFIA ettempsréceptionMRP; calendriers/joursfériés/fermetures/périmètresàconfirmerfluxparflux.

Avis : Structure indispensable ; les valeurs et étapes doivent être vérifiées. target_day du plan porte la disponibilité, pas la réception physique industrielle.

Preuves : `etudecas/simulation/engine/mrp_planning.py:1894`, `etudecas/simulation/engine/mrp_planning.py:1969`, `etudecas/simulation/engine/run_first_simulation.py:19200`, `etudecas/simulation/engine/run_first_simulation.py:20565`.

### ACH17 — Compléter le carnet initial avec des entrées prévues du premierMRP

**À isoler / clarifier** · Place : initialisation/reconstitution historique.

Actif : first_known_mrp_near_horizon_v1. Deuxcompléments338929 de122234 et300793 UNduMRP5janvier deviennent engagements; date physiquelejeudietfournisseurunique sontconventions. Pascomplément333362effectifdanscesrows.

Fondement : SourceEntréeprévueagrégée,paspreuved'ordresfermesidentifiés;enregistréequandconnueJ4,pasfuturinjectéàJ0.

Avis : Reconstruction utile pour le cas d’ouverture, à isoler par mode et hypothèse. Elle ne prouve pas l’existence d’ordres industriels certains ; rechercher leur identité source.

Preuves : `etudecas/config/mrp_reference_20261013/graph.json.gz:meta.initial_purchase_book_completion`, `etudecas/simulation/engine/run_first_simulation.py:6426`, `etudecas/simulation/engine/run_first_simulation.py:15910`.

### ACH18 — Reporter des promesses fournisseurs encore supposées modifiables

**À isoler / clarifier** · Place : politique de replanification achats.

Actif : opening_purchase_postponement etsupplier_promise_postponement known_need_and_protection_v1. SeptlignesExtractetlespromessesagrégées338929/333362peuventêtredécaléesavantdate physiqueinitiale,soushypothèsenondépart;jamaisuneexpéditionconnue exécutée.

Fondement : Exportne prouvepasl'autorisationdereport niabsenceexpédition; assumptions explicites.213 révisionsdansrésumé5ans, pascompte2025.

Avis : Replanifier peut avoir sa place ; la permission doit venir du statut de l’ordre ou rester une expérience. Ne pas inférer que toute promesse future est modifiable.

Preuves : `etudecas/config/mrp_reference_20261013/graph.json.gz:meta.opening_purchase_postponement_policy`, `etudecas/simulation/engine/run_first_simulation.py:15028`, `etudecas/simulation/engine/mrp_planning.py:1600`, `etudecas/artifacts/testing/cc20261109/nominal/summaries/first_simulation_summary.json:policy.supplier_promise_postponement`.

### P01 — Départ usine vers Muret après fabrication

**À conserver** · Place : Transport physique.

Actif : push_released_available_v1. Pousse les PF terminés utilisables et non réservés vers le dépôt, en excluant encours, stocks retenus et réceptions futures.

Fondement : Principe industriel de transfert au dépôt déjà retenu; fréquence réelle non identifiée.

Avis : Bonne place dans l’exécution logistique, pas dans le calcul des besoins. Conserver les étapes de transport.

Preuves : `etudecas/simulation/engine/run_first_simulation.py:2832`, `etudecas/simulation/engine/run_first_simulation.py:2857`.

### P02 — Libération des PF à Muret

**À conserver** · Place : Stock utilisable.

Actif : 268091:10 JO;268967:15 JO après réception à Muret. La même quantité passe de physique retenue à disponible; aucun nouveau lot ni deuxième réception.

Fondement : Temps MRP sourcés et lieu de traitement attribué à la confirmation du20octobre dans finished_goods_release_policy.

Avis : Conserver le lieu déjà retenu. Vérifier le statut des événements réels avant de déplacer ou raccourcir le délai pour améliorer une courbe.

Preuves : `etudecas/simulation/engine/run_first_simulation.py:3492`, `etudecas/simulation/engine/run_first_simulation.py:13967`, `etudecas/config/mrp_reference_20261013/graph.json.gz#meta.finished_goods_release_policy`.

### P03 — Libération des semi-finis à Gaillac

**À confirmer / paramétrer** · Place : Exécution amont.

Actif : 693055:28 JO;773474:33 JO après fin physique simulée. Gaillac garde et libère ses lots avant qu’ils deviennent utilisables pour un transfert.

Fondement : Lieu confirmé par industriel. DuréesMRP existent; position exacte des33 JOaprès achèvement explicitement hypothétique.

Avis : Conserver le lieu; distinguer durée documentée et événement à partir duquel elle court. Ne pas supprimer ces contrôles parce que le volume annuel est trop faible.

Preuves : `etudecas/config/mrp_reference_20261013/graph.json.gz#meta.production_release_policy`, `etudecas/simulation/engine/run_first_simulation.py:3566`, `etudecas/simulation/engine/run_first_simulation.py:13972`.

### P04 — Commande de transfert693055 fractionnable

**À corriger** · Place : MRP transfert.

Actif : Transportmultiple0 mais commandemultiple600 kg. Pour un besoin net de 300 kg à Avène, stock destinataire déjà déduit, le plan propose 600 kg et conserve 300 kg de surplus. Cet oracle ne teste pas la disponibilité physique à Gaillac.

Fondement : Industriel: livraison à la demande, plus petite que le standard possible. La commandepar600 est étiquetée candidate.

Avis : Dissocier également la quantité commandée du lot fabriqué. Garder fabrication600 kg, stock existant et engagements.

Preuves : `etudecas/simulation/engine/run_first_simulation.py:2875`, `etudecas/config/mrp_reference_20261013/graph.json.gz#meta.internal_component_policy`.

### P05 — Transfert773474 imposé par lots de3200 kg

**À corriger** · Place : Transport / paramètre de liaison.

Actif : Multiple3200 kg hérité du lot, consolidation7 jours. Un besoin300 kg devient un chargement3200 kg dans le helper de consolidation; le code transporte une contrainte issue de la fabrication.

Fondement : Le lot de fabrication est documenté; le minimum camion et la cadence7 jours sont dérivés, pas une obligationERP démontrée.

Avis : Rendre quantité et cadence de transfert indépendantes de la fabrication, puis éprouver le flux natif. Ne pas qualifier de confirmé un camion parce que son lot de fabrication l’est.

Preuves : `etudecas/simulation/lot_policy/engine_adapter.py:297`, `etudecas/simulation/lot_policy/engine_adapter.py:264`, `etudecas/simulation/engine/run_first_simulation.py:8220`, `etudecas/simulation/engine/run_first_simulation.py:21033`.

### P06 — Transport et traitement à destination

**À confirmer / paramétrer** · Place : Datation logistique.

Actif : Gaillac→Gien10 jours+6 JO;Gaillac→Avène7 jours+7 JO. Garde distincts départ, réception physique et disponibilité; ne compte pas le contrôle comme une nouvelle réception.

Fondement : Temps àréception6/7 JO documentés.10 joursFIA et7 joursphysiques ne sont pas des transits industriels identifiés; FIA69305570 jours non réconciliés.

Avis : Conserver les étapes, confirmer leurs valeurs et inclusions. La coïncidence hebdomadaire des flux ne prouve ni transportnul ni durée exacte.

Preuves : `etudecas/config/mrp_reference_20261013/graph.json.gz#meta.internal_component_policy`, `etudecas/simulation/engine/run_first_simulation.py:2675`.

### P07 — Marge de production tau_process

**À conserver** · Place : Planification.

Actif : Marge de datation, pas duréephysique. La marge contribue aux dates du plan; les matières, lots et capacités bornent le travail physique.

Fondement : Sens physique non confirmé; consigne utilisateur de ne pas le convertir arbitrairement.

Avis : Conserver cette distinction. Pour allonger une fabrication, il faut une durée/ressource explicite, pas réinterpréter silencieusement ce paramètre.

Preuves : `etudecas/simulation/engine/run_first_simulation.py:15133`, `etudecas/simulation/engine/run_first_simulation.py:18269`.

### P08 — Calendriers et arrondi des délais

**À confirmer / paramétrer** · Place : Calendrier / exécution.

Actif : Sécurités lundi–vendredi; délai2,5 arrondià2. Le calcul journalier arrondit certains transits; les fermetures explicites ne couvrent pas toutes les usines.

Fondement : Calendrier de sécurité demandé; calendrier atelier complet et heure des événements absents.

Avis : Déclarer les conventions par étape et site; ne pas transformer le week-end ou une fermeture supposée en panne. Hors cette revue: calibrage capacité.

Preuves : `etudecas/simulation/engine/run_first_simulation.py:8148`, `etudecas/simulation/current_reference.py:510`.

### P09 — Délai court du packaging338929

**À confirmer / paramétrer** · Place : Approvisionnement externe.

Actif : Référence42 jours avantréception +6 JOtraitement. La précision industrielle vise338929 et un stock fournisseur permettant deuxsemaines.

Fondement : RéférenceFIA42 jours; nouveau témoignage14 jours liéà un stock non quantifié.

Avis : Préparer une règle de réapprovisionnement depuis stock fournisseur. Ne pas remplacer tous les délais par14 jours ni supprimer le traitement; préciser quantité disponible et événement terminal.

Preuves : `etudecas/docs/changes/2026-11-13-retour-industriel-mrp.md:147`, `etudecas/config/mrp_reference_20261013/graph.json.gz#meta.supplier_delivery_receipt_policy`.

### P10 — Consommation physique, réservation et suivi des lots

**À conserver** · Place : Exécution matière.

Actif : Prélèvement uniquement au travail; identités des lots conservées. Réserver ne consomme pas; une libération ne fabrique pas. Les registres suivent les mouvements réels du modèle.

Fondement : Bilans et dates vérifiables; lots industriels non identifiés dans les sources.

Avis : Conserver les deux suivis et leurs invariants. Un bilan fermé ne prouve pas la bonne affectation à un format réel.

Preuves : `etudecas/simulation/engine/run_first_simulation.py:18269`, `etudecas/docs/REGLES_MRP.md:949`.

### P11 — Étiquette observé ou reconstruit des autres usages

**À corriger** · Place : Provenance des résultats.

Actif : Export quotidien trop agrégé; détail justedans les notes des lots. Pour042342,315088814 unités classéesobservées incluent289429814 reconstituées et25659000 observées.

Fondement : Contre-vérification registre/source lors de l’analyse précédente, même empreinte moteur.

Avis : Corriger la qualification et les cellules de provenance sans changer les flux physiques. Ce défaut ne constitue pas une nouvelle règleMRP.

Preuves : `etudecas/simulation/current_reference.py:549`, `etudecas/simulation/current_reference.py:559`, `etudecas/artifacts/testing/analyse_reel_268967_20261114/control/mechanisms.json`.

### P12 — Aléas, coûts et indicateurs de service

**À isoler / clarifier** · Place : Scénario et évaluation, hors calculdesbesoins.

Actif : Nominal déterministe; risques séparés et états conservés. Un incident agit sur une opération, une disponibilité ou un flux; coût de stock etCA ne remplacent pas une mesurede service enunités.

Fondement : Pas de journal industriel complet incidents/livraisons. CapacitéGaillac/M1430 exclue de ce recalibrage.

Avis : Conserver les mécanismes scientifiques et les oracles indépendants. Ne pas utiliser un aléa pour cacher une règle de planification manquante.

Preuves : `etudecas/docs/DEVELOPPEMENT_SCIENTIFIQUE.md:113`, `etudecas/docs/SCENARIO_COMPARISON.md`.

## Portée des contrôles

12 tests ciblés en mémoire et 50 contrôles sur des oracles indépendants sont exécutés ; les 21 contrôles du bloc achats sont rapportés séparément dans son manifeste. Ils portent sur les fonctions sélectionnées (compteur, lots, besoins nets, transferts, secours), pas sur une simulation complète. Le test local du compteur ne démontre pas à lui seul que tout le moteur conserve stocks/engagements au changement de mois. La revue indépendante finale précise la couverture et les réserves.

La documentation générée globale était déjà désynchronisée lors de l’analyse précédente; ce défaut ne devient pas une réussite ici. Pas de tests globaux, de fichiers factices, de navigateur/Node, de nouveau run ni de promotion du nominal. Les 5calculs de l’explorateur sont des constats dans le journal d’outils, pas un manifeste supplémentaire.

## Principes ERP consultés

- [Oracle: planning time fence et date des commandesclients](https://docs.oracle.com/en/cloud/saas/supply-chain-and-manufacturing/26b/faupc/considerations-for-configuring-supply-plan-attributes.html) : ExempleERP: pas de nouvelordre/avancement dans le gel; reports/annulations peuvent rester permis. Dates demandéedépart ouarrivée distinctes. Ne prouve pas la configuration industrielle.
- [SAP: safety time](https://help.sap.com/SAPHELP_SCM700_EHP02/helpdata/EN/2f/31c95360267614e10000000a174cb4/content.htm?no_cache=true) : La sécurité temporelle avance la couverture sur le calendrier de travail; ne crée pas une consommation physique.

Ces sources décrivent des possibilités d’ERP. Les pratiques rapportées par l’industriel et les données datées restent prioritaires pour choisir nos paramètres.
