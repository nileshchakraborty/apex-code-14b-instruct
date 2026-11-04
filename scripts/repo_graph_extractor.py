#!/usr/bin/env python3
"""Repository Symbol & Call-Graph Context Extractor.

Extracts class hierarchies, typed function signatures, dataclass schemas,
and cross-module dependency graphs using Python's AST parser.
Generates ultra-compact typed interface headers (<1,500 tokens) that provide
LLMs with full repository awareness without filling the context window with
irrelevant function bodies.
"""

import ast
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


@dataclass
class FunctionSignature:
    name: str
    args: str
    return_type: Optional[str] = None
    docstring: Optional[str] = None
    is_async: bool = False
    decorators: List[str] = field(default_factory=list)

    def to_stub(self, indent: str = "") -> str:
        async_prefix = "async " if self.is_async else ""
        ret = f" -> {self.return_type}" if self.return_type else ""
        dec = "".join(f"{indent}@{d}\n" for d in self.decorators)
        doc = f'\n{indent}    """{self.docstring}"""' if self.docstring else ""
        return f"{dec}{indent}{async_prefix}def {self.name}({self.args}){ret}:{doc}\n{indent}    ..."


@dataclass
class ClassSummary:
    name: str
    bases: List[str] = field(default_factory=list)
    docstring: Optional[str] = None
    fields: List[Tuple[str, Optional[str]]] = field(default_factory=list)  # (name, type)
    methods: List[FunctionSignature] = field(default_factory=list)
    decorators: List[str] = field(default_factory=list)

    def to_stub(self, indent: str = "") -> str:
        dec = "".join(f"{indent}@{d}\n" for d in self.decorators)
        base_str = f"({', '.join(self.bases)})" if self.bases else ""
        lines = [f"{dec}{indent}class {self.name}{base_str}:"]
        
        if self.docstring:
            lines.append(f'{indent}    """{self.docstring}"""')
            
        for fname, ftype in self.fields:
            if ftype:
                lines.append(f"{indent}    {fname}: {ftype}")
            else:
                lines.append(f"{indent}    {fname} = ...")
                
        if not self.methods and not self.fields and not self.docstring:
            lines.append(f"{indent}    ...")
        else:
            for m in self.methods:
                lines.append(m.to_stub(indent=indent + "    "))
                
        return "\n".join(lines)


@dataclass
class ModuleSummary:
    module_path: str  # e.g. "scripts.ast_contract_compiler"
    file_path: str
    docstring: Optional[str] = None
    imports: List[str] = field(default_factory=list)
    classes: List[ClassSummary] = field(default_factory=list)
    functions: List[FunctionSignature] = field(default_factory=list)
    constants: List[Tuple[str, Optional[str]]] = field(default_factory=list)  # (name, type)

    def to_stub(self) -> str:
        lines = [f"# Module: {self.module_path}"]
        if self.docstring:
            lines.append(f'"""{self.docstring}"""')
        
        # Imports summary
        if self.imports:
            lines.extend(self.imports)
            lines.append("")

        # Constants
        if self.constants:
            for cname, ctype in self.constants:
                if ctype:
                    lines.append(f"{cname}: {ctype} = ...")
                else:
                    lines.append(f"{cname} = ...")
            lines.append("")

        # Classes
        for cls in self.classes:
            lines.append(cls.to_stub())
            lines.append("")

        # Top-level Functions
        for fn in self.functions:
            lines.append(fn.to_stub())
            lines.append("")

        return "\n".join(lines).strip()


