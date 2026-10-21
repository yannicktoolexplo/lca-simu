"""Relance la reference MRP sur cinq ans puis ses sensibilites deterministes.

Le script ne démarre aucun calcul sans confirmation interactive, sauf avec
--yes. Chaque exécution utilise un nouveau dossier et conserve les résultats
partiels en cas d'échec pour diagnostic.
"""
from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DAYS = 1825
# When this file is executed by path, Python puts `etudecas/` (not the repo
# root) on sys.path. The child commands use cwd=ROOT, but in-process helpers
# such as oat_case_count also need the package import path here.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS,
                        help="Horizon de simulation en jours (défaut : 1825, cinq ans).")
    parser.add_argument("--output-root", type=Path,
                        help="Dossier de sortie neuf. Par défaut : etudecas/resultats/reprise_5ans_<date>.")
    parser.add_argument("--sensitivities", choices=("both", "oat", "realistic"), default="both",
                        help="Sensibilites apres le nominal : OAT, realiste ou les deux.")
    parser.add_argument("--no-map", action="store_true",
                        help="Ne pas construire la carte HTML complete du nominal.")
    parser.add_argument("--yes", action="store_true",
                        help="Ignorer la confirmation interactive (plusieurs calculs de cinq ans).")
    parser.add_argument("--plan-only", action="store_true",
                        help="Afficher le plan sans creer de dossier ni lancer de calcul.")
    return parser.parse_args()


def command_for(args: argparse.Namespace, output: Path) -> list[list[str]]:
    py = [sys.executable, "-B"]
    nominal = py + ["-m", "etudecas.regenerate", "--days", str(args.days),
                    "--output-dir", str(output / "nominal")]
    if not args.no_map:
        nominal.append("--with-map")
    graph = output / "nominal" / "input_graph.json"
    run_manifest = output / "nominal" / "run_manifest.json"
    commands = [nominal]
    if args.sensitivities in {"both", "oat"}:
        commands.append(py + ["-m", "etudecas.simulation.sensibility.run_sensitivity_analysis",
            "--input", str(graph), "--scenario-id", "scn:BASE", "--days", str(args.days),
            "--run-manifest", str(run_manifest),
            "--output-dir", str(output / "sensibilites" / "oat"), "--artifact-mode", "compact"])
    if args.sensitivities in {"both", "realistic"}:
        commands.append(py + ["-m", "etudecas.simulation.sensibility.run_realistic_sensitivity_study",
            "--input", str(graph), "--scenario-id", "scn:BASE", "--days", str(args.days),
            "--run-manifest", str(run_manifest),
            "--output-dir", str(output / "sensibilites" / "realiste"), "--artifact-mode", "compact"])
    return commands


def oat_case_count(graph_path: Path) -> int:
    """Count the OAT design in memory; this does not run a simulation or write files."""
    from etudecas.simulation.analysis_batch_common import load_json
    from etudecas.simulation.sensibility.run_sensitivity_analysis import build_design

    graph = load_json(graph_path)
    return len(build_design(graph, "scn:BASE", 0.2, "balanced"))


def main() -> int:
    args = parse_args()
    if args.days < 1:
        print("--days doit etre positif.", file=sys.stderr)
        return 2
    if args.output_root is None:
        output = ROOT / "etudecas" / "resultats" / f"reprise_5ans_{datetime.now():%Y%m%d_%H%M%S}"
    elif args.output_root.is_absolute():
        output = args.output_root.resolve()
    else:
        output = (ROOT / args.output_root).resolve()
    try:
        output.relative_to(ROOT)
    except ValueError:
        print(f"Le dossier de sortie doit rester dans le depot : {output}", file=sys.stderr)
        return 2
    if output.exists():
        print(f"Le dossier existe deja ; aucun fichier ne sera ecrase : {output}", file=sys.stderr)
        return 2
    commands = command_for(args, output)
    print(f"Sorties : {output}")
    print(f"Horizon : {args.days} jours ({args.days / 365:.2f} ans)")
    print("Etapes : nominal courant" + (" + carte HTML complete" if not args.no_map else "") +
          (" ; sensibilite OAT" if args.sensitivities in {"both", "oat"} else "") +
          (" ; sensibilite realiste locale et stress" if args.sensitivities in {"both", "realistic"} else ""))
    print("Les sensibilites utilisent input_graph.json produit par le nominal courant.")
    if args.plan_only:
        for index, command in enumerate(commands, start=1):
            print(f"[{index}] {' '.join(command)}")
        return 0
    if not args.yes:
        answer = input("Lancer le nominal cinq ans ? Tape OUI : ")
        if answer.strip() != "OUI":
            print("Annule ; aucun dossier ni calcul cree.")
            return 0
    output.mkdir(parents=True, exist_ok=False)
    for index, command in enumerate(commands, start=1):
        print(f"\n[{index}/{len(commands)}] {' '.join(command)}", flush=True)
        result = subprocess.run(command, cwd=ROOT, check=False)
        if result.returncode:
            print(f"Etape en echec (code {result.returncode}). Les sorties existantes sont conservees dans {output}.",
                  file=sys.stderr)
            return result.returncode
        if index == 1 and not (output / "nominal" / "input_graph.json").is_file():
            print("Le nominal n'a pas produit input_graph.json ; les sensibilites ne peuvent pas demarrer.",
                  file=sys.stderr)
            return 1
        if index == 1 and len(commands) > 1 and not args.yes:
            graph = output / "nominal" / "input_graph.json"
            if args.sensitivities in {"both", "oat"}:
                print(f"Sensibilite OAT : {oat_case_count(graph)} cas de {args.days} jours.")
            if args.sensitivities in {"both", "realistic"}:
                print("Sensibilite realiste : reference + repetition, puis tests locaux et stress sur jusqu'a 8 fournisseurs actifs.")
            answer = input("Lancer maintenant les sensibilites cinq ans ? Tape OUI : ")
            if answer.strip() != "OUI":
                print(f"Sensibilites annulees. Le nominal et sa carte restent dans {output}.")
                return 0
    print(f"\nTermine. Resultats : {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
