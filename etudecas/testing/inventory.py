"""Read-only comparison against an explicitly pinned source inventory."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path, PurePosixPath
import re

from etudecas.provenance import diagnose_source_hash


def compare_inventory(root: Path, reference: Path, expected_signature: str) -> dict:
    if not re.fullmatch(r"[0-9a-f]{64}", expected_signature):
        raise ValueError("Expected a lowercase SHA-256 signature")
    payload = json.loads(reference.read_text(encoding="utf-8-sig"))
    signature = payload.pop("inventory_signature")
    actual = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                      separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    if signature != expected_signature or actual != expected_signature:
        raise ValueError("Reference inventory signature is invalid or not the pinned version")
    entries = payload["entries"]
    if not isinstance(entries, list) or not entries or payload.get("entry_count") != len(entries):
        raise ValueError("Invalid inventory entry count")
    root = root.resolve()
    rows, seen = [], set()
    for entry in entries:
        relative = entry["relative_path"].replace("\\", "/")
        logical = PurePosixPath(relative)
        path = (root / relative).resolve()
        if (not relative or logical.is_absolute() or ".." in logical.parts or ":" in relative
                or relative in seen or not path.is_relative_to(root)):
            raise ValueError(f"Unsafe or duplicate inventory path: {relative}")
        seen.add(relative)
        if not re.fullmatch(r"[0-9a-f]{64}", entry["sha256"]):
            raise ValueError(f"Invalid source hash: {relative}")
        size = entry["size_bytes"]
        if type(size) is not int or size < 0:
            raise ValueError(f"Invalid source size: {relative}")
        if path.is_file():
            row = diagnose_source_hash(path, entry["sha256"])
            row["actual_size_bytes"] = path.stat().st_size
            if row["exact_match"] and row["actual_size_bytes"] != size:
                row.update(status="size_mismatch", exact_match=False)
        else:
            row = {"status": "missing", "exact_match": False,
                   "expected_sha256": entry["sha256"]}
        row.update(path=relative, expected_size_bytes=size)
        rows.append(row)
    same_root = str(root) == payload.get("repo")
    return {"reference_signature": signature, "reference_repo": payload.get("repo"),
            "current_repo": str(root), "repo_matches": same_root,
            "counts": dict(Counter(row["status"] for row in rows)), "entries": rows,
            "exact_match": same_root and all(row["exact_match"] for row in rows),
            "scope": "Recorded entries and repo only; transitive discovery and scientific validation are not performed"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--expected-signature", required=True)
    args = parser.parse_args(argv)
    try:
        result = compare_inventory(args.root, args.reference, args.expected_signature)
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        print(json.dumps({"error": str(exc)}))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["exact_match"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
