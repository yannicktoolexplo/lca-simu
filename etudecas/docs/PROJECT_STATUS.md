# Bilan de la livraison du 20 septembre 2026

[Comprendre le code et les dossiers](../README.md) · [Documentation par sujet](README.md)

Cette page décrit une livraison de résultats et ses vérifications. L'organisation
du logiciel et son plan de simplification sont dans le README du projet.

**Accès aux résultats : [cartes et livraisons locales](../index.html).** La livraison décrite utilise les calculs `audited_corrections_20260920`. Le [rapport de corrections intégrées](changes/2026-09-20-audit-integrated-corrections.md) décrit les corrections du moteur, des payloads, de la carte et du multi-agent. L'[audit initial](audit_20260920/README.md) reste un état historique des défauts observés sur l'ancienne référence.

**La livraison finale a passé ses contrôles d'intégration documentés.** La [synthèse vérifiable](../artifacts/testing/audit_corrections_20260920/verification-summary.json) identifie la carte, ses sources et ses preuves. Cette couverture ne constitue pas une validation exhaustive de toutes les interactions ni une calibration industrielle.

## Résultats courants

- [Carte nominale corrigée et suivis des lots](../simulation/result/_reruns/audited_corrections_20260920/maps/supply_graph_audited_corrections_20260920.html).
- [Explorateur du nouveau scénario de risque](../simulation/result/_reruns/audited_corrections_20260920/scenario_runs/state_dependent_full/maps/lot_explorer_audited_20260920.html).
- [Diagnostic et sensibilités du nouveau calcul](../simulation/result/_reruns/audited_corrections_20260920/decision_support/index.html).
- [Contre-vérification numérique](changes/2026-09-20-final-map-numeric-verification.md).
- [Replays et qualification indépendante](../artifacts/testing/audit_corrections_20260920/replays/README.md).

Le nominal, `state_dependent_full`, `safety_150` et `expedite_50` ont été recalculés sur 1 825 jours, avec leurs graphes, contrôles et graine 42 conservés. Les sensibilités restent séparées du nominal. Les quatre calculs passent les 62 familles d'invariants, soit **3 867 173 contrôles physiques ponctuels**. L'oracle Excel rapproche **14 600 lignes jour/article**, sans écart quotidien ou hebdomadaire selon le profil source explicité. Les semaines signées négatives sont traitées par report des corrections ; ce n'est pas une égalité aux lignes brutes de l'Excel.

Pour 268091, la première semaine vaut désormais **13 300 UN**. Les quantités physiques en UN restent entières ; les fractions prévisionnelles ne sont pas assimilées à une unité client non servie.

## Vérifications et empreintes

La [preuve numérique finale](changes/2026-09-20-final-map-numeric-verification.md) couvre **567 figures, 1 370 séries, 2 176 246 valeurs recalculées et 8 627 contrôles**, sans écart dans ce périmètre. Les valeurs recalculées comprennent des contrôles hors séries temporelles ; elles ne représentent pas autant d'observations indépendantes. Cette preuve ne certifie ni tous les textes et éléments d'habillage, ni la calibration industrielle.

Les [suites générales et complémentaires](../artifacts/testing/audit_corrections_20260920/final-tests/README.md) ont réussi : **1 035 tests principaux et 70 sous-tests**, avec 2 ignorés et 17 désélectionnés dans la référence. Leurs 751 empreintes étaient identiques avant/après cette exécution. **Une petite correction ultérieure du panneau Données a ensuite passé 18 tests ciblés et 3 sous-tests** : la suite générale n'a donc pas été exécutée sur l'empreinte finale complète. Les tests ignorés portent sur une ancienne fixture opt-in et ne valident pas le nouveau livrable.

Sur l'état final, **156 tests ciblés et 3 sous-tests passent**, après la correction du contrôle des arrondis et la précision FIFO du diagnostic. Les preuves finales couvrent 9 parcours généraux, 87 radars, le clavier des cinq fenêtres, 9 contrôles du suivi détaillé, 7 contrôles de l'explorateur risque et 193 rapprochements du diagnostic. Aucune erreur JavaScript n'a été constatée sur ces parcours. Le gate et le handoff de la toolbox acceptent les empreintes finales ; les exécutions antérieures restent conservées séparément.

