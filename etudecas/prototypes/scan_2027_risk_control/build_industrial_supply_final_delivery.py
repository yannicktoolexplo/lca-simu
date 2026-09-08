#!/usr/bin/env python3
"""Build a portable folder, ZIP and single HTML from explicit HTML mappings.

The builder is deliberately presentation-agnostic.  Every source HTML and its
portable destination are supplied by the caller.  Existing files are read and
hashed but never edited; all rewritten navigation lives in a fresh staging
directory.  No simulation data source is discovered implicitly.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import posixpath
import re
import shutil
import tempfile
import unicodedata
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Iterable, Mapping, Sequence
from urllib.parse import unquote, urlsplit, urlunsplit

from etudecas.prototypes.scan_2027_risk_control import standalone_single_html


SCHEMA_VERSION = "etudecas.portable_html_delivery.v1"
MANIFEST_FILE = "delivery_manifest.json"
MANIFEST_DIGEST_FILE = "delivery_manifest.sha256.txt"
README_FILE = "LISEZ_MOI.txt"
DEFAULT_LAUNCHER = "OUVRIR_LA_DEMONSTRATION.html"
REFERENCE_RE = re.compile(
    r"(?<![\w:-])(?P<attribute>href|src)\s*=\s*(?P<quote>['\"])(?P<value>[^'\"]*)(?P=quote)",
    re.IGNORECASE,
)
ALLOWED_EMBEDDED_SCHEMES = {"data", "blob"}


@dataclass(frozen=True)
class HtmlAsset:
    source: Path
    destination: str
    opaque: bool = False


@dataclass(frozen=True)
class EvidenceAsset:
    source: Path
    destination: str


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _portable_path(value: str, *, suffix: str | None = None) -> str:
    raw = str(value or "")
    normalized = unicodedata.normalize("NFC", raw).replace("\\", "/")
    pure = PurePosixPath(normalized)
    if (
        not normalized
        or raw != raw.strip()
        or pure.is_absolute()
        or normalized.startswith("/")
        or pure.as_posix() != normalized
        or any(
            part in {"", ".", ".."}
            or part.endswith((".", " "))
            or any(ord(character) < 32 for character in part)
            or any(
                character in standalone_single_html.WINDOWS_INVALID_NAME_CHARS
                for character in part
            )
            or part.split(".", 1)[0].upper()
            in standalone_single_html.WINDOWS_RESERVED_NAMES
            for part in pure.parts
        )
    ):
        raise ValueError(f"Portable destination must be a safe relative path: {value}")
    if suffix is not None and pure.suffix.lower() != suffix:
        raise ValueError(f"Portable destination must end with {suffix}: {value}")
    return pure.as_posix()


def _child(root: Path, relative: str) -> Path:
    normalized = _portable_path(relative)
    target = root.joinpath(*PurePosixPath(normalized).parts).resolve()
    try:
        target.relative_to(root.resolve())
    except ValueError as error:
        raise ValueError(f"Portable path escapes its root: {relative}") from error
    return target


def _source_snapshot(paths: Iterable[Path]) -> dict[Path, tuple[int, str]]:
    snapshot: dict[Path, tuple[int, str]] = {}
    for raw in paths:
        path = raw.resolve()
        if not path.is_file():
            raise FileNotFoundError(f"Delivery source not found: {path}")
        snapshot[path] = (path.stat().st_size, _sha256(path))
    return snapshot


def _assert_snapshot(snapshot: Mapping[Path, tuple[int, str]]) -> None:
    for path, expected in snapshot.items():
        if not path.is_file() or (path.stat().st_size, _sha256(path)) != expected:
            raise RuntimeError(f"Delivery source changed during the build: {path}")


def _resolved_local_target(source: Path, reference: str) -> Path:
    parsed = urlsplit(html.unescape(reference.strip()))
    return (source.parent / unquote(parsed.path)).resolve()


def _validate_opaque_html(document: str, *, source: Path) -> None:
    if not standalone_single_html._is_opaque_standalone(document):
        raise ValueError(f"Opaque HTML does not expose the standalone contract: {source}")
    standalone_single_html._validate_opaque_standalone_references(
        document,
        source.name,
    )
    standalone_single_html.validate_single_html(source)


def _rewrite_html(
    document: str,
    *,
    source: Path,
    destination: str,
    source_to_destination: Mapping[Path, str],
) -> str:
    standalone_single_html._assert_no_reserved_source_markers(
        document,
        label=str(source),
    )
    standalone_single_html._validate_document_contract(
        document,
        label=str(source),
        allow_local=True,
    )
    destination_parent = PurePosixPath(destination).parent.as_posix()
    relative_start = "." if destination_parent == "." else destination_parent

    def replace_tag(tag_match: re.Match[str]) -> str:
        tag_document = tag_match.group(0)
        tag = tag_match.group("tag").casefold()

        def replace_reference(match: re.Match[str]) -> str:
            attribute = match.group("attribute").casefold()
            reference = html.unescape(match.group("value").strip())
            if not reference or reference.startswith("#"):
                return match.group(0)
            if attribute == "href" and tag != "a":
                return match.group(0)
            parsed = urlsplit(reference)
            if parsed.scheme in ALLOWED_EMBEDDED_SCHEMES and attribute == "src":
                return match.group(0)
            if parsed.scheme or parsed.netloc:
                raise ValueError(
                    f"External reference is forbidden: {source} -> {reference}"
                )
            if not parsed.path:
                return match.group(0)
            target = _resolved_local_target(source, reference)
            mapped = source_to_destination.get(target)
            if mapped is None:
                raise FileNotFoundError(
                    "Local reference has no explicit delivery mapping: "
                    f"{source} -> {reference}"
                )
            rewritten_path = posixpath.relpath(mapped, start=relative_start)
            rewritten = urlunsplit(
                ("", "", rewritten_path, parsed.query, parsed.fragment)
            )
            return (
                f"{match.group('attribute')}={match.group('quote')}"
                f"{html.escape(rewritten, quote=True)}{match.group('quote')}"
            )

        return REFERENCE_RE.sub(replace_reference, tag_document)

    rewritten = standalone_single_html.START_TAG_RE.sub(replace_tag, document)
    rewritten = standalone_single_html._inject_csp(
        rewritten,
        standalone_single_html.PORTABLE_CSP_POLICY,
    )
    standalone_single_html._validate_document_contract(
        rewritten,
        label=str(source),
        allow_local=True,
    )
    return rewritten


def _reference_issues(root: Path) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    resolved_root = root.resolve()
    for page in sorted(root.rglob("*.html")):
        try:
            document = page.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            issues.append(
                {
                    "page": page.relative_to(root).as_posix(),
                    "reference": "",
                    "reason": "invalid_utf8",
                }
            )
            continue
        try:
            standalone_single_html._validate_document_contract(
                document,
                label=page.relative_to(root).as_posix(),
                allow_local=True,
            )
        except ValueError as error:
            issues.append(
                {
                    "page": page.relative_to(root).as_posix(),
                    "reference": "",
                    "reason": f"offline_contract:{error}",
                }
            )
            continue
        references = (
            match
            for tag in standalone_single_html.START_TAG_RE.finditer(document)
            for match in REFERENCE_RE.finditer(tag.group(0))
        )
        for match in references:
            reference = html.unescape(match.group("value").strip())
            if not reference or reference.startswith("#"):
                continue
            parsed = urlsplit(reference)
            if parsed.scheme in ALLOWED_EMBEDDED_SCHEMES:
                continue
            if parsed.scheme or parsed.netloc:
                issues.append(
                    {
                        "page": page.relative_to(root).as_posix(),
                        "reference": reference,
                        "reason": "external_reference",
                    }
                )
                continue
            if not parsed.path:
                continue
            target = (page.parent / unquote(parsed.path)).resolve()
            try:
                target.relative_to(resolved_root)
            except ValueError:
                issues.append(
                    {
                        "page": page.relative_to(root).as_posix(),
                        "reference": reference,
                        "reason": "outside_package",
                    }
                )
                continue
            if not target.is_file():
                issues.append(
                    {
                        "page": page.relative_to(root).as_posix(),
                        "reference": reference,
                        "reason": "missing_local_target",
                    }
                )
    return issues


def _readme(launcher: str, single_html_name: str) -> str:
    return (
        "LIVRAISON HTML PORTABLE\n\n"
        f"Dossier/ZIP : extraire le dossier puis ouvrir {launcher}.\n"
        f"Fichier unique : ouvrir {single_html_name} avec un navigateur récent.\n\n"
        "Aucun serveur et aucun accès Internet ne sont nécessaires. "
        "Les fichiers sources n'ont pas été modifiés.\n"
    )


def _populate_package(
    root: Path,
    *,
    entrypoint_source: Path,
    html_assets: Sequence[HtmlAsset],
    evidence_assets: Sequence[EvidenceAsset],
    launcher_name: str,
    single_html_name: str,
    source_snapshot: Mapping[Path, tuple[int, str]],
) -> dict[str, object]:
    root.mkdir(parents=True, exist_ok=False)
    launcher_name = _portable_path(launcher_name, suffix=".html")
    if PurePosixPath(launcher_name).parent.as_posix() != ".":
        raise ValueError("The lightweight launcher must be a root HTML filename")

    normalized_assets = [
        HtmlAsset(
            source=asset.source.resolve(),
            destination=_portable_path(asset.destination, suffix=".html"),
            opaque=asset.opaque,
        )
        for asset in html_assets
    ]
    entrypoint_source = entrypoint_source.resolve()
    if any(asset.source == entrypoint_source for asset in normalized_assets):
        raise ValueError("The entrypoint must not be repeated as an HTML asset")
    destinations = ["index.html", launcher_name] + [
        asset.destination for asset in normalized_assets
    ]
    normalized_evidence = [
        EvidenceAsset(
            source=asset.source.resolve(),
            destination=_portable_path(asset.destination),
        )
        for asset in evidence_assets
    ]
    destinations.extend(asset.destination for asset in normalized_evidence)
    reserved = {
        MANIFEST_FILE,
        MANIFEST_DIGEST_FILE,
        README_FILE,
        standalone_single_html.INVENTORY_PATH,
    }
    portable_names = {destination.casefold() for destination in destinations}
    reserved_names = {destination.casefold() for destination in reserved}
    if (
        len(destinations) != len(portable_names)
        or reserved_names & portable_names
    ):
        raise ValueError("Portable destinations are duplicated or reserved")

    source_to_destination = {entrypoint_source: "index.html"}
    source_to_destination.update(
        {asset.source: asset.destination for asset in normalized_assets}
    )
    source_to_destination.update(
        {asset.source: asset.destination for asset in normalized_evidence}
    )
    expected_source_count = len(normalized_assets) + len(normalized_evidence) + 1
    if len(source_to_destination) != expected_source_count:
        raise ValueError("A delivery source is mapped more than once")

    source_records: list[dict[str, object]] = []
    html_plan = [HtmlAsset(entrypoint_source, "index.html"), *normalized_assets]
    for asset in html_plan:
        try:
            document = asset.source.read_text(encoding="utf-8")
        except UnicodeDecodeError as error:
            raise ValueError(f"Source HTML is not UTF-8: {asset.source}") from error
        if asset.opaque:
            _validate_opaque_html(document, source=asset.source)
            rewritten = None
        else:
            rewritten = _rewrite_html(
                document,
                source=asset.source,
                destination=asset.destination,
                source_to_destination=source_to_destination,
            )
        destination = _child(root, asset.destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if rewritten is None:
            destination.write_bytes(asset.source.read_bytes())
        else:
            destination.write_text(rewritten, encoding="utf-8")
        source_size, source_hash = source_snapshot[asset.source]
        source_records.append(
            {
                "kind": "html",
                "destination": asset.destination,
                "opaque": asset.opaque,
                "source_bytes": source_size,
                "source_sha256": source_hash,
                "portable_sha256": _sha256(destination),
            }
        )

    index_path = root / "index.html"
    launcher_path = root / launcher_name
    shutil.copyfile(index_path, launcher_path)
    source_records.append(
        {
            "kind": "launcher_alias",
            "destination": launcher_name,
            "source_bytes": index_path.stat().st_size,
            "source_sha256": _sha256(index_path),
            "portable_sha256": _sha256(launcher_path),
        }
    )

    for asset in normalized_evidence:
        destination = _child(root, asset.destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(asset.source, destination)
        source_size, source_hash = source_snapshot[asset.source]
        source_records.append(
            {
                "kind": "evidence",
                "destination": asset.destination,
                "source_bytes": source_size,
                "source_sha256": source_hash,
                "portable_sha256": _sha256(destination),
            }
        )

    (root / README_FILE).write_text(
        _readme(launcher_name, single_html_name),
        encoding="utf-8",
    )
    issues = _reference_issues(root)
    if issues:
        raise ValueError(
            "Portable HTML reference validation failed: "
            + json.dumps(issues, ensure_ascii=False)
        )

    output_files: dict[str, dict[str, object]] = {}
    for path in sorted(value for value in root.rglob("*") if value.is_file()):
        relative = path.relative_to(root).as_posix()
        output_files[relative] = {
            "size_bytes": path.stat().st_size,
            "sha256": _sha256(path),
        }
    manifest: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "status": "complete",
        "created_at_utc": _utc_now(),
        "entrypoint": "index.html",
        "lightweight_launcher": launcher_name,
        "single_html_companion": single_html_name,
        "offline": True,
        "portable": True,
        "requires_internet": False,
        "requires_local_server": False,
        "source_artifacts_mutated": False,
        "security_profile": standalone_single_html.SECURITY_PROFILE,
        "normal_html_csp": standalone_single_html.PORTABLE_CSP_POLICY,
        "opaque_html_policy": "cryptographically_validated_and_copied_unchanged",
        "source_records": source_records,
        "outputs": output_files,
    }
    _write_json(root / MANIFEST_FILE, manifest)
    manifest_hash = _sha256(root / MANIFEST_FILE)
    (root / MANIFEST_DIGEST_FILE).write_text(
        f"{manifest_hash}  {MANIFEST_FILE}\n",
        encoding="ascii",
    )
    return manifest


def validate_delivery_package(root: Path) -> dict[str, object]:
    root = root.resolve()
    manifest_path = root / MANIFEST_FILE
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (
        not isinstance(manifest, dict)
        or manifest.get("schema_version") != SCHEMA_VERSION
        or manifest.get("status") != "complete"
        or manifest.get("offline") is not True
        or manifest.get("portable") is not True
        or manifest.get("requires_internet") is not False
        or manifest.get("requires_local_server") is not False
        or manifest.get("source_artifacts_mutated") is not False
        or manifest.get("security_profile")
        != standalone_single_html.SECURITY_PROFILE
        or manifest.get("normal_html_csp")
        != standalone_single_html.PORTABLE_CSP_POLICY
        or manifest.get("opaque_html_policy")
        != "cryptographically_validated_and_copied_unchanged"
    ):
        raise ValueError("Portable delivery manifest is not releasable")
    outputs = manifest.get("outputs")
    if not isinstance(outputs, dict) or not outputs:
        raise ValueError("Portable delivery output ledger is missing")
    for relative, record in outputs.items():
        if not isinstance(record, dict):
            raise ValueError(f"Invalid output record: {relative}")
        path = _child(root, str(relative))
        if (
            not path.is_file()
            or path.stat().st_size != int(record.get("size_bytes", -1))
            or _sha256(path) != str(record.get("sha256") or "")
        ):
            raise ValueError(f"Portable output hash mismatch: {relative}")
    observed_files = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
    }
    if observed_files != set(outputs) | {MANIFEST_FILE, MANIFEST_DIGEST_FILE}:
        raise ValueError("Portable delivery contains an unsigned or missing file")
    digest_line = (root / MANIFEST_DIGEST_FILE).read_text(encoding="ascii").strip()
    expected_line = f"{_sha256(manifest_path)}  {MANIFEST_FILE}"
    if digest_line != expected_line:
        raise ValueError("Portable delivery manifest digest mismatch")
    entrypoint = _child(root, str(manifest.get("entrypoint") or ""))
    launcher = _child(root, str(manifest.get("lightweight_launcher") or ""))
    if entrypoint.read_bytes() != launcher.read_bytes():
        raise ValueError("Lightweight launcher differs from index.html")
    source_records = manifest.get("source_records")
    if not isinstance(source_records, list):
        raise ValueError("Portable source record ledger is missing")
    for record in source_records:
        if (
            not isinstance(record, dict)
            or record.get("kind") != "html"
            or record.get("opaque") is True
        ):
            continue
        page = _child(root, str(record.get("destination") or ""))
        standalone_single_html._assert_csp(
            page.read_text(encoding="utf-8"),
            standalone_single_html.PORTABLE_CSP_POLICY,
            label=str(record.get("destination")),
        )
    issues = _reference_issues(root)
    if issues:
        raise ValueError(
            "Portable HTML reference validation failed: "
            + json.dumps(issues, ensure_ascii=False)
        )
    return manifest


def _build_zip(root: Path, archive: Path) -> dict[str, object]:
    with zipfile.ZipFile(
        archive,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as bundle:
        for path in sorted(value for value in root.rglob("*") if value.is_file()):
            relative = (PurePosixPath(root.name) / path.relative_to(root).as_posix()).as_posix()
            info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            with path.open("rb") as source, bundle.open(
                info,
                "w",
                force_zip64=True,
            ) as destination:
                shutil.copyfileobj(source, destination, length=1024 * 1024)
    expected = {
        (PurePosixPath(root.name) / path.relative_to(root).as_posix()).as_posix()
        for path in root.rglob("*")
        if path.is_file()
    }
    with zipfile.ZipFile(archive) as bundle:
        observed = set(bundle.namelist())
        if observed != expected or any(
            name.startswith("/") or ".." in PurePosixPath(name).parts
            for name in observed
        ):
            raise ValueError("Portable ZIP inventory is invalid")
        bad = bundle.testzip()
        if bad is not None:
            raise ValueError(f"Portable ZIP contains a corrupt member: {bad}")
    return {
        "path": str(archive),
        "size_bytes": archive.stat().st_size,
        "sha256": _sha256(archive),
        "file_count": len(expected),
    }


def build_delivery(
    *,
    entrypoint_source: Path,
    html_assets: Sequence[HtmlAsset],
    evidence_assets: Sequence[EvidenceAsset],
    output_dir: Path,
    archive: Path,
    single_html: Path,
    launcher_name: str = DEFAULT_LAUNCHER,
) -> dict[str, object]:
    output_dir = output_dir.resolve()
    archive = archive.resolve()
    single_html = single_html.resolve()
    archive_digest = archive.with_suffix(archive.suffix + ".sha256.txt")
    single_digest = single_html.with_suffix(single_html.suffix + ".sha256.txt")
    final_targets = (output_dir, archive, archive_digest, single_html, single_digest)
    normalized_targets = {
        unicodedata.normalize("NFC", str(path)).casefold() for path in final_targets
    }
    if len(normalized_targets) != len(final_targets):
        raise ValueError("Delivery output targets must all be distinct")
    existing = [str(path) for path in final_targets if path.exists()]
    if existing:
        raise FileExistsError("Delivery outputs already exist: " + ", ".join(existing))
    if archive.suffix.lower() != ".zip" or single_html.suffix.lower() != ".html":
        raise ValueError("Archive must be .zip and the single-file output must be .html")
    parent = output_dir.parent
    if archive.parent != parent or single_html.parent != parent:
        raise ValueError("Folder, ZIP and single HTML must share one output parent")
    parent.mkdir(parents=True, exist_ok=True)

    source_paths = [entrypoint_source, *(asset.source for asset in html_assets)]
    source_paths.extend(asset.source for asset in evidence_assets)
    snapshot = _source_snapshot(source_paths)
    staging_parent = Path(
        tempfile.mkdtemp(prefix=f".{output_dir.name}.staging-", dir=parent)
    ).resolve()
    package_stage = staging_parent / output_dir.name
    archive_stage = staging_parent / archive.name
    single_stage = staging_parent / single_html.name
    moved: list[Path] = []
    try:
        manifest = _populate_package(
            package_stage,
            entrypoint_source=entrypoint_source,
            html_assets=html_assets,
            evidence_assets=evidence_assets,
            launcher_name=launcher_name,
            single_html_name=single_html.name,
            source_snapshot=snapshot,
        )
        validate_delivery_package(package_stage)
        single_result = standalone_single_html.build_single_html(
            package_stage,
            single_stage,
            index_aliases=(launcher_name,),
        )
        standalone_single_html.validate_single_html(single_stage)
        zip_result = _build_zip(package_stage, archive_stage)
        archive_stage_digest = archive_stage.with_suffix(
            archive_stage.suffix + ".sha256.txt"
        )
        archive_stage_digest.write_text(
            f"{zip_result['sha256']}  {archive.name}\n",
            encoding="ascii",
        )
        _assert_snapshot(snapshot)

        moves = (
            (archive_stage, archive),
            (archive_stage_digest, archive_digest),
            (single_stage, single_html),
            (
                single_stage.with_suffix(single_stage.suffix + ".sha256.txt"),
                single_digest,
            ),
            (package_stage, output_dir),
        )
        for source, destination in moves:
            source.rename(destination)
            moved.append(destination)
        staging_parent.rmdir()
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "complete",
            "output_dir": str(output_dir),
            "launcher": str(output_dir / launcher_name),
            "archive": {
                **zip_result,
                "path": str(archive),
                "digest_file": str(archive_digest),
            },
            "single_html": {
                **single_result,
                "output_html": str(single_html),
                "hash_file": str(single_digest),
            },
            "source_artifacts_mutated": False,
            "delivery_manifest": manifest,
        }
    except Exception:
        for path in reversed(moved):
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink(missing_ok=True)
        if staging_parent.is_dir():
            shutil.rmtree(staging_parent)
        raise


def _mapping(value: str, *, opaque: bool = False) -> HtmlAsset:
    try:
        source, destination = value.split("=", 1)
    except ValueError as error:
        raise argparse.ArgumentTypeError("Expected SOURCE=DESTINATION") from error
    if not source.strip() or not destination.strip():
        raise argparse.ArgumentTypeError("Expected SOURCE=DESTINATION")
    return HtmlAsset(Path(source.strip()), destination.strip(), opaque=opaque)


def _evidence_mapping(value: str) -> EvidenceAsset:
    try:
        source, destination = value.split("=", 1)
    except ValueError as error:
        raise argparse.ArgumentTypeError("Expected SOURCE=DESTINATION") from error
    if not source.strip() or not destination.strip():
        raise argparse.ArgumentTypeError("Expected SOURCE=DESTINATION")
    return EvidenceAsset(Path(source.strip()), destination.strip())


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--entrypoint-html", type=Path, required=True)
    parser.add_argument(
        "--html-map",
        action="append",
        default=[],
        metavar="SOURCE=DESTINATION",
    )
    parser.add_argument(
        "--opaque-html-map",
        action="append",
        default=[],
        metavar="SOURCE=DESTINATION",
    )
    parser.add_argument(
        "--file-map",
        "--evidence-map",
        dest="evidence_map",
        action="append",
        default=[],
        metavar="SOURCE=DESTINATION",
    )
    parser.add_argument("--launcher-name", default=DEFAULT_LAUNCHER)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--single-html", type=Path, required=True)
    args = parser.parse_args(argv)
    args.html_assets = [
        *(_mapping(value) for value in args.html_map),
        *(_mapping(value, opaque=True) for value in args.opaque_html_map),
    ]
    args.evidence_assets = [
        _evidence_mapping(value) for value in args.evidence_map
    ]
    return args


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    result = build_delivery(
        entrypoint_source=args.entrypoint_html,
        html_assets=args.html_assets,
        evidence_assets=args.evidence_assets,
        output_dir=args.output_dir,
        archive=args.archive,
        single_html=args.single_html,
        launcher_name=args.launcher_name,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
