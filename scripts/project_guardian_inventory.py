from __future__ import annotations

import ast
from collections import Counter
import os
import re
import subprocess
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


SOURCE_SUFFIXES = {
    ".cs",
    ".fs",
    ".vb",
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".java",
    ".go",
    ".rs",
}
PROJECT_SUFFIXES = {".csproj", ".fsproj", ".vbproj"}
PROJECT_FILENAMES = {"package.json", "pyproject.toml", "cargo.toml", "go.mod"}
SOLUTION_SUFFIXES = {".sln", ".slnx"}


class InventoryError(RuntimeError):
    pass


def _flags() -> int:
    return subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def normalize_path(value: str | os.PathLike[str]) -> str:
    return str(Path(value).expanduser().resolve(strict=False))


def run_git(root: str, args: Iterable[str], check: bool = True) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=normalize_path(root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=_flags(),
        timeout=120,
    )
    if check and completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise InventoryError(f"Git command failed: {detail}")
    return completed.stdout.strip()


def git_root(path: str) -> str:
    root = run_git(path, ["rev-parse", "--show-toplevel"])
    if not root:
        raise InventoryError(f"Not a Git repository: {path}")
    return normalize_path(root)


def git_common_dir(path: str) -> str:
    root = git_root(path)
    value = run_git(root, ["rev-parse", "--git-common-dir"])
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = Path(root) / candidate
    return normalize_path(candidate)


def same_repository(left: str, right: str) -> bool:
    try:
        return os.path.normcase(git_common_dir(left)) == os.path.normcase(git_common_dir(right))
    except (InventoryError, OSError):
        return False


def list_tree(root: str, ref: str) -> list[str]:
    output = run_git(root, ["ls-tree", "-r", "--name-only", ref])
    return sorted(line.replace("\\", "/") for line in output.splitlines() if line.strip())


def _project_markers(files: list[str]) -> list[str]:
    markers = []
    for path in files:
        pure = PurePosixPath(path)
        if pure.suffix.lower() in PROJECT_SUFFIXES | SOLUTION_SUFFIXES:
            markers.append(path)
        elif pure.name.lower() in PROJECT_FILENAMES:
            markers.append(path)
    return markers


def _branch_rows(root: str) -> list[dict[str, Any]]:
    fmt = "%00".join(
        [
            "%(refname:short)",
            "%(objectname)",
            "%(upstream:short)",
            "%(upstream:trackshort)",
            "%(committerdate:iso-strict)",
            "%(subject)",
        ]
    )
    output = run_git(root, ["for-each-ref", f"--format={fmt}", "refs/heads", "refs/remotes"])
    rows = []
    for line in output.splitlines():
        parts = line.split("\x00")
        if len(parts) != 6:
            continue
        name, commit, upstream, tracking, committed_at, subject = parts
        rows.append(
            {
                "name": name,
                "commit": commit,
                "upstream": upstream or None,
                "tracking": tracking or None,
                "committed_at": committed_at or None,
                "last_commit_subject": subject or None,
                "remote": name.startswith("origin/"),
            }
        )
    return rows


def _worktree_rows(root: str) -> list[dict[str, Any]]:
    output = run_git(root, ["worktree", "list", "--porcelain"])
    records: list[dict[str, Any]] = []
    current: dict[str, Any] = {}
    for line in [*output.splitlines(), ""]:
        if not line:
            if current:
                path = current.get("path")
                if path and Path(path).exists():
                    status = run_git(path, ["status", "--porcelain=v1"], check=False)
                    changes = [entry for entry in status.splitlines() if entry.strip()]
                    current["dirty"] = bool(changes)
                    current["change_count"] = len(changes)
                else:
                    current["dirty"] = None
                    current["change_count"] = None
                records.append(current)
            current = {}
            continue
        key, _, value = line.partition(" ")
        if key == "worktree":
            current["path"] = normalize_path(value)
        elif key == "HEAD":
            current["commit"] = value
        elif key == "branch":
            current["branch"] = value.removeprefix("refs/heads/")
        elif key in {"detached", "bare", "locked", "prunable"}:
            current[key] = True
            if value:
                current[f"{key}_reason"] = value
    return records


