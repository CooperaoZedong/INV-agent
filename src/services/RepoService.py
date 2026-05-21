from __future__ import annotations

import ast
import fnmatch
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

@dataclass(frozen=True)
class RepoServiceConfig:
    repo_root: Path
    max_file_size_bytes: int = 1_024_000      # 1 MB
    max_read_lines: int = 1200
    max_search_hits: int = 100
    blocked_dirs: tuple[str, ...] = (
        ".git",
        ".idea",
        ".vscode",
        ".venv",
        "venv",
        "node_modules",
        "dist",
        "build",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".next",
        "coverage",
        "target",
    )
    blocked_file_names: tuple[str, ...] = (
        ".env",
        ".env.local",
        ".env.production",
        ".env.development",
        "poetry.lock",
        "devb_device_insights_event.json"
    )

class LocalRepoService:
    def __init__(self, config: RepoServiceConfig):
        self.config = config
        self.repo_root = config.repo_root

        if not self.repo_root.exists():
            raise FileNotFoundError(f"Repo root does not exist: {self.repo_root}")
        if not self.repo_root.is_dir():
            raise NotADirectoryError(f"Repo root is not a directory: {self.repo_root}")

    def _resolve_path(self, relative_path: str) -> Path:
        resolved_path = (self.repo_root / relative_path).resolve()
        if not str(resolved_path).startswith(str(self.repo_root)):
            raise ValueError(f"Attempted path traversal outside of repo root: {relative_path}")
        self._assert_not_blocked(resolved_path)
        return resolved_path

    def _assert_not_blocked(self, path: Path) -> None:
        for part in path.parts:
            if part in self.config.blocked_dirs:
                raise ValueError(f"Blocked path segment: {part}")

        if path.name in self.config.blocked_file_names:
            raise ValueError(f"Blocked file: {path.name}")

    def _is_blocked_path(self, path: Path) -> bool:
        try:
            self._assert_not_blocked(path)
            return False
        except ValueError:
            return True

    def _is_text_file(self, path: Path) -> bool:
        try:
            with path.open("rb") as f:
                chunk = f.read(2048)
            return b"\x00" not in chunk
        except Exception:
            return False

    def _safe_read_text(self, path: Path) -> str:
        size = path.stat().st_size
        if size > self.config.max_file_size_bytes:
            raise ValueError(
                f"File too large to read safely ({size} bytes): {path.relative_to(self.repo_root)}"
            )
        if not self._is_text_file(path):
            raise ValueError(f"Not a text file: {path.relative_to(self.repo_root)}")

        return path.read_text(encoding="utf-8", errors="ignore")

    def _iter_files(self, path: str = ".") -> Iterable[Path]:
        root = self._resolve_path(path)
        if root.is_file():
            yield root
            return

        for dirpath, dirnames, filenames in os.walk(root):
            dirpath_p = Path(dirpath)

            dirnames[:] = [
                d
                for d in dirnames
                if d not in self.config.blocked_dirs
                   and not self._is_blocked_path(dirpath_p / d)
            ]

            for filename in filenames:
                p = dirpath_p / filename
                if self._is_blocked_path(p):
                    continue
                yield p

    def list_tree(self, path: str = ".", depth: int = 3, max_entries_per_dir: int = 200) -> Dict[str, Any]:
        root = self._resolve_path(path)

        if root.is_file():
            return {
                "root": str(root.relative_to(self.repo_root)),
                "type": "file",
            }

        results: List[Dict[str, Any]] = []
        base_depth = len(root.parts)

        for dirpath, dirnames, filenames in os.walk(root):
            dirpath_p = Path(dirpath)
            rel_dir = str(dirpath_p.relative_to(self.repo_root))

            dirnames[:] = [
                d
                for d in sorted(dirnames)
                if d not in self.config.blocked_dirs
                   and not self._is_blocked_path(dirpath_p / d)
            ]

            current_depth = len(dirpath_p.parts) - base_depth
            if current_depth > depth:
                dirnames[:] = []
                continue

            visible_files = []
            for f in sorted(filenames):
                p = dirpath_p / f
                if self._is_blocked_path(p):
                    continue
                visible_files.append(f)

            results.append(
                {
                    "dir": rel_dir,
                    "subdirs": dirnames[:max_entries_per_dir],
                    "files": visible_files[:max_entries_per_dir],
                }
            )

        return {
            "root": str(root.relative_to(self.repo_root)),
            "depth": depth,
            "tree": results,
        }

    def read_file(
            self,
            path: str,
            start_line: Optional[int] = None,
            end_line: Optional[int] = None,
    ) -> Dict[str, Any]:
        p = self._resolve_path(path)
        if not p.is_file():
            raise ValueError(f"Not a file: {path}")

        content = self._safe_read_text(p)
        lines = content.splitlines()

        s = 1 if start_line is None else max(1, start_line)
        e = len(lines) if end_line is None else min(len(lines), end_line)

        if e < s:
            raise ValueError("end_line must be >= start_line")

        if (e - s + 1) > self.config.max_read_lines:
            e = s + self.config.max_read_lines - 1

        selected = lines[s - 1 : e]

        return {
            "path": str(p.relative_to(self.repo_root)),
            "start_line": s,
            "end_line": e,
            "total_lines": len(lines),
            "content": "\n".join(selected),
        }

    def read_multiple(
            self,
            paths: List[str],
            start_line: Optional[int] = None,
            end_line: Optional[int] = None,
    ) -> Dict[str, Any]:
        results = []
        for path in paths[:20]:
            try:
                results.append(self.read_file(path, start_line=start_line, end_line=end_line))
            except Exception as exc:
                results.append({"path": path, "error": str(exc)})

        return {"files": results}

    def search_code(
            self,
            query: str,
            path: str = ".",
            glob: Optional[str] = None,
            regex: bool = False,
            case_sensitive: bool = False,
    ) -> Dict[str, Any]:
        flags = 0 if case_sensitive else re.IGNORECASE
        pattern = re.compile(query if regex else re.escape(query), flags=flags)

        hits: List[Dict[str, Any]] = []

        for p in self._iter_files(path):
            if glob and not fnmatch.fnmatch(p.name, glob) and not fnmatch.fnmatch(
                    str(p.relative_to(self.repo_root)), glob
            ):
                continue

            try:
                content = self._safe_read_text(p)
            except Exception:
                continue

            for idx, line in enumerate(content.splitlines(), start=1):
                if pattern.search(line):
                    hits.append(
                        {
                            "path": str(p.relative_to(self.repo_root)),
                            "line": idx,
                            "match": line[:500],
                        }
                    )
                    if len(hits) >= self.config.max_search_hits:
                        return {
                            "query": query,
                            "path": path,
                            "glob": glob,
                            "regex": regex,
                            "matches": hits,
                            "truncated": True,
                        }

        return {
            "query": query,
            "path": path,
            "glob": glob,
            "regex": regex,
            "matches": hits,
            "truncated": False,
        }

    def find_symbol(self, symbol_name: str, path: str = ".") -> Dict[str, Any]:
        """
        Python-first symbol lookup:
        - top-level class defs
        - top-level function defs
        - async defs
        - class methods
        """
        matches: List[Dict[str, Any]] = []

        for p in self._iter_files(path):
            if p.suffix != ".py":
                continue

            try:
                source = self._safe_read_text(p)
                tree = ast.parse(source)
            except Exception:
                continue

            rel_path = str(p.relative_to(self.repo_root))

            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == symbol_name:
                    matches.append(
                        {
                            "path": rel_path,
                            "symbol": node.name,
                            "kind": "function",
                            "line": node.lineno,
                            "end_line": getattr(node, "end_lineno", node.lineno),
                        }
                    )

                elif isinstance(node, ast.ClassDef):
                    if node.name == symbol_name:
                        matches.append(
                            {
                                "path": rel_path,
                                "symbol": node.name,
                                "kind": "class",
                                "line": node.lineno,
                                "end_line": getattr(node, "end_lineno", node.lineno),
                            }
                        )

                    for child in node.body:
                        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name == symbol_name:
                            matches.append(
                                {
                                    "path": rel_path,
                                    "symbol": f"{node.name}.{child.name}",
                                    "kind": "method",
                                    "line": child.lineno,
                                    "end_line": getattr(child, "end_lineno", child.lineno),
                                }
                            )

            if len(matches) >= self.config.max_search_hits:
                break

        return {
            "symbol_name": symbol_name,
            "matches": matches[: self.config.max_search_hits],
        }

    def get_module_summary(self, path: str) -> Dict[str, Any]:
        """
        Best on Python files. Returns:
        - imports
        - classes
        - top-level functions
        - docstring
        """
        p = self._resolve_path(path)
        if not p.is_file():
            raise ValueError(f"Not a file: {path}")

        result = {
            "path": str(p.relative_to(self.repo_root)),
            "language": self._infer_language(p),
            "module_docstring": None,
            "imports": [],
            "classes": [],
            "functions": [],
        }

        if p.suffix != ".py":
            return result

        source = self._safe_read_text(p)
        tree = ast.parse(source)

        result["module_docstring"] = ast.get_docstring(tree)

        imports: List[str] = []
        classes: List[Dict[str, Any]] = []
        functions: List[Dict[str, Any]] = []

        for node in tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)

            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    imports.append(f"{module}.{alias.name}".strip("."))

            elif isinstance(node, ast.ClassDef):
                methods = [
                    child.name
                    for child in node.body
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
                ]
                classes.append(
                    {
                        "name": node.name,
                        "line": node.lineno,
                        "methods": methods,
                    }
                )

            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions.append(
                    {
                        "name": node.name,
                        "line": node.lineno,
                    }
                )

        result["imports"] = sorted(set(imports))
        result["classes"] = classes
        result["functions"] = functions
        return result

    def dependency_map(self, target: str) -> Dict[str, Any]:
        """
        For v1, keep this simple:
        - if target is a file: summarize imports from that file
        - if target is a symbol: find symbol, then summarize enclosing file(s)
        """
        try:
            p = self._resolve_path(target)
            if p.is_file():
                return {
                    "target_type": "file",
                    "target": str(p.relative_to(self.repo_root)),
                    "summary": self.get_module_summary(str(p.relative_to(self.repo_root))),
                }
        except Exception:
            pass

        symbol_hits = self.find_symbol(target)
        summaries = []

        seen = set()
        for hit in symbol_hits["matches"]:
            path = hit["path"]
            if path in seen:
                continue
            seen.add(path)
            try:
                summaries.append(self.get_module_summary(path))
            except Exception as exc:
                summaries.append({"path": path, "error": str(exc)})

        return {
            "target_type": "symbol",
            "target": target,
            "matches": symbol_hits["matches"],
            "summaries": summaries,
        }

    def _infer_language(self, path: Path) -> str:
        mapping = {
            ".py": "python",
            ".ts": "typescript",
            ".tsx": "typescript-react",
            ".js": "javascript",
            ".jsx": "javascript-react",
            ".java": "java",
            ".go": "go",
            ".rb": "ruby",
            ".cs": "csharp",
            ".php": "php",
            ".kt": "kotlin",
            ".rs": "rust",
            ".sql": "sql",
            ".sh": "shell",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".json": "json",
        }
        return mapping.get(path.suffix.lower(), "unknown")

