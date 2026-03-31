from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a short-path alias for an existing sensitivity output.")
    parser.add_argument("--source", required=True, help="Existing sensitivity output directory.")
    parser.add_argument("--dest", required=True, help="Short alias directory to create/update.")
    return parser.parse_args()


def ensure_cases_junction(source: Path, dest: Path) -> None:
    source_cases = source / "cases"
    dest_cases = dest / "cases"
    if not source_cases.is_dir():
        raise FileNotFoundError(f"Missing source cases directory: {source_cases}")
    if dest_cases.exists():
        if dest_cases.is_dir() and not any(dest_cases.iterdir()):
            dest_cases.rmdir()
        else:
            return
    result = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            "New-Item",
            "-ItemType",
            "Junction",
            "-Path",
            str(dest_cases),
            "-Target",
            str(source_cases),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0 and not dest_cases.exists():
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "Failed to create cases junction")


def rewrite_text(text: str, source: Path, dest: Path) -> str:
    replacements = [
        (str(source.resolve()), str(dest.resolve())),
        (str(source).replace("/", "\\"), str(dest).replace("/", "\\")),
        (str(source).replace("\\", "/"), str(dest).replace("\\", "/")),
    ]
    out = text
    for old, new in replacements:
        out = out.replace(old, new)
    return out


def main() -> int:
    args = parse_args()
    source = Path(args.source)
    dest = Path(args.dest)
    if not source.is_dir():
        raise FileNotFoundError(f"Missing source directory: {source}")
    dest.mkdir(parents=True, exist_ok=True)
    ensure_cases_junction(source, dest)

    for item in source.iterdir():
        if item.name == "cases":
            continue
        target = dest / item.name
        if item.is_dir():
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(item, target)
            continue
        try:
            text = item.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            shutil.copy2(item, target)
            continue
        target.write_text(rewrite_text(text, source, dest), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
