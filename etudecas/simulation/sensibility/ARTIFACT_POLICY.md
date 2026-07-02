# Sensibility Artifact Policy

The sensitivity runners should not keep complete simulation outputs for every
case by default. Full case outputs are useful for debugging, but they make the
workspace too large for normal development.

## Retention modes

- `summary`: default. Keep case inputs, summaries, reports and small diagnostic
  CSVs only.
- `compact`: keep summaries/reports plus selected operational CSVs needed for
  quick inspection. Do not keep `mrp_trace_daily.csv` by default.
- `full`: keep the entire `simulation_output` directory. Use only for a small
  number of cases being debugged.

## Existing heavy outputs

Inventory dry-run:

```powershell
python etudecas\simulation\sensibility\cleanup_sensibility_outputs.py
```

Archive a small batch first:

```powershell
python etudecas\simulation\sensibility\cleanup_sensibility_outputs.py --execute --limit 10
```

Archive all non-kept `simulation_output` directories:

```powershell
python etudecas\simulation\sensibility\cleanup_sensibility_outputs.py --execute
```

Delete all non-kept `simulation_output` directories when the study is
reproducible from scripts and compact summaries are enough:

```powershell
python etudecas\simulation\sensibility\cleanup_sensibility_outputs.py --delete --execute
```

Keep paths containing a token:

```powershell
python etudecas\simulation\sensibility\cleanup_sensibility_outputs.py --keep baseline --keep selected_case --execute
```

The script writes:

- `sensibility_artifact_manifest.csv`
- `sensibility_artifact_manifest.json`

It moves outputs to `etudecas/simulation/sensibility_archives` by default. Use
`--archive-root` to place the archive outside the repository. With `--delete`,
it removes only discovered `simulation_output` directories and keeps the root
summaries, reports, case registry CSVs and input files.
