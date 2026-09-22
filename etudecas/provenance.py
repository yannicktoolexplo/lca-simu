"""Read-only diagnosis of exact SHA-256 mismatches for UTF-8 source files."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re


def diagnose_source_hash(path: Path, expected_sha256: str) -> dict[str, object]:
    """Classify a mismatch without accepting it or changing the source file."""
    if not re.fullmatch(r"[0-9a-fA-F]{64}", expected_sha256):
        raise ValueError("Expected a 64-character SHA-256 hex digest")
    expected = expected_sha256.lower()
    raw = path.read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    lf_hash = None
    try:
        raw.decode("utf-8")
    except UnicodeDecodeError:
        pass
    else:
        lf_hash = hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()
    status = "exact_match" if actual == expected else (
        "line_endings_only" if lf_hash == expected else "content_mismatch"
    )
    return {"path": str(path.resolve()), "status": status,
            "expected_sha256": expected, "actual_sha256": actual,
            "lf_candidate_sha256": lf_hash, "exact_match": actual == expected}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        result = diagnose_source_hash(args.path, args.expected_sha256)
    except (OSError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["exact_match"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
