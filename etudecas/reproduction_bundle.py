"""Capture current calculation sources and inputs, without generated results.

An archive verifies file identity, not industrial calibration or reproducibility
of a numerical result. Dependencies are recorded, never installed automatically.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path, PurePosixPath
import platform
import stat
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = "reproduction-bundle.json"
SCHEMA = "etudecas.reproduction_bundle.v1"
EXCLUDED = {"result", "results", "resultats", "artifacts", "docs", "documentation", "archive",
            "archives", "__pycache__", ".git", ".venv", ".pytest_cache",
            "reproduction_historique", "node_modules"}
SOURCE_SUFFIXES = {".py", ".js", ".css", ".html", ".ps1", ".json", ".toml", ".yaml", ".yml", ".txt"}
MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 512 * 1024 * 1024


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _name(value: str) -> str:
    """Use the same unambiguous member names on Windows and POSIX."""
    path = PurePosixPath(value)
    reserved = {"CON", "PRN", "AUX", "NUL"} | {
        f"{prefix}{i}" for prefix in ("COM", "LPT") for i in range(1, 10)}
    if (not value or any(c in value for c in '\\:*?"<>|') or any(ord(c) < 32 for c in value) or path.is_absolute()
            or value != path.as_posix() or any(part in {".", ".."} for part in path.parts)
            or any(part.rstrip(" .") != part or part.split(".")[0].upper() in reserved
                   for part in path.parts)):
        raise ValueError(f"Unsafe archive path: {value!r}")
    return value


def _no_links(path: Path) -> None:
    for item in (path, *path.parents):
        if item.exists() or item.is_symlink():
            info = item.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
                raise ValueError(f"Symlink/reparse path is forbidden: {item}")


def _local(path: Path, root: Path) -> Path:
    _no_links(path)
    resolved = path.resolve()
    if not resolved.is_relative_to(root):
        raise ValueError(f"Input outside the source workspace: {path}")
    return resolved


def _source_name(name: str) -> bool:
    path = PurePosixPath(name)
    # Excel's transient owner/lock marker is not a workbook input. Opening or
    # closing a source workbook must not change the reproducible source set.
    if path.name.startswith("~$") and path.suffix.lower() in {".xlsx", ".xlsm", ".xls"}:
        return False
    if any(part in EXCLUDED for part in path.parts):
        return False
    if not name.startswith("etudecas/"):
        return (path.name.startswith("requirements") and path.suffix == ".txt") or name == "pyproject.toml"
    return (path.suffix.lower() in SOURCE_SUFFIXES or name.startswith("etudecas/data/source/")
            or (name.startswith("etudecas/config/") and path.suffix.lower() == ".csv"))


def _inventory(root: Path) -> tuple[set[str], str]:
    if (root / ".git").exists():
        result = subprocess.run(["git", "ls-files", "-z", "-co", "--exclude-standard", "--",
                                 "etudecas", "requirements*.txt", "pyproject.toml"],
                                cwd=root, check=True, capture_output=True)
        names = set(result.stdout.decode("utf-8").split("\0")) - {""}
        origin = "git-visible working files; bytes read from filesystem"
    else:
        manifest_path = root / MANIFEST
        if not manifest_path.is_file():
            raise ValueError("No .git or extracted reproduction-bundle.json inventory")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("schema") != SCHEMA:
            raise ValueError("Unsupported fallback inventory schema")
        names = {_name(row["path"]) for row in manifest["files"]}
        # Include new source files added after extraction, within the same scope.
        for base, dirs, files in os.walk(root / "etudecas", followlinks=False):
            dirs[:] = [d for d in dirs if d not in EXCLUDED]
            for name in files:
                names.add((Path(base) / name).relative_to(root).as_posix())
        origin = "extracted manifest plus bounded current source discovery; no Git used"
    names = {name for name in names if _source_name(name)}
    # These ignored files are runtime inputs, not simulation output directories.
    for folder in ("etudecas/data/source", "etudecas/config", "etudecas/visualization/maps/vendor"):
        base_path = root / folder
        for base, dirs, files in os.walk(base_path, followlinks=False):
            dirs[:] = [d for d in dirs if d not in EXCLUDED]
            for filename in files:
                path = Path(base) / filename
                relative = path.relative_to(root).as_posix()
                if path.suffix.lower() not in {".zip", ".pyc"} and _source_name(relative):
                    names.add(relative)
    return names, origin


def capture(output_zip: Path, commands: list[list[str]], *, root: Path = ROOT) -> dict:
    _no_links(root)
    root = root.resolve()
    output_zip = Path(output_zip)
    if output_zip.exists():
        raise FileExistsError(output_zip)
    _no_links(output_zip)
    if not commands or any(not command or not all(isinstance(v, str) for v in command) for command in commands):
        raise ValueError("At least one explicit argv command is required")
    if any(value.startswith("--") and "=" in value for command in commands for value in command[1:]):
        raise ValueError("Pass each option and its value as separate argv entries; --option=value is unsupported")
    names, origin = _inventory(root)
    initial_inventory = {name for name in names if (root / name).is_file()}
    portable_commands = []
    explicit_inputs = set()
    for index, command in enumerate(commands):
        portable = ["${PYTHON}"]
        for i, value in enumerate(command[1:], start=1):
            previous = command[i - 1]
            if previous == "--output-dir":
                portable.append(f"${{RUN_OUTPUT_{index}}}")
                continue
            candidate = Path(value)
            candidate = candidate if candidate.is_absolute() else root / candidate
            if candidate.is_file():
                path = _local(candidate, root)
                name = path.relative_to(root).as_posix()
                # Explicit graph/config files can be ignored or under result/.
                if path.suffix.lower() not in {".json", ".csv", ".xlsx", ".py", ".toml", ".yaml", ".yml"}:
                    raise ValueError(f"Unsupported explicit calculation input: {path}")
                names.add(name)
                explicit_inputs.add(name)
                portable.append("${ROOT}/" + name)
            elif previous.startswith("--") and (previous == "--input" or previous.endswith(("-csv", "-json"))):
                if value:
                    raise FileNotFoundError(f"Missing command input {previous}: {value}")
                portable.append(value)
            elif Path(value).is_absolute():
                raise ValueError(f"Unresolved absolute command argument: {value}")
            else:
                portable.append(value)
        portable_commands.append(portable)
    files = []
    blobs = {}
    for name in sorted(names):
        _name(name)
        path = root / name
        if not path.is_file():
            if name in explicit_inputs:
                raise FileNotFoundError(path)
            continue
        path = _local(path, root)
        data = path.read_bytes()
        if len(data) > MAX_FILE_BYTES:
            raise ValueError(f"File too large for a source bundle: {name}")
        blobs[name] = data
        files.append({"path": name, "bytes": len(data), "sha256": _sha(data),
                      "explicit_command_input": name in explicit_inputs})
    if sum(map(len, blobs.values())) > MAX_TOTAL_BYTES:
        raise ValueError("Source bundle exceeds its total size limit")
    environment = {"python": sys.version, "platform": platform.platform(),
                   "packages": sorted({(d.metadata.get("Name", "unknown"), d.version)
                                       for d in importlib.metadata.distributions()})}
    manifest = {"schema": SCHEMA, "inventory_origin": origin, "files": files,
                "commands": portable_commands, "original_commands": commands,
                "environment": environment, "simulation_executed": False,
                "historical_qualification_transferred": False,
                "scope": "Current filesystem sources and explicit inputs. No calibration certification."}
    output_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_zip, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in blobs.items():
            archive.writestr(name, data)
        archive.writestr(MANIFEST, json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"))
    # Refuse a capture whose source changed during the archive operation.
    try:
        for row in files:
            _no_links(root / row["path"])
            if _sha((root / row["path"]).read_bytes()) != row["sha256"]:
                raise ValueError(f"Source changed during capture: {row['path']}")
        current_names, _ = _inventory(root)
        if {name for name in current_names if (root / name).is_file()} != initial_inventory:
            raise ValueError("Source inventory changed during capture")
    except Exception:
        # This exact file was created exclusively by this call. Do not leave a
        # structurally valid archive after a refused, concurrently changing capture.
        output_zip.unlink()
        raise
    return verify(output_zip)


def _validated(archive: zipfile.ZipFile) -> dict:
    names = []
    total = 0
    for entry in archive.infolist():
        name = _name(entry.filename)
        if entry.is_dir() or stat.S_ISLNK(entry.external_attr >> 16):
            raise ValueError(f"Only regular file members are accepted: {name}")
        if entry.file_size > MAX_FILE_BYTES:
            raise ValueError(f"Oversized archive member: {name}")
        total += entry.file_size
        names.append(name)
    if total > MAX_TOTAL_BYTES or len(names) != len({n.casefold() for n in names}):
        raise ValueError("Oversized archive or ambiguous duplicate paths")
    folded = {name.casefold() for name in names}
    if any(parent.as_posix().casefold() in folded
           for name in names for parent in PurePosixPath(name).parents if parent.as_posix() != "."):
        raise ValueError("An archive file is also used as a directory")
    manifest = json.loads(archive.read(MANIFEST))
    if manifest.get("schema") != SCHEMA:
        raise ValueError("Unsupported bundle schema")
    rows = manifest["files"]
    listed = [_name(row["path"]) for row in rows]
    if len(listed) != len(set(listed)) or set(listed) | {MANIFEST} != set(names):
        raise ValueError("Manifest inventory differs from archive members")
    for row in rows:
        data = archive.read(row["path"])
        if len(data) != row["bytes"] or _sha(data) != row["sha256"]:
            raise ValueError(f"File checksum differs: {row['path']}")
    return manifest


def verify(archive_path: Path) -> dict:
    archive_path = Path(archive_path)
    with zipfile.ZipFile(archive_path) as archive:
        manifest = _validated(archive)
    return {"ok": True, "archive": str(archive_path), "archive_sha256": _sha(archive_path.read_bytes()),
            "files": len(manifest["files"]), "compressed_bytes": archive_path.stat().st_size,
            "uncompressed_bytes": sum(row["bytes"] for row in manifest["files"]),
            "scope": "File identities only; no simulation or environment installation performed."}


def verify_current(archive_path: Path, *, root: Path = ROOT) -> dict:
    """Refuse changed, missing, or newly inventoried sources after a calculation.

    Output directories exempt only newly created files. A file already captured
    in the archive remains protected even if an output argument overlaps it.
    """
    _no_links(root)
    root = root.resolve()
    archive_path = Path(archive_path)
    with zipfile.ZipFile(archive_path) as archive:
        manifest = _validated(archive)
    expected = {row["path"]: row for row in manifest["files"]}
    for name, row in expected.items():
        path = _local(root / name, root)
        if not path.is_file():
            raise ValueError(f"Captured source or input is missing: {name}")
        data = path.read_bytes()
        if len(data) != row["bytes"] or _sha(data) != row["sha256"]:
            raise ValueError(f"Captured source or input changed: {name}")
    output_directories = []
    for command in manifest.get("original_commands", []):
        for index, argument in enumerate(command):
            if argument == "--output-dir":
                if index + 1 >= len(command) or not command[index + 1]:
                    raise ValueError("Missing output directory in archived command")
                output = Path(command[index + 1])
                output = output if output.is_absolute() else root / output
                # Absolute destinations outside this workspace cannot mask any
                # inventoried source; relative ones resolve against this root.
                output_directories.append(Path(os.path.abspath(output)))
    names, _ = _inventory(root)
    added = []
    for name in sorted(names - expected.keys()):
        candidate = root / name
        if any(candidate.is_relative_to(output) for output in output_directories):
            continue
        if candidate.is_file():
            _local(candidate, root)
            added.append(name)
    if added:
        raise ValueError("New runtime/source files since capture: " + ", ".join(added))
    return {"ok": True, "archive": str(archive_path), "root": str(root),
            "archive_sha256": _sha(archive_path.read_bytes()), "files": len(expected),
            "current_sources_verified": True,
            "scope": "Captured sources and inputs unchanged; no additional inventoried runtime files. "
                     "New files under declared output directories excluded; no calibration certification."}


def extract(archive_path: Path, destination: Path, *, workspace: Path = ROOT) -> dict:
    destination = Path(destination).absolute()
    _no_links(destination)
    if not destination.resolve().is_relative_to(workspace.resolve()):
        raise ValueError("Extraction destination must be within the selected workspace")
    if destination.exists() and (not destination.is_dir() or any(destination.iterdir())):
        raise FileExistsError("Extraction requires a new or empty destination")
    with zipfile.ZipFile(archive_path) as archive:
        _validated(archive)
        destination.mkdir(parents=True, exist_ok=True)
        for name in archive.namelist():
            target = destination / name
            _no_links(target)
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as stream:
                stream.write(archive.read(name))
    return {"ok": True, "destination": str(destination), **verify(archive_path)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="operation", required=True)
    cap = sub.add_parser("capture")
    cap.add_argument("--commands-json", type=Path, required=True)
    cap.add_argument("--output-zip", type=Path, required=True)
    check = sub.add_parser("verify")
    check.add_argument("archive", type=Path)
    unpack = sub.add_parser("extract")
    unpack.add_argument("archive", type=Path)
    unpack.add_argument("destination", type=Path)
    args = parser.parse_args()
    if args.operation == "capture":
        result = capture(args.output_zip, json.loads(args.commands_json.read_text(encoding="utf-8")))
    elif args.operation == "verify":
        result = verify(args.archive)
    else:
        result = extract(args.archive, args.destination)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
