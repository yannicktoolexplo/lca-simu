# Pilote de simulation des risques dépendants de l’état

Essais du 4 novembre 2026 sur `dev_yannick`, révision
[`e33539d`](https://github.com/yannicktoolexplo/lca-simu/commit/e33539dcb4ccc8f95329be933d1ac1ce570b2108).
Le pilote vérifie la génération d’un événement, son application aux flux,
l’équivalence d’un rejeu figé et l’effet d’une variation de stock. Les résultats
ci-dessous sont agrégés. Les données, identifiants, coûts et journaux
transactionnels restent dans les dossiers locaux d’essai.

## Référence MRP datée et configuration historique

| Parcours | Résultat |
|---|---|
| Référence MRP courante, 14 jours, `audit_only` | Rejeu nominal exécuté. Le manifeste confirme l’intégrité du code et des entrées pendant le calcul. |
| Même référence, 60 jours, même graphe préparé et famille `lead` | Le bras sans effet de risque s’exécute via le lanceur de sensibilité. La qualification indépendante de cette sortie relève une disponibilité de transfert interne orpheline et deux contrôles du mode de réconciliation en échec. |
| Même référence avec effets de risque activés | Arrêt à l’initialisation par le garde du moteur `Dated opening purchase execution is currently qualified only for BASE without risk overlays`. La configuration avec un calendrier de risques est soumise au même garde. |
| Configuration de risque historique, 120 jours | Neuf bras distincts exécutés et contrôlés avec la qualification CSV indépendante du dépôt. Configuration expérimentale séparée de la référence MRP datée. |

Le garde se trouve dans le bloc d’initialisation des achats ouverts dans
[run_first_simulation.py](../simulation/engine/run_first_simulation.py).
La commande de préparation et le lanceur sont
[current_reference.py](../simulation/current_reference.py) et
[current_reference_sensitivity_runner.py](../simulation/current_reference_sensitivity_runner.py).
La reproduction de l’expérience sur la référence datée dépend de la qualification
de la coexistence des achats ouverts datés et des effets de risque.

## Résultat des 120 jours

Le pilote réutilise un graphe et un profil archivés, le premier tirage consigné
et un retard imposé sur une liaison. Horizon de 120 jours, graine 2028516550,
temps de transport déterministes, famille `lead`, délai d’observation de
30 jours et amorçage physique de 0 jour. Le choc archivé ajoute 35 jours sur
sa fenêtre J0–J89. Les seuils, la durée et le périmètre sont des hypothèses
de simulation.

| Calendrier | Stock de référence | Stock d’ouverture du composant exposé × 1,25 |
|---|---|---|
| Aucun événement imposé, règle désactivée | Témoin | Témoin de la sensibilité stock |
| Aucun événement imposé, règle active | Un événement généré à J30 | Hors du plan de ce pilote |
| Premier retard seul | Aucun événement endogène | Aucun événement endogène |
| Premier retard et rejeu figé de l’événement supplémentaire | Même séquence physique que le bras dynamique correspondant | Même séquence physique que le bras dynamique correspondant |
| Premier retard et règle recalculée | Un événement généré à J30 | Le même événement est généré à J30 |

- L’événement généré dans les trois bras dynamiques concerne la même liaison,
  distincte de celle du choc imposé. Il est actif de J31 à J44. Le signal
  `factory_input_shortage_next_receipt_late` emploie la valeur sentinelle
  365 en l’absence de réception attendue, avec un seuil de 35 dans ce cas.
  La valeur 365 représente donc une réception inconnue du modèle.
- Pour les 17 expéditions portant l’identifiant de cet événement dans le bras
  « premier retard et règle recalculée », l’appariement avec le bras
  « premier retard seul » retrouve 17 correspondances uniques et +2 jours
  sur chaque arrivée réalisée dans la simulation.
- Le fichier de service journalier est identique dans les neuf bras.
  Pour les paires figé/dynamique, les expéditions comparées hors métadonnées
  causales, les réceptions, les campagnes de production et le service
  coïncident, avec comme sans variation du stock.
- Ce cas vérifie une propagation simulée jusqu’à des réceptions et donne un
  résultat nul sur le service et sur l’occurrence de l’événement sous la
  sensibilité stock. Le premier retard imposé et l’événement endogène
  coexistent. Le contraste avec le bras sans retard imposé laisse le lien
  causal entre eux indéterminé.
- L’ajustement par `--measurement-start-stock-scale-csv` exécuté séparément
  échoue à la qualification des lots, notamment sur le type d’événement et
  le bilan du registre. La variante retenue utilise
  `--opening-observed-stock-scale-csv`. Le stock du couple ciblé augmente
  effectivement, avec arrondi dans son unité physique. Cette variation
  suppose un stock disponible à l’ouverture. La valorisation d’un achat,
  d’un transfert ou d’une réserve prépositionnée reste à établir.

## Rejouer le pilote

Exécuter le bloc Python ci-dessous depuis la racine d’un checkout de la
révision testée, par exemple en le plaçant dans un script temporaire et en
lançant `python -B chemin_du_script.py`. Les deux archives sont vérifiées
contre leurs manifestes. Chaque calcul écrit ses propres sorties. Le coût
de la réserve et la probabilité d’un choc restent des entrées à documenter
pour une analyse économique.

```python
import csv
import hashlib
import io
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zipfile import ZipFile

commit = "e33539dcb4ccc8f95329be933d1ac1ce570b2108"
assert subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip() == commit
archive_dir = Path("etudecas/config/reproduction_historique")
work = Path("etudecas/artifacts/testing") / datetime.now().strftime("article_cascade_%Y%m%d_%H%M%S")
inputs = work / "inputs"
inputs.mkdir(parents=True, exist_ok=False)

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def read_csv(path):
    with path.open(newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))

def write_csv(path, fields, rows):
    with path.open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

supplier_archive = archive_dir / "supplier_inputs.zip"
campaign_archive = archive_dir / "inputs_sources_01_03.zip"
supplier_manifest = json.loads((archive_dir / "supplier_manifest.json").read_text(encoding="utf-8"))
campaign_manifest = json.loads((archive_dir / "manifest.json").read_text(encoding="utf-8"))
assert digest(supplier_archive) == supplier_manifest["archive"]["sha256"]
assert digest(campaign_archive) == campaign_manifest["archive_sha256"]

graph_path, profile_path, primary_path = (inputs / name for name in (
    "graph.json", "profile.json", "primary_delay.csv",
))
with ZipFile(supplier_archive) as archive:
    graph_path.write_bytes(archive.read("graphs/op100_source.json"))
    profile_path.write_bytes(archive.read("protocol/engine_profile.json"))
with ZipFile(campaign_archive) as archive:
    member, = [name for name in archive.namelist()
               if name.startswith("01/cascades/prepared_inputs/lead_time_delay_")
               and name.endswith("/supplier_risk_events.csv")]
    primary_path.write_bytes(archive.read(member))

profile = json.loads(profile_path.read_text(encoding="utf-8"))
seed = str(supplier_manifest["method"]["common_seed_blocks"][0])
primary, = read_csv(primary_path)
common = [
    sys.executable, "-B", "-m", "etudecas.simulation.engine.run_first_simulation",
    "--input", str(graph_path), "--scenario-id", "scn:BASE", "--days", "120",
    "--seed", seed, "--mrp-execution-mode", "historical", "--warmup-days", "0",
    "--no-stochastic-lead-times", "--common-random-numbers",
    "--supplier-state-risk-observation-warmup-days", "30",
    "--supplier-state-risk-families", "lead", "--output-profile", "full",
    "--skip-map", "--skip-plots", "--lot-trace", *profile["args"],
]
runs = []

def run(name, state=False, calendar=None, buffer=None):
    result = work / name
    command = [*common, "--output-dir", str(result)]
    command.append("--supplier-state-dependent-risks" if state
                   else "--no-supplier-state-dependent-risks")
    if calendar is not None:
        command += ["--supplier-risk-events-csv", str(calendar)]
    if buffer is not None:
        command += ["--opening-observed-stock-scale-csv", str(buffer)]
    with (work / f"{name}.log").open("x", encoding="utf-8") as log:
        subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=230)
    runs.append({"name": name, "output": str(result), "command": command})
    return result / "data"

tracked = (supplier_archive, campaign_archive, graph_path, profile_path, primary_path)
before = {str(path): digest(path) for path in tracked}
run("reference")
state = run("state_only", state=True)
initial = run("primary_only", calendar=primary_path)
dynamic = run("primary_and_state", state=True, calendar=primary_path)
events = "supplier_state_dependent_risk_events.csv"
second, = read_csv(dynamic / events)
assert read_csv(state / events) == [second]
assert int(second["start_day"]) == int(second["trigger_day"]) + 1

frozen_path = inputs / "frozen_events.csv"
write_csv(frozen_path, [
    "event_id", "causal_root_id", "risk_type", "supplier_id", "item_id",
    "dst_node_id", "edge_id", "start_day", "end_day", "multiplier", "notes",
], [primary, second])
opening, = [row for row in read_csv(initial / "initialization_observed_stock.csv")
            if (row["node_id"], row["item_id"]) == (primary["dst_node_id"], primary["item_id"])]
assert float(opening["opening_stock_qty"]) > 0
buffer_path = inputs / "buffer.csv"
write_csv(buffer_path, ["node_id", "item_id", "scale"], [{
    "node_id": primary["dst_node_id"], "item_id": primary["item_id"], "scale": 1.25,
}])
before.update({str(path): digest(path) for path in (frozen_path, buffer_path, dynamic / events)})
run("frozen_no_buffer", calendar=frozen_path)
run("reference_buffer", buffer=buffer_path)
run("primary_only_buffer", calendar=primary_path, buffer=buffer_path)
run("frozen_buffer", calendar=frozen_path, buffer=buffer_path)
run("dynamic_buffer", state=True, calendar=primary_path, buffer=buffer_path)
assert before == {path: digest(Path(path)) for path in before}

qualification = [
    sys.executable, "-B", "-m", "etudecas.toolbox", "qualify",
    "--task-id", "article-cascade-pilot", "--output", str(work / "proofs"),
]
for result in runs:
    qualification += ["--run", result["output"]]
(work / "runs.json").write_text(json.dumps({
    "commit": commit, "input_hashes": before, "inputs_unchanged": True,
    "runs": runs, "qualification_command": qualification,
}, indent=2) + "\n", encoding="utf-8")
subprocess.run(qualification, check=True, timeout=180)
print(work)
```

## Exploiter les prochaines simulations

1. Figer le commit, la configuration et la fenêtre. Qualifier séparément le
   témoin daté, les achats ouverts sous risque et l’appariement des tirages
   avant toute utilisation avec effets sur cette référence.
2. Préenregistrer l’incident initial et la réponse réalisable. Conserver les
   bras avec et sans choc, le calendrier figé et la règle recalculée. Vérifier
   l’équivalence physique du figé et du dynamique sous la politique de
   référence avant de comparer les réponses.
3. Rapprocher `supplier_state_dependent_risk_events.csv`,
   `supplier_risk_events_applied_daily.csv`,
   `production_supplier_shipments_daily.csv`,
   `production_input_replenishment_arrivals_daily.csv`,
   `lot_causal_links.csv` et `production_demand_service_daily.csv`.
   Identifier séparément le signal, l’application à une transaction, le lien
   avec le premier incident et l’effet client. Conserver les résultats nuls.
4. Pour l’article, vérifier sur un cas anonymisé le signal effectivement
   connu, la décision et l’expédition déplacée. Un effet issu des règles
   programmées relève de la simulation. La validation du mécanisme demande
   des traces indépendantes, notamment des épisodes comparables sans incident.
   Estimer la valeur de l’action sur un périmètre économique explicite avec
   coûts documentés et sensibilité aux fréquences de choc.

Voir aussi la [référence MRP](MRP_REFERENCE_20261014.md), les
[critères de vérification](TEST_VALIDATION.md) et le
[guide scientifique](DEVELOPPEMENT_SCIENTIFIQUE.md).
