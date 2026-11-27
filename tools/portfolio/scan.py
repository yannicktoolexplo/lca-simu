"""Inventory the tracked trees at every remote branch tip. Python 3.11+, Git.

The scanner never checks out a branch or executes project code. Its output is
an index of leads for review, not a scientific assessment.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter, defaultdict
from functools import lru_cache
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tempfile
import tomllib
import unicodedata
import warnings

SCHEMA = 1
MAX_BYTES = 8_000_000
MAX_EXAMPLES = 6
CODE = {".py", ".js", ".mjs", ".ts", ".r", ".jl", ".sql", ".sh", ".ps1", ".ipynb"}
DOC = {".md", ".rst", ".txt", ".adoc"}
DATA = {".csv", ".xlsx", ".xls", ".parquet", ".jsonl", ".feather", ".bw2package", ".tsv"}
FIGURE = {".png", ".svg", ".jpg", ".jpeg", ".webp", ".gif"}
CONFIG = {".json", ".yaml", ".yml", ".toml", ".ini", ".cfg"}
SELF = ("tools/portfolio/", ".agents/skills/supply-portfolio/")
VENDOR = {"node_modules", "__pycache__", "site-packages", ".venv", "venv", ".venv-brightway", "vendor"}
# Use distribution names for common imports with a distinct installation name.
DISTRIBUTIONS = {"sklearn": "scikit-learn", "PIL": "pillow", "yaml": "pyyaml",
                 "pptx": "python-pptx", "docx": "python-docx", "cv2": "opencv-python",
                 "dotenv": "python-dotenv", "mpl_toolkits": "matplotlib"}
ORDER = ["code", "notebook", "dependency", "data", "figure", "test", "document", "config", "presentation", "other"]


def git(repo, *args, data=None):
    # Explicit fetches are the only commands that may access the remote.
    env = dict(os.environ, GIT_NO_LAZY_FETCH="1", GIT_TERMINAL_PROMPT="0")
    return subprocess.run(["git", "-C", str(repo), *args], input=data, stdout=subprocess.PIPE,
                          check=True, env=env).stdout


def branch_heads(repo, remote, offline):
    if remote.startswith("-") or remote not in git(repo, "remote").decode().splitlines():
        raise ValueError(f"Remote Git inconnu : {remote!r}")
    prefix = f"refs/remotes/{remote}/"
    if not offline:
        # Explicit refspec works even with single-branch clones. Pruning is
        # restricted to this remote's tracking namespace. Local heads are untouched.
        git(repo, "fetch", "--atomic", "--prune", "--no-tags", "--no-recurse-submodules",
            remote, f"+refs/heads/*:{prefix}*")
    lines = git(repo, "for-each-ref", "--format=%(refname)%09%(objectname)%09%(symref)", prefix)
    heads = {}
    for line in lines.decode().splitlines():
        ref, sha, symref = line.split("\t")
        if not symref and ref != prefix + "HEAD":
            heads[ref[len(prefix):]] = sha
    if not heads:
        raise ValueError("Aucune branche distante en cache. Lancer un inventaire en ligne.")
    return heads


def file_kind(path, mode):
    p = PurePosixPath(path)
    if path.startswith(SELF) or path == ".codex/agents/portfolio_supply.toml":
        return "harness"
    if mode == "160000":
        return "submodule"
    if mode == "120000":
        return "symlink"
    if VENDOR.intersection(p.parts):
        return "vendor"
    name = p.name.lower()
    if ((name.startswith("requirements") and p.suffix == ".txt")
            or name in {"pyproject.toml", "package.json"}):
        return "dependency"
    ext = p.suffix.lower()
    if ext in CODE:
        if name.startswith("test_") or "tests" in p.parts:
            return "test"
        return "notebook" if ext == ".ipynb" else "code"
    if ext in DOC or ext in {".pdf", ".docx", ".html"}:
        return "document"
    if ext in FIGURE:
        return "figure"
    if ext in DATA:
        return "data"
    if ext in CONFIG:
        return "config"
    if ext in {".pptx", ".ppt"}:
        return "presentation"
    return "other"


def tree_index(repo, heads):
    entries = {}
    # Sharing a tip is common immediately after branching. Read that tree once.
    tips = defaultdict(list)
    for name, sha in heads.items():
        tips[sha].append(name)
    counts = Counter()
    for sha, branches in tips.items():
        records = git(repo, "ls-tree", "-r", "-z", "--full-tree", sha).split(b"\0")
        for record in records:
            if not record:
                continue
            meta, raw_path = record.split(b"\t", 1)
            mode, _, oid = meta.decode("ascii").split()
            path = os.fsdecode(raw_path)
            key = (path, oid, mode)
            if key not in entries:
                entries[key] = {"path": path, "blob": oid, "mode": mode,
                                "kind": file_kind(path, mode), "branches": []}
            entries[key]["branches"].extend(branches)
            counts.update(branches)
    return entries, counts


def source_candidate(row):
    p = PurePosixPath(row["path"])
    return (row["kind"] in {"code", "test", "notebook", "dependency"}
            or (row["kind"] == "document" and p.suffix.lower() in DOC))


def object_sizes(repo, objects):
    if not objects:
        return {}
    payload = ("\n".join(objects) + "\n").encode("ascii")
    info = git(repo, "cat-file", "--batch-check=%(objectname) %(objecttype) %(objectsize)", data=payload)
    sizes = {}
    for line in info.splitlines():
        oid, kind, *size = line.split()
        if kind == b"blob":
            sizes[oid.decode("ascii")] = int(size[0])
    return sizes


def get_sources(repo, remote, objects, offline):
    objects = sorted(set(objects))
    sizes = object_sizes(repo, objects)
    missing = sorted(set(objects).difference(sizes))
    if missing and not offline:
        # A blobless clone can have all trees but none of the source blobs.
        # Request only source objects, batching to avoid one connection per file.
        for start in range(0, len(missing), 256):
            block = missing[start:start + 256]
            git(repo, "-c", "fetch.negotiationAlgorithm=noop", "-c", "fetch.unpackLimit=1",
                "fetch", "--filter=blob:none", "--no-auto-maintenance", "--no-tags",
                "--no-write-fetch-head", "--no-recurse-submodules", "--stdin", remote, data=("\n".join(block) + "\n").encode("ascii"))
        sizes = object_sizes(repo, objects)
        if set(objects).difference(sizes):
            raise ValueError("Objets sources manquants après récupération.")
    eligible = sorted(oid for oid, size in sizes.items() if size <= MAX_BYTES)
    sources = {}
    # Keep a bounded batch here; fetching binary reports or datasets is unnecessary.
    for start in range(0, len(eligible), 24):
        block = eligible[start:start + 24]
        raw = git(repo, "cat-file", "--batch", data=("\n".join(block) + "\n").encode("ascii"))
        pos = 0
        for oid in block:
            header = raw.index(b"\n", pos)
            object_id, kind, length = raw[pos:header].split()
            size = int(length)
            if object_id.decode() != oid or kind != b"blob" or size != sizes[oid]:
                raise ValueError("Réponse cat-file incohérente.")
            value = raw[header + 1:header + 1 + size]
            pos = header + 2 + size
            try:
                if b"\0" not in value:
                    sources[oid] = value.decode("utf-8-sig")
            except UnicodeDecodeError:
                pass
    return sources, sizes


def normalize(text):
    folded = unicodedata.normalize("NFKD", text.casefold())
    ascii_like = "".join(ch for ch in folded if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9∞]+", " ", ascii_like).strip()


class Taxonomy:
    def __init__(self, rows):
        self.rows = {m["id"]: m for m in rows}
        if len(self.rows) != len(rows):
            raise ValueError("Identifiants de méthodes dupliqués.")
        self.terms = defaultdict(set)
        for m in rows:
            for term in m["terms"]:
                self.terms[normalize(term)].add(m["id"])
        terms = sorted(self.terms, key=lambda term: (-len(term), term))
        self.regex = re.compile(r"(?<!\S)(?=(" + "|".join(map(re.escape, terms)) + r")(?!\S))")

    def match(self, text):
        found = set()
        tokens = normalize(text)
        for token in self.regex.finditer(tokens):
            found.update(self.terms[token[1]])
        # PID also means process identifier in orchestration scripts. Require
        # a control-specific corroboration in the same evidence source.
        if "pid" in found and not re.search(
            r"\b(kp|ki|kd|correcteur|regulateur|controller|proportional|lqr|mpc|hinf|regulation)\b", tokens
        ):
            found.remove("pid")
        return found


def package_name(s):
    # PEP 508 project names and npm names. Never copy URLs, tokens or local paths.
    match = re.match(r"^([A-Za-z0-9][A-Za-z0-9_.-]*)(?=\s|\[|[!~<>=;@#]|$)", s.strip())
    if match:
        return re.sub(r"[-_.]+", "-", match[1]).lower()


def dependencies(path, text):
    name = PurePosixPath(path).name.lower()
    if name == "pyproject.toml":
        config = tomllib.loads(text)
        project = config.get("project", {})
        names = list(project.get("dependencies", []))
        for group in project.get("optional-dependencies", {}).values():
            names.extend(group)
        poetry = config.get("tool", {}).get("poetry", {})
        names.extend(key for key in poetry.get("dependencies", {}) if key != "python")
    elif name == "package.json":
        config = json.loads(text)
        return {"npm/" + key for field in ["dependencies", "devDependencies", "peerDependencies", "optionalDependencies"]
                for key in config.get(field, {}) if re.fullmatch(r"(?:@[\w.-]+/)?[\w.-]+", key)}
    else:
        names = text.splitlines()
    return {name for entry in names if isinstance(entry, str) and (name := package_name(entry))}


def imports_from(code):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SyntaxWarning)
        tree = ast.parse(code)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and not node.level and node.module:
            imported.add(node.module.split(".")[0])
    return imported


def notebook_code(text):
    chunks = []
    for cell in json.loads(text)["cells"]:
        if cell.get("cell_type") == "code":
            source = cell.get("source", "")
            chunks.append("".join(source))
    return chunks


def signals(entries, sources, sizes, taxonomy):
    # Filter repository modules using each branch's own names, including legacy
    # scripts imported by basename. Don't count relative imports or the stdlib.
    local = defaultdict(set)
    for row in entries.values():
        p = PurePosixPath(row["path"])
        if p.suffix == ".py" and row["kind"] in {"code", "test"}:
            for branch in row["branches"]:
                local[branch].add(p.stem)
                local[branch].update(p.parts[:-1])

    @lru_cache(maxsize=None)
    def inspect_blob(oid, suffix, dep_name):
        text = sources[oid]
        if text.startswith("version https://git-lfs.github.com/spec/v1"):
            return set(), set(), set(), "lfs_pointer"
        chunks = [text]
        declared, imported = set(), set()
        problem = None
        try:
            if dep_name:
                declared = dependencies(dep_name, text)
            elif suffix == ".ipynb":
                chunks = notebook_code(text)
            if suffix in {".py", ".ipynb"}:
                for chunk in chunks:
                    try:
                        imported.update(imports_from(chunk))
                    except (SyntaxError, ValueError, RecursionError):
                        # Recover standalone import statements from notebooks
                        # with magics or legacy scripts with syntax errors.
                        problem = "imports_partially_read"
                        for line in chunk.splitlines():
                            statement = line.strip()
                            if statement.startswith(("import ", "from ")):
                                try:
                                    imported.update(imports_from(statement))
                                except (SyntaxError, ValueError, RecursionError):
                                    pass
        except (ValueError, KeyError, TypeError, AttributeError, RecursionError):
            problem = "source_parse_error"
        found = taxonomy.match("\n".join(chunks))
        return found, declared, imported, problem

    for row in entries.values():
        p = PurePosixPath(row["path"])
        oid = row["blob"]
        branches = sorted(row["branches"])
        row.update(branches=branches, review=[], tools=[], methods=[])
        if row["kind"] in {"vendor", "harness", "submodule", "symlink"}:
            row["content"] = row["kind"]
            if row["kind"] in {"submodule", "symlink"}:
                row["review"].append("linked_resource")
            continue
        matched = taxonomy.match(row["path"])
        row["method_signals"] = {key: ["path"] for key in matched}
        if source_candidate(row):
            if oid not in sources:
                if oid not in sizes:
                    row["content"] = "object_not_cached"
                elif sizes[oid] > MAX_BYTES:
                    row["content"] = "over_size_limit"
                else:
                    row["content"] = "binary_or_non_utf8"
                row["review"].append(row["content"])
            else:
                dep_name = p.name if row["kind"] == "dependency" else ""
                body, declared, imported, problem = inspect_blob(oid, p.suffix.lower(), dep_name)
                for method in body:
                    row["method_signals"].setdefault(method, []).append("text")
                row["content"] = problem or "read"
                if problem:
                    row["review"].append(problem)
                for tool in sorted(declared):
                    row["tools"].append({"name": tool, "signal": "declared", "branches": branches})
                import_signals = defaultdict(set)
                for name in sorted(imported.difference(sys.stdlib_module_names, {"__future__"})):
                    external = [branch for branch in branches if name not in local[branch]]
                    if external:
                        tool = DISTRIBUTIONS.get(name, name).lower().replace("_", "-")
                        import_signals[tool].update(external)
                for tool, names in sorted(import_signals.items()):
                    row["tools"].append({"name": tool, "signal": "imported", "branches": sorted(names)})
        else:
            row["content"] = "path_only"
            if row["kind"] in {"presentation", "document", "other"}:
                row["review"].append("read_artifact")
        row["methods"] = sorted(row["method_signals"])
        if not row["methods"] and not row["tools"]:
            row["review"].append("unclassified")


def summarize(rows, heads, taxonomy):
    methods, tools = defaultdict(list), defaultdict(list)
    for row in rows:
        for mid in row["methods"]:
            methods[mid].append((row, row["branches"], "+".join(row["method_signals"][mid])))
        for tool in row["tools"]:
            tools[tool["name"]].append((row, tool["branches"], tool["signal"]))

    def summary(evidence):
        branches = sorted({b for _, bs, _ in evidence for b in bs})
        counts = Counter(row["kind"] for row, _, _ in evidence)
        def priority(item):
            row, _, sig = item
            # Prefer evidence in a source filename or an explicit declaration.
            return ("path" not in sig and sig not in {"declared", "imported"},
                    ORDER.index(row["kind"]) if row["kind"] in ORDER else len(ORDER),
                    len(row["path"]), row["path"], row["blob"])
        examples, seen_paths = [], set()
        for row, bs, sig in sorted(evidence, key=priority):
            if row["path"] in seen_paths:
                continue
            seen_paths.add(row["path"])
            name = "dev_P0001" if "dev_P0001" in bs else bs[0]
            examples.append({"branch": name, "sha": heads[name], "path": row["path"], "blob": row["blob"],
                             "kind": row["kind"], "signal": sig})
            if len(examples) == MAX_EXAMPLES:
                break
        return {"status": "signal_only" if evidence else "no_signal",
                "branches": branches, "counts": dict(counts), "examples": examples}

    catalog = [{k: v for k, v in spec.items() if k != "terms"} | summary(methods[mid])
               for mid, spec in taxonomy.rows.items()]
    tooling = [{"name": name} | summary(evidence) for name, evidence in sorted(tools.items())]
    return catalog, tooling


def write_lines(path, rows):
    with path.open("w", encoding="utf-8", errors="backslashreplace", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def run(repo, out, remote, offline):
    if out.exists():
        raise ValueError(f"Choisir un nouveau dossier de résultats : {out}")
    heads = branch_heads(repo, remote, offline)
    entries, tree_counts = tree_index(repo, heads)
    objects = [row["blob"] for row in entries.values() if source_candidate(row)]
    sources, sizes = get_sources(repo, remote, objects, offline)
    taxonomy = Taxonomy(json.loads(Path(__file__).with_name("taxonomy.json").read_text(encoding="utf-8")))
    signals(entries, sources, sizes, taxonomy)
    rows = [entries[key] for key in sorted(entries)]
    review = [row for row in rows if row["review"]]
    methods, tools = summarize(rows, heads, taxonomy)
    coverage = {"branch_file_occurrences": sum(tree_counts.values()), "unique_path_versions": len(rows),
                "unique_paths": len({r["path"] for r in rows}), "unique_objects": len({r["blob"] for r in rows}),
                "review_path_versions": len(review), "by_content": dict(Counter(r["content"] for r in rows)),
                "by_kind": dict(Counter(r["kind"] for r in rows)), "source_byte_limit": MAX_BYTES}
    inventory = {"schema_version": SCHEMA, "remote": remote, "ref_mode": "cached" if offline else "fetched",
                 "branches": [{"name": name, "sha": sha, "file_count": tree_counts[name]} for name, sha in sorted(heads.items())],
                 "methods": methods, "tools": tools, "coverage": coverage}
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=out.parent) as tmp:
        stage = Path(tmp) / "inventory"
        stage.mkdir()
        write_lines(stage / "files.jsonl", rows)
        write_lines(stage / "review.jsonl", review)
        (stage / "inventory.json").write_text(json.dumps(inventory, ensure_ascii=False, sort_keys=True, indent=2)
                                              + "\n", encoding="utf-8", errors="backslashreplace")
        stage.rename(out)
    return inventory


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--remote", default="origin")
    parser.add_argument("--out", type=Path, required=True, help="Nouveau dossier de résultats")
    parser.add_argument("--offline", action="store_true", help="Utiliser les branches distantes et objets en cache")
    args = parser.parse_args()
    try:
        inventory = run(args.repo, args.out, args.remote, args.offline)
    except (OSError, ValueError, subprocess.CalledProcessError) as err:
        parser.exit(1, f"Inventaire interrompu : {err}\n")
    print(f"{len(inventory['branches'])} branches, {inventory['coverage']['unique_path_versions']} "
          f"chemins/versions, {len(inventory['tools'])} outils candidats. {args.out / 'inventory.json'}")


if __name__ == "__main__":
    main()