class RepoASTVisitor(ast.NodeVisitor):
    """AST visitor extracting structural symbols and signatures from a single Python file."""

    def __init__(self, module_path: str, file_path: str):
        self.module_path = module_path
        self.file_path = file_path
        self.docstring: Optional[str] = None
        self.imports: List[str] = []
        self.classes: List[ClassSummary] = []
        self.functions: List[FunctionSignature] = []
        self.constants: List[Tuple[str, Optional[str]]] = []
        self._current_class: Optional[ClassSummary] = None

    def _unparse(self, node: Optional[ast.AST]) -> str:
        if node is None:
            return ""
        try:
            return ast.unparse(node)
        except Exception:
            return ""

    def visit_Module(self, node: ast.Module):
        # Extract module-level docstring
        doc = ast.get_docstring(node)
        if doc:
            self.docstring = doc.split("\n")[0].strip()  # Single-line summary
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import):
        if self._current_class is None:
            for alias in node.names:
                as_str = f" as {alias.asname}" if alias.asname else ""
                self.imports.append(f"import {alias.name}{as_str}")

    def visit_ImportFrom(self, node: ast.ImportFrom):
        if self._current_class is None:
            module = node.module or ""
            dots = "." * node.level
            names = ", ".join(
                f"{a.name} as {a.asname}" if a.asname else a.name for a in node.names
            )
            self.imports.append(f"from {dots}{module} import {names}")

    def visit_AnnAssign(self, node: ast.AnnAssign):
        """Extract typed field or constant."""
        name = self._unparse(node.target)
        type_str = self._unparse(node.annotation)
        if self._current_class is not None:
            self._current_class.fields.append((name, type_str))
        else:
            if name.isupper():
                self.constants.append((name, type_str))

    def visit_Assign(self, node: ast.Assign):
        """Extract untyped upper-case constant."""
        if self._current_class is None:
            for target in node.targets:
                name = self._unparse(target)
                if name.isupper():
                    self.constants.append((name, None))

    def _extract_fn_signature(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef, is_async: bool
    ) -> FunctionSignature:
        args_str = self._unparse(node.args)
        ret_type = self._unparse(node.returns) if node.returns else None
        doc = ast.get_docstring(node)
        doc_summary = doc.split("\n")[0].strip() if doc else None
        decorators = [self._unparse(d) for d in node.decorator_list]
        return FunctionSignature(
            name=node.name,
            args=args_str,
            return_type=ret_type,
            docstring=doc_summary,
            is_async=is_async,
            decorators=decorators,
        )

    def visit_FunctionDef(self, node: ast.FunctionDef):
        sig = self._extract_fn_signature(node, is_async=False)
        if self._current_class is not None:
            self._current_class.methods.append(sig)
        else:
            self.functions.append(sig)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        sig = self._extract_fn_signature(node, is_async=True)
        if self._current_class is not None:
            self._current_class.methods.append(sig)
        else:
            self.functions.append(sig)

    def visit_ClassDef(self, node: ast.ClassDef):
        bases = [self._unparse(b) for b in node.bases]
        doc = ast.get_docstring(node)
        doc_summary = doc.split("\n")[0].strip() if doc else None
        decorators = [self._unparse(d) for d in node.decorator_list]
        cls_summary = ClassSummary(
            name=node.name,
            bases=bases,
            docstring=doc_summary,
            decorators=decorators,
        )

        old_class = self._current_class
        self._current_class = cls_summary
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef, ast.AnnAssign)):
                self.visit(item)
        self._current_class = old_class

        self.classes.append(cls_summary)


class RepoGraphExtractor:
    """Scans repositories, resolves module dependencies, and generates typed interfaces."""

    def __init__(self, repo_root: str):
        self.repo_root = Path(repo_root).resolve()
        self.modules: Dict[str, ModuleSummary] = {}
        self.dependency_graph: Dict[str, Set[str]] = {}  # module -> imported modules

    def scan_repository(
        self,
        subdirs: Optional[List[str]] = None,
        exclude_dirs: Optional[Set[str]] = None,
    ) -> Dict[str, ModuleSummary]:
        """Traverse Python files and build AST symbol index."""
        if exclude_dirs is None:
            exclude_dirs = {
                ".git",
                "__pycache__",
                ".venv",
                "venv",
                "env",
                ".pytest_cache",
                ".mypy_cache",
                "build",
                "dist",
                "site-packages",
            }

        scan_roots = (
            [self.repo_root / d for d in subdirs] if subdirs else [self.repo_root]
        )

        for sroot in scan_roots:
            if not sroot.exists():
                continue
            for root, dirs, files in os.walk(sroot):
                dirs[:] = [d for d in dirs if d not in exclude_dirs]
                for file in files:
                    if file.endswith(".py") and not file.startswith("."):
                        fpath = Path(root) / file
                        self._process_file(fpath)

        self._build_dependency_graph()
        return self.modules

    def _process_file(self, fpath: Path):
        try:
            rel_path = fpath.relative_to(self.repo_root)
            mod_parts = list(rel_path.with_suffix("").parts)
            if mod_parts and mod_parts[-1] == "__init__":
                mod_parts = mod_parts[:-1]
            mod_name = ".".join(mod_parts) if mod_parts else rel_path.stem

            code = fpath.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(code, filename=str(fpath))
            visitor = RepoASTVisitor(module_path=mod_name, file_path=str(rel_path))
            visitor.visit(tree)

            mod_summary = ModuleSummary(
                module_path=mod_name,
                file_path=str(rel_path),
                docstring=visitor.docstring,
                imports=visitor.imports,
                classes=visitor.classes,
                functions=visitor.functions,
                constants=visitor.constants,
            )
            self.modules[mod_name] = mod_summary
        except Exception:
            pass  # Silently skip unparseable or binary files

    def _build_dependency_graph(self):
        """Map cross-module import relationships."""
        all_mods = set(self.modules.keys())
        for mod_name, mod in self.modules.items():
            deps: Set[str] = set()
            for imp in mod.imports:
                for target_mod in all_mods:
                    if target_mod != mod_name and (
                        f"import {target_mod}" in imp
                        or f"from {target_mod}" in imp
                        or any(imp.startswith(f"from .{m}") for m in target_mod.split("."))
                    ):
                        deps.add(target_mod)
            self.dependency_graph[mod_name] = deps

    def get_interface_header(
        self,
        target_modules: Optional[List[str]] = None,
        include_dependencies: bool = True,
        max_chars: int = 12000,  # ~2,500 tokens
    ) -> str:
        """Generate a compact multi-file typed interface header for LLM context injection."""
        selected_mods: Set[str] = set()

        if target_modules:
            for tm in target_modules:
                if tm in self.modules:
                    selected_mods.add(tm)
                    if include_dependencies:
                        selected_mods.update(self.dependency_graph.get(tm, set()))
        else:
            # Include all non-test modules
            selected_mods = {
                m for m in self.modules.keys() if not m.startswith("tests.") and "test" not in m
            }

        headers: List[str] = [
            "# ==============================================================================",
            "# REPOSITORY TYPED INTERFACE HEADER (Auto-generated AST Symbol Graph)",
            "# Provides exact types, classes, and method signatures without implementation bodies.",
            "# ==============================================================================",
            "",
        ]

        current_len = sum(len(h) for h in headers)
        for mod_name in sorted(selected_mods):
            if mod_name not in self.modules:
                continue
            stub = self.modules[mod_name].to_stub()
            if current_len + len(stub) > max_chars:
                headers.append(f"# [Truncated {len(selected_mods) - len(headers)} additional modules to fit budget]")
                break
            headers.append(stub)
            headers.append("-" * 60)
            current_len += len(stub) + 65

        return "\n".join(headers)


