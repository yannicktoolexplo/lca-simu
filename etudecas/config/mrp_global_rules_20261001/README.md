# Essais globaux des règles MRP

Ce point de reprise conserve la référence 007923 et deux essais distincts :

- `nominal` : dernière référence retenue, avec six protections continues et quatre rapprochements du total industriel ;
- `total` : rapprochement des besoins industriels renseignés pour les 22 achats externes ;
- `safety` : même rapprochement, avec protection continue sur 20 achats. 001848 conserve principal/secours et 021081 ses fournisseurs multiples.

Il s'agit d'essais comparatifs, pas d'une promotion automatique dans le nominal.
Les semaines absentes restent inconnues. Les jours et quantités de sécurité
source, les stocks initiaux et les consommations physiques complémentaires
restent conservés. La sélection explicite de 001893 aligne aussi son délai de
planification : son effet n'est pas uniquement celui de la sécurité. Les offres
fixées à celles utilisées dans la référence ne constituent pas une politique
universelle sous incident fournisseur.

Le moteur reste inchangé. `checkpoint.zip` contient les trois graphes exacts,
les commandes, les empreintes des sources et les preuves compactes. Aucun CSV
ni HTML volumineux n'y est conservé. Les résultats et décisions sont décrits
dans la [documentation métier](../../data/reports/mrp_source_rules.md).

## Reproduire la comparaison et sa carte

Depuis la racine du dépôt, avec les dépendances du projet, le bloc suivant
recalcule trois simulations de 1 825 jours dans un dossier neuf. Il peut prendre
un temps important. Il vérifie les véritables entrées archivées, sans test
d'altération de fichiers. La recette portable n'a pas été exécutée une seconde
fois après l'archivage ; ses commandes sont celles des calculs vérifiés.

```powershell
@'
from pathlib import Path
import hashlib, importlib.util, json, subprocess, sys, uuid, zipfile
from etudecas.visualization.maps.source_comparison import build_comparison_payload
from etudecas.visualization.maps.portable_diagnostic import (
    comparison_document, strip_comparison, packed, COMPARISON_RUNTIME,
    COMPARISON_START, COMPARISON_END,
)
root=Path.cwd()
work=root/'etudecas/artifacts/testing'/('reprise_global_'+uuid.uuid4().hex)
work.mkdir(parents=True,exist_ok=False)
with zipfile.ZipFile(root/'etudecas/config/mrp_global_rules_20261001/checkpoint.zip') as bundle:
    manifest=json.loads(bundle.read('manifest.json'))
    for name,info in manifest['members'].items():
        content=bundle.read(name)
        assert hashlib.sha256(content).hexdigest()==info['sha256'],name
        destination=(work/name).resolve()
        assert destination.is_relative_to(work.resolve()),name
        destination.parent.mkdir(parents=True,exist_ok=True)
        with destination.open('xb') as stream:stream.write(content)
for name,expected in manifest['source_workbooks'].items():
    assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==expected,name
for name,expected in manifest['code_at_prepare'].items():
    assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==expected,name
for key,variant in manifest['variants'].items():
    args=list(variant['python_args'])
    for flag in ('--input','--output-dir'):
        index=args.index(flag)+1
        args[index]=str(work/args[index])
    subprocess.run([sys.executable,*args],cwd=root,check=True)
source=root/'etudecas/data/source'
payload=build_comparison_payload(
    source/'Flow_Data_Inventory_and_Replenishment_rules.xlsx',
    source/'Flow_Data_MRP_results.xlsx',
    {key:work/'runs'/key for key in manifest['variants']})
metadata=json.loads((work/'comparison_metadata.json').read_text(encoding='utf-8'))
for key,presentation in metadata.pop('runs').items():payload['runs'][key].update(presentation)
payload.update(metadata)
spec=importlib.util.spec_from_file_location('global_view',work/'deliver.py')
view=importlib.util.module_from_spec(spec)
spec.loader.exec_module(view)
document=comparison_document(payload).replace('</h1>','</h1>'+view.overview(payload,view.metrics_for(payload)),1)
standalone=work/'comparaison_mrp.html'
with standalone.open('x',encoding='utf-8') as stream:stream.write(document)
base=root/'etudecas/resultats/regroupement_001757_20260929/carte_mrp_001893_007923.html'
if base.exists():
    original=strip_comparison(base.read_text(encoding='utf-8'))
    runtime=COMPARISON_RUNTIME.replace('__ENTRY__',json.dumps(packed(document.encode('utf-8'),standalone.name,'text/html')))
    head,closing,tail=original.rpartition('</html>')
    assert closing
    with (work/'carte_mrp.html').open('x',encoding='utf-8') as stream:
        stream.write(head+COMPARISON_START+runtime+COMPARISON_END+closing+tail)
print(standalone)
'@ | python -B -
```

La comparaison est recalculée depuis les nouveaux CSV et les Excel suivis.
La carte complète réutilise les autres panneaux et les deux suivis de lots
historiques du fichier de base, s'il est présent ; ils ne représentent pas les
nouveaux essais. Si ce fichier a été retiré, sa reconstruction relève du point
de reprise antérieur. Les trois courbes et le tableau cliquable restent
reconstructibles avec cette seule archive et les sources du dépôt.

Preuves locales : `etudecas/artifacts/testing/mrp_global_rules_20261001/manifest.json`.
Les vérifications techniques ne certifient pas une identité avec l'ERP industriel.
