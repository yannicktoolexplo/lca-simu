# Matières, emballages, réceptions et incidents

## Lecture métier

La référence article, le lot du fabricant, la réception, l'occurrence de stock,
le contenant et le transport sont des identités distinctes. Un même lot fabricant
peut être reçu en plusieurs fois. Une réception peut contenir plusieurs lots
fabricants. Un contenant peut regrouper des quantités de plusieurs réceptions,
si cette composition est documentée. La palettisation estimée ne crée jamais
d'identifiants de palettes réelles.

Le numéro fabricant n'est pas déduit d'un identifiant BATCH, SHIP, d'une commande,
d'une quantité ou d'une proximité de dates. Les données actuelles fournissent des
identités simulées et des événements de réception, sans numéro fabricant
documenté. La carte affiche donc « Lot fournisseur inconnu ». Le statut qualité
reste également « non renseigné » : une réception ne prouve pas une libération
par le contrôle qualité.

Références consultées le 19 septembre 2026 :

- [GS1, standard de traçabilité](https://www.gs1.org/standards/gs1-global-traceability-standard/current-standard) : distinguer produit/lot, unités logistiques et événements de réception/expédition, en conservant leurs liens.
- [Commission européenne, BPF chapitre 4, § 4.22–4.24](https://health.ec.europa.eu/system/files/2016-11/chapter4_01-2011_en_0.pdf) : enregistrer fabricant, fournisseur, numéro fabricant, réception et quantité pour les matières et emballages.
- [Commission européenne, BPF chapitre 5, § 5.30–5.34 et 5.45–5.48](https://health.ec.europa.eu/document/download/4a1fdb4f-6f6f-49c4-b264-8056e5bbe078_en?filename=chapter_5.pdf) : contrôles à réception, distinction des lots et identification des emballages. Cette référence est pharmaceutique ; elle ne constitue pas une qualification réglementaire de notre cas.

## Ce que montre la carte

Le suivi de lots comporte une section « Matières, emballages et réceptions ».
Chaque article peut être développé pour voir :

- événement de réception, date, site, provenance et occurrence de stock ;
- lot fabricant documenté ou simulé, source de l'information et quantité attribuée ;
- quantité reçue et quantité prélevée par les fabrications nommées dans la ligne ;
- identités et contenus des contenants à réception, lorsqu'ils sont renseignés ;
- expédition et propositions de regroupement camion, explicitement estimatives.

Les quantités restent séparées par article et unité. Un stock initial est
identifié comme tel. Les stocks agrégés d'usine ne sont pas additionnés aux
réceptions. Une fabrication intermédiaire peut figurer dans la chaîne : la
colonne de consommation nomme la fabrication qui a réellement prélevé la matière.

Pour PBATCH-411EC755D7110AE0, l'article 338929 donne quatre réceptions de 5 000 UN,
et des prélèvements respectifs de 2 000, 5 000, 5 000 et 2 400 UN. Le total prélevé
est 14 400 UN. Les 20 000 UN reçues ne sont pas le total consommé par cette
fabrication. Les identités simulées BATCH partagées par certaines réceptions ne
sont pas présentées comme des numéros fabricant observés.

## Explorer un incident

Le bouton « Explorer un rappel de cette réception » met en évidence son périmètre
aval dans le registre existant. Si le lot fabricant ou un contenant est renseigné,
il peut également servir de cible. La liste des fabrications permet de passer
d'un lot potentiellement concerné à l'autre. Fermer l'exploration efface cette
sélection, sans changer le calcul nominal.

Le périmètre est une **liste conservative à examiner** :

- seuls les liens physiques de transport et production de quantité positive sont parcourus ;
- une cible réception n'englobe pas les autres réceptions du même article ;
- une cible lot fabricant regroupe ses réceptions explicitement rattachées ;
- un incident natif sur une expédition part de ses occurrences réceptionnées, pas de tout le stock fournisseur dont elle a prélevé une partie ;
- les chemins qui se rejoignent ne comptent pas deux fois la même occurrence ;
- en cas de mélange sans affectation précise, la réception entière et sa descendance constituent un périmètre possible. Aucune proportion de produits défectueux n'est inventée.

Un rappel peut concerner des fabrications antérieures à sa découverte. Cette vue
parcourt donc l'ensemble du registre simulé, pas seulement les événements après
une date de détection. Les champs de date des incidents importés sont informatifs
dans cette exploration ; ils ne déclenchent pas de blocage physique.

Les incidents déjà identifiés par `risk_event_ids` dans les événements moteur
sont affichés comme enregistrés. Les aperçus importés portent obligatoirement
`scenario_preview`. Les propositions de camions ne peuvent pas servir de cible
physique : ce ne sont pas des identifiants de chargements exécutés.

**Limite actuelle : cette exploration ne recalcule pas les stocks, pertes,
délais, coûts ou niveaux de service.** La simulation future d'une quarantaine,
d'un rebut ou d'un retard exigera d'appliquer l'événement à l'état physique au
jour voulu puis de rejouer le scénario. Le registre existant de risques continue
de traiter les effets déjà implémentés ; cette extension n'ajoute pas un nouveau
moteur d'incidents. Exposition généalogique et effet causal restent distincts.

## Données complémentaires et contrat

Le constructeur du suivi lit facultativement `material_traceability.json` à côté
de `production_lot_events.csv`, ou le chemin explicite `material_traceability_json`.
Un fichier explicitement demandé et absent fait échouer la construction.
Le [fichier exemple](examples/material_traceability.example.json) est fictif,
séparé de la base et n'est pas chargé automatiquement.

Version : `material-traceability/1.0`.

| Collection | Contenu |
|---|---|
| `origins` | `id`, `manufacturer_id`, `item_id`, `batch_number`, `status` (`observed` ou `simulated`), `source_reference` |
| `allocations` | `receipt_id` (identifiant LEVT de réception), `origin_id`, `quantity`, `uom` |
| `handling_units` | `id`, `kind`, `status`, `source_reference`, `contents` : réception, quantité, unité |
| `incidents` | `id`, `label`, `kind`, `day`, `status: scenario_preview`, `source_reference`, `target_type`, `target_id` |

Les types d'incident acceptés sont `quality_recall`, `quarantine` et
`transport_delay`. Les cibles sont `receipt`, `supplier_lot`, `handling_unit` et
`shipment` ; un retard de transport doit cibler une expédition. Le libellé seul
ne change pas l'algorithme physique : ces incidents importés sont des aperçus.

`observed` signifie qu'une source a été déclarée par l'importateur. Le programme
vérifie la cohérence de l'import, pas l'authenticité du certificat fournisseur.
La clé fabricant + article + numéro de lot distingue les origines ; le nom du
fournisseur commercial peut être différent de celui du fabricant.

Les allocations partielles laissent un reliquat inconnu. Un fractionnement de
stock entièrement identifié et d'origine unique conserve cette origine dans les
transports. Si le parent mélange plusieurs origines sans détail du prélèvement,
les origines possibles sont conservées sans fabriquer une répartition. Une
identité explicite contradictoire avec des parents entièrement connus est refusée.
Chaque réception utilise une occurrence de stock distincte.

## Vérifications et reproduction

Le module refuse les doublons, références inconnues, unités incompatibles,
quantités non finies, fractions physiques en UN, allocations excessives et
consommations/transferts supérieurs au reçu. Pour les masses exportées avec six
décimales, la tolérance cumulée est bornée par le nombre de termes arrondis ;
elle n'est pas appliquée aux unités physiques entières.

Les tests couvrent un lot fabricant livré en plusieurs fois, plusieurs origines
dans une réception, les fractionnements, les mélanges, les contenants, les
branches sans lien et l'absence de modification du registre par l'exploration.
Le navigateur compare le périmètre affiché à une traversée indépendante des CSV.
Les preuves de cette livraison sont dans `artifacts/testing/materials_20260919`.

```powershell
python -m pytest -c pytest-reference.ini -o addopts= etudecas/tests/lots/test_lot_trace_procurement.py etudecas/tests/lots/test_lot_trace_payload.py etudecas/tests/lots/test_lot_trace_view_model.py etudecas/simulation/logistics -q
python -m etudecas.visualization.maps.material_delivery --help
python -m etudecas.testing.historical_browser material --help
```

`material_delivery` permet d'ajouter la vue à une carte existante, dans un nouveau
fichier. Il vérifie d'abord la concordance des identifiants, dates, quantités et
liens entre la carte et les CSV, puis enregistre les empreintes de provenance.
Il ne rejoue pas le moteur et ne remplace pas la qualification par navigateur.
