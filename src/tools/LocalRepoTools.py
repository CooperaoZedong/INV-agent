from __future__ import annotations
from typing import List, Optional

from pydantic import BaseModel, Field
from langchain_core.tools import StructuredTool

from src.services.RepoService import LocalRepoService

class RepoListTreeArgs(BaseModel):
    path: str = Field(default='.', description="Relative path under the repo root")
    depth: int = Field(default=3, ge=0, le=8, description="Maximum folder depth to traverse")


class RepoReadFileArgs(BaseModel):
    path: str = Field(description="Relative file path under the repo root")
    start_line: Optional[int] = Field(default=None, ge=1, description="Optional start line")
    end_line: Optional[int] = Field(default=None, ge=1, description="Optional end line")


class RepoReadMultipleArgs(BaseModel):
    paths: List[str] = Field(description="List of relative file paths")
    start_line: Optional[int] = Field(default=None, ge=1)
    end_line: Optional[int] = Field(default=None, ge=1)


class RepoSearchCodeArgs(BaseModel):
    query: str = Field(description="Search text or regex pattern")
    path: str = Field(default=".", description="Relative path under repo root")
    glob: Optional[str] = Field(
        default=None,
        description='Optional file filter, e.g. "*.py" or "src/**/*.ts"',
    )
    regex: bool = Field(default=False, description="Interpret query as regex")
    case_sensitive: bool = Field(default=False, description="Use case-sensitive matching")


class RepoFindSymbolArgs(BaseModel):
    symbol_name: str = Field(description="Class, function, or method name to find")
    path: str = Field(default=".", description="Relative path under repo root")


class RepoModuleSummaryArgs(BaseModel):
    path: str = Field(description="Relative file path under repo root")


class RepoDependencyMapArgs(BaseModel):
    target: str = Field(
        description="Either a relative file path or a symbol name whose enclosing module(s) should be summarized"
    )

class LocalRepoToolset:
    def __init__(self, service: LocalRepoService):
        self.service = service

    def _list_tree(self, path: str = '.', depth: int = 3) -> dict:
        return self.service.list_tree(path=path, depth=depth)

    def _read_file(self, path: str, start_line: Optional[int] = None, end_line: Optional[int] = None) -> dict:
        return self.service.read_file(path=path, start_line=start_line, end_line=end_line)

    def _read_multiple(self, paths: List[str], start_line: Optional[int] = None, end_line: Optional[int] = None) -> dict:
        return self.service.read_multiple(paths=paths, start_line=start_line, end_line=end_line)

    def _search_code(self, query: str, path: str = '.', glob: Optional[str] = None, regex: bool = False, case_sensitive: bool = False) -> dict:
        return self.service.search_code(query=query, path=path, glob=glob, regex=regex, case_sensitive=case_sensitive)

    def _find_symbol(self, symbol_name: str, path: str = '.') -> dict:
        return self.service.find_symbol(symbol_name=symbol_name, path=path)

    def _get_module_summary(self, path: str) -> dict:
        return self.service.get_module_summary(path=path)

    def _dependency_map(self, target: str) -> dict:
        return self.service.dependency_map(target=target)

    def get_tools(self) -> List[StructuredTool]:
        return [
            StructuredTool.from_function(
                func=self._list_tree,
                name="repo_list_tree",
                description=(
                    "List directories and files under a relative path in the local repository. "
                    "Use this first to understand project structure."
                ),
                args_schema=RepoListTreeArgs,
            ),
            StructuredTool.from_function(
                func=self._read_file,
                name="repo_read_file",
                description=(
                    "Read a text file from the local repository. Optionally restrict to a line range."
                ),
                args_schema=RepoReadFileArgs,
            ),
            StructuredTool.from_function(
                func=self._read_multiple,
                name="repo_read_multiple",
                description=(
                    "Read several repository files in one tool call. Use for correlated modules."
                ),
                args_schema=RepoReadMultipleArgs,
            ),
            StructuredTool.from_function(
                func=self._search_code,
                name="repo_search_code",
                description=(
                    "Search code or text across repository files. Supports optional regex and glob filtering."
                ),
                args_schema=RepoSearchCodeArgs,
            ),
            StructuredTool.from_function(
                func=self._find_symbol,
                name="repo_find_symbol",
                description=(
                    "Find a Python class, function, or method by symbol name in the repository."
                ),
                args_schema=RepoFindSymbolArgs,
            ),
            StructuredTool.from_function(
                func=self._get_module_summary,
                name="repo_get_module_summary",
                description=(
                    "Summarize a module or file, including imports, classes, and top-level functions."
                ),
                args_schema=RepoModuleSummaryArgs,
            ),
            StructuredTool.from_function(
                func=self._dependency_map,
                name="repo_dependency_map",
                description=(
                    "Return a simple dependency-oriented summary for a file path or symbol name."
                ),
                args_schema=RepoDependencyMapArgs,
            ),
        ]