## Décisions et limites métier

- **Sécurité confirmée :** jours source interprétés selon lundi-vendredi et dépôt à **100 % des jours source**. Le coefficient historique 0,75 n'est plus la décision courante. Cela n'introduit pas une fermeture physique implicite des opérations le week-end.
- **Durée de fabrication :** `tau_process` conserve son rôle actuel de planification ; son interprétation en durée physique reste à confirmer.
- **Économie :** les bases de prix manquantes sont explicitement inconnues. Les quatre valorisations restent incomplètes ; les montants connus ne suffisent pas à soutenir un classement économique. Opérations, approvisionnements externes et exposition restent distingués.
- **MRP et stock réservé :** les 23 bases statiques et les conventions de propriété/valorisation du réservé restent à examiner.
- **Risques :** application, exposition et association aval sont distinguées ; une concomitance ne prouve pas une causalité. Le taux cumulé ne mesure pas la ponctualité.
- **Incidents de lots :** une exploration d'exposition ou de rappel ne simule pas encore une nouvelle quarantaine, un rebut ou un retard physique ciblé. La règle du premier incident reste à définir après la qualification des hypothèses ouvertes.

## Suivi des lots et historique conservé

Les deux suivis restent disponibles : [explorateur simplifié](EXPLORATEUR_DES_LOTS.md) et suivi détaillé. Les [enquêtes enregistrées](ENQUETES_LOTS.md), [fiches récapitulatives](FICHE_LOT.md), [parcours bidirectionnels](PARCOURS_DES_LOTS.md) et [transports/impacts](TRANSPORTS_ET_IMPACTS.md) gardent leurs guides. Les preuves de leurs livraisons antérieures ne sont pas automatiquement des preuves du dernier HTML.

Dans le nouveau nominal, **PBATCH-411EC755D7110AE0** conserve **1 835 + 12 565 = 14 400 UN**, avec une lecture datée à **J296**. Dans l'ancien `corrected_map_20260918`, les preuves conservées décrivent 53 événements causaux, 16 lots métier et **3 473 + 10 927 = 14 400 UN** ; à la fin de J291, 10 927 UN étaient au dépôt et 3 473 UN en transport. Les différences appartiennent à des calculs différents, pas à un remplacement silencieux des faits historiques.

La [carte examinée initialement](../simulation/result/_reruns/corrected_map_20260918/maps/supply_graph_corrected_map_20260918_enquetes_20260920.html), son [diagnostic](../simulation/result/_reruns/corrected_map_20260918/decision_support/index.html), le [rapport du 18 septembre](../../CORRECTIONS_ETUDECAS_2026-09-18.md) et le [manifeste historique](reference/current.json) restent accessibles. Les nombres d'occurrences et captures des anciennes livraisons restent attachés à leurs propres jeux de données.

## Multi-agent et prochaines vérifications

L'[intégration native et sa toolbox](MULTI_AGENT_OPERATIONNEL.md) sont installées : profils, skills découvrables, commandes déterministes, empreintes et contrats de retour. Le nombre d'agents ne constitue pas une garantie ; les vérifications indépendantes et la provenance des preuves restent nécessaires. La [documentation technique](README.md) et la [procédure de vérification](EXECUTION_VERIFICATION.md) décrivent les contrôles à reprendre après un changement.

Poursuivre la qualification des hypothèses industrielles, puis préparer le premier incident physique de lot et son expérience comparative. Les [priorités détaillées](changes/2026-09-20-audit-integrated-corrections.md#priorités-après-cette-livraison) précisent les points ouverts. Le chargement des profils personnalisés dans une nouvelle session Codex reste à observer. Les gros artefacts restent locaux et ne sont pas ajoutés au versionnement.
