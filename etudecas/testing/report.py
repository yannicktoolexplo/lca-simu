"""Summarize a pytest JUnit report without suppressing failures or errors."""

import argparse
from collections import Counter
import json
from pathlib import Path
import xml.etree.ElementTree as ET


def summarize(path: Path) -> dict:
    root = ET.parse(path).getroot()
    if root.tag not in ("testsuites", "testsuite"):
        raise ValueError("Expected a JUnit testsuites or testsuite root")
    counts = Counter()
    modules = {}
    failures = []
    skips = Counter()
    for case in root.iter("testcase"):
        classname = case.get("classname", "")
        name = case.get("name", "")
        outcomes = [(kind, case.find(kind)) for kind in ("error", "failure", "skipped")]
        kind, problem = next(((kind, value) for kind, value in outcomes if value is not None), ("passed", None))
        counts[kind] += 1
        group = classname or "collection"
        modules.setdefault(group, Counter())[kind] += 1
        if kind in ("error", "failure"):
            for diagnostic in case:
                if diagnostic.tag in ("error", "failure"):
                    failures.append({"classname": classname, "name": name, "outcome": diagnostic.tag,
                                     "message": diagnostic.get("message", ""), "detail": diagnostic.text or ""})
        elif kind == "skipped":
            skips[problem.get("message", "")] += 1
    if not counts:
        raise ValueError("JUnit report contains no test cases")
    return {"schema_version": "etudecas.test_report.v1", "source": path.name,
            "counts": dict(sorted(counts.items())), "testcase_count": sum(counts.values()),
            "modules": {name: dict(sorted(value.items())) for name, value in sorted(modules.items())},
            "failures": failures, "skip_reasons": dict(sorted(skips.items()))}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--junit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = summarize(args.junit)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except (OSError, ValueError, ET.ParseError) as exc:
        print(f"Report error: {exc}")
        return 2
    print(json.dumps(result["counts"]))
    return 1 if result["failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