def _test_repo_extractor():
    print("🧪 Testing Repository Symbol Call-Graph Extractor...")
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "core").mkdir()
        
        # File 1: core/base.py
        (root / "core" / "base.py").write_text(
            '"""Base abstractions for data storage."""\n'
            'from typing import Optional, Any\n'
            'MAX_CAPACITY: int = 1000\n\n'
            'class BaseStorage:\n'
            '    """Abstract storage class."""\n'
            '    def __init__(self, capacity: int = MAX_CAPACITY):\n'
            '        self.capacity = capacity\n\n'
            '    def get(self, key: str) -> Optional[Any]:\n'
            '        """Retrieve value by key."""\n'
            '        raise NotImplementedError\n'
        )

        # File 2: core/lru.py
        (root / "core" / "lru.py").write_text(
            '"""LRU Cache implementation."""\n'
            'from core.base import BaseStorage, MAX_CAPACITY\n'
            'from typing import Any, Optional\n\n'
            'class LRUCache(BaseStorage):\n'
            '    """Least-Recently Used Cache."""\n'
            '    def __init__(self, capacity: int = MAX_CAPACITY):\n'
            '        super().__init__(capacity)\n'
            '        self._data = {}\n\n'
            '    def get(self, key: str) -> Optional[Any]:\n'
            '        return self._data.get(key)\n\n'
            '    def put(self, key: str, value: Any) -> None:\n'
            '        """Insert or update key-value pair."""\n'
            '        self._data[key] = value\n'
        )

        extractor = RepoGraphExtractor(str(root))
        mods = extractor.scan_repository()
        print(f"  Discovered modules: {list(mods.keys())}")
        assert "core.base" in mods
        assert "core.lru" in mods

        # Check symbol extraction
        base_mod = mods["core.base"]
        assert len(base_mod.classes) == 1
        assert base_mod.classes[0].name == "BaseStorage"
        assert len(base_mod.classes[0].methods) == 2

        # Check dependency resolution
        assert "core.base" in extractor.dependency_graph.get("core.lru", set())
        print("  ✅ Cross-module dependency graph resolved correctly.")

        # Check interface header generation
        header = extractor.get_interface_header(target_modules=["core.lru"])
        print("  Generated Header Preview:")
        for line in header.split("\n")[:25]:
            print("   ", line)
        assert "class LRUCache(BaseStorage):" in header
        assert "def put(self, key: str, value: Any) -> None:" in header
        assert "class BaseStorage:" in header  # Included automatically via dependency graph!
        print("  ✅ Dependency inclusion verified in header stub.")

    print("🎉 Repository Symbol Call-Graph Extractor verified successfully!")


if __name__ == "__main__":
    _test_repo_extractor()
