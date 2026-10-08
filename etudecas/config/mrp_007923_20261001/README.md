# Point de reprise : extension validée à 007923

La variante retenue est **`shared`**. Elle part du point de reprise
`mrp_shared_stock_20261001` et ajoute à 007923/Avène la protection continue
des 15 jours ouvrés de sécurité source et le rapprochement hebdomadaire avec
le total industriel I. Fournisseur, prix, standard, délai et consommation
physique estimée restent inchangés. Le moteur n'a pas été modifié pour ces essais.

Sur les 52 photos de 2025, l'écart moyen absolu de 007923 diminue de
25 755,51 à 12 180,32 kg. Les 36 jours sans stock disponible disparaissent,
sans dégrader le service client sur cinq ans. Le stock du 29 décembre atteint
26 959,80 kg contre 39 901,71 kg source : l'écart n'est pas entièrement résolu.

Les variantes `lead` et `combined`, alignant le délai de 001893 sur le
fournisseur exécuté, sont **écartées** : leur amélioration au premier trimestre
ne compense pas la dégradation annuelle et du service. La variante `full`,
ajoutant les règles complètes sur 001893, est **un dépistage de 365 jours écarté**,
pas un calcul de cinq ans. Le saut initial 001893 reste à résoudre ; le besoin
net corrigé dépasse encore deux standards et déclenche 71 760 kg. Les engagements
initiaux manquants à Avène restent une piste, sans réaffectation arbitraire
des commandes de la division 1820 ni assimilation de prévisions à des réceptions.

`checkpoint.zip` conserve les cinq graphes réellement exécutés, les arguments
du moteur, les paramètres de présentation et les preuves compactes. Il ne
contient ni les CSV ni les HTML volumineux. Les jours de sécurité source,
les deux suivis de lots et les anciennes références sont conservés.

## Recalcul et comparaison

Depuis la racine du dépôt, avec les dépendances Python du projet installées,
ce bloc crée un dossier neuf, vérifie les vraies entrées archivées, relance
les simulations puis produit une comparaison HTML. Il ne remplace aucun résultat.
Il faut prévoir une durée significative : quatre calculs de 1 825 jours
(référence comprise) et un de 365 jours pour reproduire toutes les courbes.
Pour recalculer uniquement la version retenue, remplacer `keys = ...` par
`keys = ['shared']` ; la comparaison perd alors son témoin.

```powershell
@'
from pathlib import Path
import hashlib, json, subprocess, sys, uuid, zipfile
from etudecas.visualization.maps.source_comparison import build_comparison_payload
from etudecas.visualization.maps.portable_diagnostic import comparison_document
root = Path.cwd()
work = root / 'etudecas/artifacts/testing' / ('reprise_007923_' + uuid.uuid4().hex)
work.mkdir(parents=True, exist_ok=False)
with zipfile.ZipFile(root / 'etudecas/config/mrp_007923_20261001/checkpoint.zip') as bundle:
    manifest = json.loads(bundle.read('manifest.json'))
    for name, info in manifest['members'].items():
        content = bundle.read(name)
        assert hashlib.sha256(content).hexdigest() == info['sha256'], name
        destination = (work / name).resolve()
        assert destination.is_relative_to(work.resolve()), name
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open('xb') as stream:
            stream.write(content)
for source, expected in manifest['source_workbooks'].items():
    assert hashlib.sha256(Path(source).read_bytes()).hexdigest() == expected, source
keys = list(manifest['variants'])
for key in keys:
    args = list(manifest['variants'][key]['python_args'])
    for flag in ('--input', '--output-dir'):
        index = args.index(flag) + 1
        args[index] = str(work / args[index])
    subprocess.run([sys.executable, *args], cwd=root, check=True)
source = root / 'etudecas/data/source'
payload = build_comparison_payload(
    source / 'Flow_Data_Inventory_and_Replenishment_rules.xlsx',
    source / 'Flow_Data_MRP_results.xlsx',
    {key: work / 'runs' / key for key in keys})
metadata = json.loads((work / 'comparison_metadata.json').read_text(encoding='utf-8'))
for key, presentation in metadata.pop('runs').items():
    if key in payload['runs']:
        payload['runs'][key].update(presentation)
metadata['default_runs'] = [key for key in metadata['default_runs'] if key in keys]
payload.update(metadata)
with (work / 'comparaison_mrp.html').open('x', encoding='utf-8') as stream:
    stream.write(comparison_document(payload))
print(work / 'comparaison_mrp.html')
'@ | python -B -
```

Les commandes et graphes correspondent aux exécutions vérifiées ; cette recette
portable n'a pas déclenché une seconde campagne identique après archivage.
Elle reconstruit la comparaison depuis les nouveaux CSV et les Excel suivis
par Git. Les autres panneaux et les deux suivis de lots de la carte complète
locale restent historiques et relèvent de leurs recettes antérieures.

Documentation métier : [règles MRP](../../data/reports/mrp_source_rules.md).
Preuves locales et décision :
`etudecas/artifacts/testing/mrp_offer_alignment_20261001/manifest.json`.
Les contrôles techniques ne certifient pas la calibration de toutes les matières.