def _candidate_summaries(root: str, branches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates = []
    for branch in branches:
        if branch["remote"] or branch["name"].endswith("/HEAD"):
            continue
        try:
            files = list_tree(root, branch["name"])
        except InventoryError:
            continue
        markers = _project_markers(files)
        top_areas = Counter(
            "/".join(path.split("/")[:2]) if "/" in path else "repository root" for path in files
        )
        source_count = sum(1 for path in files if PurePosixPath(path).suffix.lower() in SOURCE_SUFFIXES)
        score = len(markers) * 1000 + min(source_count, 10000) * 3 + min(len(files), 10000)
        candidates.append(
            {
                "ref": branch["name"],
                "commit": branch["commit"],
                "file_count": len(files),
                "source_file_count": source_count,
                "project_markers": markers[:50],
                "top_areas": [
                    {"path": path, "file_count": count} for path, count in top_areas.most_common(12)
                ],
                "score": score,
                "committed_at": branch.get("committed_at"),
            }
        )
    return sorted(candidates, key=lambda row: (row["score"], row.get("committed_at") or ""), reverse=True)


def choose_base(
    root: str,
    default_branch: str,
    branches: list[dict[str, Any]],
    requested_ref: str | None = None,
) -> dict[str, Any]:
    candidates = _candidate_summaries(root, branches)
    by_name = {row["ref"]: row for row in candidates}
    if requested_ref:
        commit = run_git(root, ["rev-parse", "--verify", f"{requested_ref}^{{commit}}"])
        selected = by_name.get(requested_ref)
        if selected is None:
            files = list_tree(root, commit)
            selected = {
                "ref": requested_ref,
                "commit": commit,
                "file_count": len(files),
                "source_file_count": sum(
                    1 for path in files if PurePosixPath(path).suffix.lower() in SOURCE_SUFFIXES
                ),
                "project_markers": _project_markers(files)[:50],
                "top_areas": [],
                "score": 0,
                "committed_at": None,
            }
        return {"selected": selected, "recommended": selected, "candidates": candidates, "reason": "explicit"}

    default = by_name.get(default_branch)
    if default and (default["project_markers"] or default["source_file_count"] >= 10):
        return {"selected": default, "recommended": default, "candidates": candidates, "reason": "default_branch_has_code"}

    # A truly greenfield repository has one committed code line, even when it contains
    # only a README or .gitignore. Select that line automatically. An empty default
    # branch remains ambiguous when other branches contain distinct commits/code.
    unique_commits = {row["commit"] for row in candidates}
    if default and len(unique_commits) == 1:
        return {"selected": default, "recommended": default, "candidates": candidates, "reason": "single_greenfield_code_line"}

    recommended = candidates[0] if candidates else None
    second = candidates[1] if len(candidates) > 1 else None
    clearly_better = bool(
        recommended
        and recommended["project_markers"]
        and (second is None or recommended["score"] >= max(second["score"] * 1.25, second["score"] + 1000))
    )
    return {
        "selected": recommended if clearly_better else None,
        "recommended": recommended,
        "candidates": candidates,
        "reason": "clear_candidate" if clearly_better else "ambiguous_or_empty_default",
    }


def _read_blobs(root: str, commit: str, paths: list[str]) -> dict[str, str]:
    if not paths:
        return {}
    process = subprocess.Popen(
        ["git", "cat-file", "--batch"],
        cwd=root,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=_flags(),
    )
    assert process.stdin is not None and process.stdout is not None
    values: dict[str, str] = {}
    try:
        for path in paths:
            if "\n" in path or "\r" in path:
                continue
            process.stdin.write(f"{commit}:{path}\n".encode("utf-8"))
            process.stdin.flush()
            header = process.stdout.readline()
            if not header or header.rstrip().endswith(b" missing"):
                continue
            parts = header.rstrip().split()
            if len(parts) < 3:
                continue
            size = int(parts[-1])
            content = process.stdout.read(size)
            process.stdout.read(1)
            values[path] = content.decode("utf-8", errors="replace")
    finally:
        process.stdin.close()
        process.terminate()
        process.wait(timeout=5)
        process.stdout.close()
        if process.stderr is not None:
            process.stderr.close()
    return values


def _module_kind(path: str) -> str:
    value = path.lower()
    if re.search(r"(^|/)(tests?|__tests__)(/|$)", value) or "test" in PurePosixPath(value).stem:
        return "test"
    if re.search(r"(^|/)(tools?|scripts?)(/|$)", value):
        return "tool"
    return "source"


def _module_id(path: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9._/-]+", "-", path.strip("/")) or "root"
    return f"module:{value}"


def _discover_modules(files: list[str], blobs: dict[str, str]) -> tuple[list[dict[str, Any]], dict[str, str]]:
    manifests = [
        path
        for path in files
        if PurePosixPath(path).suffix.lower() in PROJECT_SUFFIXES
        or PurePosixPath(path).name.lower() in PROJECT_FILENAMES
    ]
    roots = []
    for manifest in manifests:
        root = str(PurePosixPath(manifest).parent)
        roots.append(("" if root == "." else root, manifest))
    if not roots:
        top = sorted({path.split("/", 1)[0] if "/" in path else "" for path in files})
        roots = [(value, value or "repository") for value in top]
    roots = sorted(set(roots), key=lambda row: (len(row[0]), row[0]))

    modules: list[dict[str, Any]] = []
    for root, manifest in roots:
        name = PurePosixPath(manifest).stem if manifest != "repository" else "repository"
        modules.append(
            {
                "id": _module_id(root or name),
                "name": name,
                "root": root,
                "manifest": manifest if manifest in files else None,
                "kind": _module_kind(root or manifest),
                "file_count": 0,
                "source_file_count": 0,
                "test_file_count": 0,
                "dependencies": [],
            }
        )

    file_modules: dict[str, str] = {}
    for path in files:
        matching = [module for module in modules if not module["root"] or path == module["root"] or path.startswith(module["root"] + "/")]
        module = max(matching, key=lambda row: len(row["root"])) if matching else modules[0]
        file_modules[path] = module["id"]
        module["file_count"] += 1
        if PurePosixPath(path).suffix.lower() in SOURCE_SUFFIXES:
            module["source_file_count"] += 1
            if _module_kind(path) == "test":
                module["test_file_count"] += 1

    manifest_to_module = {module["manifest"]: module for module in modules if module.get("manifest")}
    for manifest, module in manifest_to_module.items():
        if PurePosixPath(manifest).suffix.lower() not in PROJECT_SUFFIXES:
            continue
        for include in re.findall(r"<ProjectReference\s+Include=[\"']([^\"']+)", blobs.get(manifest, ""), re.IGNORECASE):
            target = str((PurePosixPath(manifest).parent / PurePosixPath(include.replace("\\", "/"))))
            parts = []
            for part in PurePosixPath(target).parts:
                if part == "..":
                    if parts:
                        parts.pop()
                elif part != ".":
                    parts.append(part)
            normalized = "/".join(parts)
            dependency = manifest_to_module.get(normalized)
            if dependency and dependency["id"] != module["id"]:
                module["dependencies"].append(dependency["id"])
        module["dependencies"] = sorted(set(module["dependencies"]))
    return modules, file_modules


def _line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _parameter_names(raw: str) -> list[str]:
    values = []
    for part in raw.split(","):
        cleaned = re.sub(r"\s*=.*$", "", part).strip()
        if not cleaned:
            continue
        tokens = re.findall(r"[A-Za-z_][A-Za-z0-9_]*", cleaned)
        if tokens:
            values.append(tokens[-1])
    return values


def _python_symbols(path: str, text: str, module_id: str) -> list[dict[str, Any]]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    values = []
    stack: list[str] = []

    class Visitor(ast.NodeVisitor):
        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            qualified = ".".join([*stack, node.name])
            values.append({"kind": "class", "name": node.name, "qualified_name": qualified, "signature": f"class {node.name}", "parameters": [], "file": path, "line": node.lineno, "module_id": module_id})
            stack.append(node.name)
            self.generic_visit(node)
            stack.pop()

        def _function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
            parameters = [argument.arg for argument in [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]]
            if node.args.vararg:
                parameters.append("*" + node.args.vararg.arg)
            if node.args.kwarg:
                parameters.append("**" + node.args.kwarg.arg)
            qualified = ".".join([*stack, node.name])
            values.append({"kind": "method" if stack else "function", "name": node.name, "qualified_name": qualified, "signature": f"{node.name}({', '.join(parameters)})", "parameters": parameters, "file": path, "line": node.lineno, "module_id": module_id})
            stack.append(node.name)
            self.generic_visit(node)
            stack.pop()

        visit_FunctionDef = _function
        visit_AsyncFunctionDef = _function

    Visitor().visit(tree)
    return values


def _regex_symbols(path: str, text: str, module_id: str) -> list[dict[str, Any]]:
    values = []
    suffix = PurePosixPath(path).suffix.lower()
    if suffix in {".cs", ".java"}:
        for match in re.finditer(r"\b(class|interface|record|struct|enum)\s+([A-Za-z_][A-Za-z0-9_]*)", text):
            values.append({"kind": match.group(1), "name": match.group(2), "qualified_name": match.group(2), "signature": match.group(0), "parameters": [], "file": path, "line": _line_number(text, match.start()), "module_id": module_id})
        method = re.compile(r"(?m)^\s*(?:(?:public|private|protected|internal|static|virtual|override|abstract|sealed|async|extern|partial|new)\s+)*[A-Za-z_][A-Za-z0-9_<>,.\[\]?]*\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(([^;{}]*)\)\s*(?:where[^\n{=>]+)?\s*(?:\{|=>|;)")
        for match in method.finditer(text):
            name = match.group(1)
            if name in {"if", "for", "foreach", "while", "switch", "catch", "using", "lock"}:
                continue
            params = _parameter_names(match.group(2))
            values.append({"kind": "method", "name": name, "qualified_name": name, "signature": f"{name}({', '.join(params)})", "parameters": params, "file": path, "line": _line_number(text, match.start()), "module_id": module_id})
    elif suffix in {".js", ".jsx", ".ts", ".tsx"}:
        pattern = re.compile(r"(?m)\b(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(([^)]*)\)|\bclass\s+([A-Za-z_$][\w$]*)")
        for match in pattern.finditer(text):
            name = match.group(1) or match.group(3)
            params = _parameter_names(match.group(2) or "")
            values.append({"kind": "function" if match.group(1) else "class", "name": name, "qualified_name": name, "signature": f"{name}({', '.join(params)})" if match.group(1) else f"class {name}", "parameters": params, "file": path, "line": _line_number(text, match.start()), "module_id": module_id})
    return values


def build_code_graph(root: str, commit: str, max_source_files: int = 1500, max_symbols: int = 8000) -> dict[str, Any]:
    files = list_tree(root, commit)
    source_files = [path for path in files if PurePosixPath(path).suffix.lower() in SOURCE_SUFFIXES]
    manifest_files = [path for path in files if PurePosixPath(path).suffix.lower() in PROJECT_SUFFIXES or PurePosixPath(path).name.lower() in PROJECT_FILENAMES]
    selected_sources = source_files[:max_source_files]
    blobs = _read_blobs(root, commit, sorted(set([*manifest_files, *selected_sources])))
    modules, file_modules = _discover_modules(files, blobs)
    symbols: list[dict[str, Any]] = []
    for path in selected_sources:
        text = blobs.get(path, "")
        module_id = file_modules.get(path, modules[0]["id"] if modules else "module:repository")
        found = _python_symbols(path, text, module_id) if path.lower().endswith(".py") else _regex_symbols(path, text, module_id)
        for symbol in found:
            symbol["id"] = f"symbol:{path}:{symbol['line']}:{symbol['name']}"
            symbols.append(symbol)
            if len(symbols) >= max_symbols:
                break
        if len(symbols) >= max_symbols:
            break
    file_nodes = [
        {"path": path, "module_id": file_modules.get(path), "kind": _module_kind(path)}
        for path in files
        if PurePosixPath(path).suffix.lower() in SOURCE_SUFFIXES or path in manifest_files
    ]
    return {
        "commit": commit,
        "file_count": len(files),
        "source_file_count": len(source_files),
        "modules": modules,
        "files": file_nodes,
        "symbols": symbols,
        "truncated": len(source_files) > len(selected_sources) or len(symbols) >= max_symbols,
        "limits": {"source_files": max_source_files, "symbols": max_symbols},
    }


def scan_repository(root: str, default_branch: str, requested_ref: str | None = None) -> dict[str, Any]:
    branches = _branch_rows(root)
    worktrees = _worktree_rows(root)
    base = choose_base(root, default_branch, branches, requested_ref=requested_ref)
    selected = base.get("selected")
    profiles = {row["ref"]: row for row in base.get("candidates", [])}
    for branch in branches:
        profile = profiles.get(branch["name"])
        if profile:
            for key in ("file_count", "source_file_count", "project_markers", "top_areas", "score"):
                branch[key] = profile.get(key)
        if selected and not branch["remote"]:
            counts = run_git(root, ["rev-list", "--left-right", "--count", f"{selected['commit']}...{branch['commit']}"], check=False)
            parts = counts.split()
            if len(parts) == 2 and all(part.isdigit() for part in parts):
                branch["behind_canonical"] = int(parts[0])
                branch["ahead_of_canonical"] = int(parts[1])
            changed = run_git(root, ["diff", "--name-only", f"{selected['commit']}...{branch['commit']}"], check=False)
            paths = [path.replace("\\", "/") for path in changed.splitlines() if path.strip()]
            branch["changed_paths"] = paths[:500]
            branch["changed_path_count"] = len(paths)
            branch["changed_paths_truncated"] = len(paths) > 500
    graph_source = selected or base.get("recommended")
    graph = build_code_graph(root, graph_source["commit"]) if graph_source else None
    if graph is not None:
        graph["ref"] = graph_source["ref"]
        graph["provisional"] = selected is None
    return {
        "branches": branches,
        "worktrees": worktrees,
        "base": base,
        "graph": graph,
    }
