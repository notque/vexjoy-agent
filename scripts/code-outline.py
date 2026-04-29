#!/usr/bin/env python3
"""Extract structural outlines from source files using tree-sitter.

Usage:
    python3 scripts/code-outline.py path/to/file.py           # JSON output
    python3 scripts/code-outline.py path/to/file.py --format outline  # text outline
    python3 scripts/code-outline.py path/to/dir/ --recursive   # all files in dir

Exit codes: 0=success, 1=parse error, 2=script error
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

# Language detection from file extension
EXTENSION_MAP: dict[str, str] = {
    ".go": "go",
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".php": "php",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".swift": "swift",
    ".sh": "bash",
    ".bash": "bash",
    ".bas": "vb6",
    ".cls": "vb6",
    ".frm": "vb6",
}

# Tree-sitter grammar module names and their language() functions
GRAMMAR_MODULES: dict[str, tuple[str, str]] = {
    "python": ("tree_sitter_python", "language"),
    "javascript": ("tree_sitter_javascript", "language"),
    "typescript": ("tree_sitter_typescript", "language_typescript"),
    "go": ("tree_sitter_go", "language"),
    "php": ("tree_sitter_php", "language_php"),
    "bash": ("tree_sitter_bash", "language"),
    "kotlin": ("tree_sitter_kotlin", "language"),
    "swift": ("tree_sitter_swift", "language"),
}


@dataclass
class ImportInfo:
    """Represents an import statement."""

    module: str
    names: list[str] = field(default_factory=list)
    line: int = 0


@dataclass
class FunctionInfo:
    """Represents a function or method."""

    name: str
    line: int
    end_line: int
    params: str = ""
    return_type: str = ""
    exported: bool = False
    is_async: bool = False


@dataclass
class ClassInfo:
    """Represents a class, struct, or interface."""

    name: str
    line: int
    end_line: int
    kind: str = "class"  # class, struct, interface
    methods: list[FunctionInfo] = field(default_factory=list)


@dataclass
class FileOutline:
    """Complete outline of a source file."""

    file: str
    language: str
    parser: str  # "tree-sitter" or "regex"
    imports: list[ImportInfo] = field(default_factory=list)
    functions: list[FunctionInfo] = field(default_factory=list)
    classes: list[ClassInfo] = field(default_factory=list)


def detect_language(file_path: Path) -> str | None:
    """Detect language from file extension."""
    return EXTENSION_MAP.get(file_path.suffix.lower())


def get_parser(language: str):
    """Get tree-sitter parser for language, returns None if unavailable."""
    if language not in GRAMMAR_MODULES:
        return None

    module_name, func_name = GRAMMAR_MODULES[language]

    try:
        import importlib

        from tree_sitter import Language, Parser

        mod = importlib.import_module(module_name)
        lang_func = getattr(mod, func_name)
        lang = Language(lang_func())
        return Parser(lang)
    except (ImportError, AttributeError, OSError):
        return None


def node_text(node) -> str:
    """Extract text from a tree-sitter node."""
    return node.text.decode("utf-8") if node else ""


# --- Python Extractor ---


def extract_python(tree, source_bytes: bytes) -> FileOutline:
    """Extract outline from Python AST."""
    outline = FileOutline(file="", language="python", parser="tree-sitter")
    root = tree.root_node

    for child in root.children:
        if child.type == "import_statement":
            # import os, sys
            names = []
            for c in child.children:
                if c.type == "dotted_name":
                    names.append(node_text(c))
            if names:
                outline.imports.append(ImportInfo(module=names[0], names=names[1:], line=child.start_point[0] + 1))

        elif child.type == "import_from_statement":
            # from x import y, z
            module = ""
            names = []
            for c in child.children:
                if c.type == "dotted_name" and not module:
                    module = node_text(c)
                elif c.type == "dotted_name":
                    names.append(node_text(c))
                elif c.type == "aliased_import":
                    name_node = c.children[0] if c.children else None
                    if name_node:
                        names.append(node_text(name_node))
                elif c.type == "import_prefix":
                    module = node_text(c)
            outline.imports.append(ImportInfo(module=module, names=names, line=child.start_point[0] + 1))

        elif child.type == "function_definition":
            outline.functions.append(_extract_python_function(child))

        elif child.type == "decorated_definition":
            # Find the actual function/class under decorator
            for c in child.children:
                if c.type == "function_definition":
                    outline.functions.append(_extract_python_function(c, decorated_node=child))
                elif c.type == "class_definition":
                    outline.classes.append(_extract_python_class(c, decorated_node=child))

        elif child.type == "class_definition":
            outline.classes.append(_extract_python_class(child))

    return outline


def _extract_python_function(node, decorated_node=None) -> FunctionInfo:
    """Extract function info from a Python function_definition node."""
    name = ""
    params = ""
    return_type = ""
    is_async = False

    for c in node.children:
        if c.type == "identifier":
            name = node_text(c)
        elif c.type == "parameters":
            params = node_text(c)[1:-1]  # strip parens
        elif c.type == "type":
            return_type = node_text(c)
        elif c.type == "async":
            is_async = True

    start_node = decorated_node if decorated_node else node
    return FunctionInfo(
        name=name,
        line=start_node.start_point[0] + 1,
        end_line=node.end_point[0] + 1,
        params=params,
        return_type=return_type,
        is_async=is_async,
    )


def _extract_python_class(node, decorated_node=None) -> ClassInfo:
    """Extract class info from a Python class_definition node."""
    name = ""
    methods: list[FunctionInfo] = []

    for c in node.children:
        if c.type == "identifier":
            name = node_text(c)
        elif c.type == "block":
            for stmt in c.children:
                if stmt.type == "function_definition":
                    methods.append(_extract_python_function(stmt))
                elif stmt.type == "decorated_definition":
                    for dc in stmt.children:
                        if dc.type == "function_definition":
                            methods.append(_extract_python_function(dc, decorated_node=stmt))

    start_node = decorated_node if decorated_node else node
    return ClassInfo(
        name=name,
        line=start_node.start_point[0] + 1,
        end_line=node.end_point[0] + 1,
        methods=methods,
    )


# --- TypeScript/JavaScript Extractor ---


def extract_typescript(tree, source_bytes: bytes) -> FileOutline:
    """Extract outline from TypeScript/JavaScript AST."""
    outline = FileOutline(file="", language="typescript", parser="tree-sitter")
    root = tree.root_node

    for child in root.children:
        if child.type == "import_statement":
            _extract_ts_import(child, outline)

        elif child.type == "export_statement":
            for c in child.children:
                if c.type == "function_declaration":
                    func = _extract_ts_function(c)
                    func.exported = True
                    func.line = child.start_point[0] + 1
                    outline.functions.append(func)
                elif c.type == "class_declaration":
                    cls = _extract_ts_class(c)
                    cls.line = child.start_point[0] + 1
                    outline.classes.append(cls)

        elif child.type == "function_declaration":
            outline.functions.append(_extract_ts_function(child))

        elif child.type == "class_declaration":
            outline.classes.append(_extract_ts_class(child))

        elif child.type == "lexical_declaration":
            # const arrow = (x: number): number => x + 1
            for c in child.children:
                if c.type == "variable_declarator":
                    func = _try_extract_arrow_function(c, child)
                    if func:
                        outline.functions.append(func)

    return outline


def _extract_ts_import(node, outline: FileOutline) -> None:
    """Extract import info from TypeScript import_statement."""
    module = ""
    names: list[str] = []

    for c in node.children:
        if c.type == "string":
            module = node_text(c).strip("\"'")
        elif c.type == "import_clause":
            for ic in c.children:
                if ic.type == "named_imports":
                    for spec in ic.children:
                        if spec.type == "import_specifier":
                            name_node = spec.children[0] if spec.children else None
                            if name_node:
                                names.append(node_text(name_node))
                elif ic.type == "namespace_import":
                    # * as name
                    for ns in ic.children:
                        if ns.type == "identifier":
                            names.append(f"* as {node_text(ns)}")
                elif ic.type == "identifier":
                    names.append(node_text(ic))

    outline.imports.append(ImportInfo(module=module, names=names, line=node.start_point[0] + 1))


def _extract_ts_function(node) -> FunctionInfo:
    """Extract function info from TypeScript function_declaration."""
    name = ""
    params = ""
    return_type = ""
    is_async = False

    for c in node.children:
        if c.type == "identifier":
            name = node_text(c)
        elif c.type == "formal_parameters":
            params = node_text(c)[1:-1]
        elif c.type == "type_annotation":
            return_type = node_text(c).lstrip(": ")
        elif c.type == "async":
            is_async = True

    return FunctionInfo(
        name=name,
        line=node.start_point[0] + 1,
        end_line=node.end_point[0] + 1,
        params=params,
        return_type=return_type,
        is_async=is_async,
    )


def _extract_ts_class(node) -> ClassInfo:
    """Extract class info from TypeScript class_declaration."""
    name = ""
    methods: list[FunctionInfo] = []

    for c in node.children:
        if c.type == "type_identifier":
            name = node_text(c)
        elif c.type == "class_body":
            for member in c.children:
                if member.type == "method_definition":
                    methods.append(_extract_ts_method(member))

    return ClassInfo(
        name=name,
        line=node.start_point[0] + 1,
        end_line=node.end_point[0] + 1,
        methods=methods,
    )


def _extract_ts_method(node) -> FunctionInfo:
    """Extract method info from TypeScript method_definition."""
    name = ""
    params = ""
    return_type = ""
    is_async = False

    for c in node.children:
        if c.type == "property_identifier":
            name = node_text(c)
        elif c.type == "formal_parameters":
            params = node_text(c)[1:-1]
        elif c.type == "type_annotation":
            return_type = node_text(c).lstrip(": ")
        elif c.type == "async":
            is_async = True

    return FunctionInfo(
        name=name,
        line=node.start_point[0] + 1,
        end_line=node.end_point[0] + 1,
        params=params,
        return_type=return_type,
        is_async=is_async,
    )


def _try_extract_arrow_function(node, parent_node) -> FunctionInfo | None:
    """Try to extract an arrow function from a variable_declarator."""
    name = ""
    for c in node.children:
        if c.type == "identifier":
            name = node_text(c)
        elif c.type == "arrow_function":
            params = ""
            return_type = ""
            is_async = False
            for ac in c.children:
                if ac.type == "formal_parameters":
                    params = node_text(ac)[1:-1]
                elif ac.type == "type_annotation":
                    return_type = node_text(ac).lstrip(": ")
                elif ac.type == "async":
                    is_async = True
            return FunctionInfo(
                name=name,
                line=parent_node.start_point[0] + 1,
                end_line=parent_node.end_point[0] + 1,
                params=params,
                return_type=return_type,
                is_async=is_async,
            )
    return None


# --- Go Extractor ---


def extract_go(tree, source_bytes: bytes) -> FileOutline:
    """Extract outline from Go AST."""
    outline = FileOutline(file="", language="go", parser="tree-sitter")
    root = tree.root_node

    # Track structs/interfaces for method association
    type_map: dict[str, ClassInfo] = {}

    for child in root.children:
        if child.type == "import_declaration":
            _extract_go_imports(child, outline)

        elif child.type == "function_declaration":
            outline.functions.append(_extract_go_function(child))

        elif child.type == "method_declaration":
            receiver_type, method = _extract_go_method(child)
            if receiver_type in type_map:
                type_map[receiver_type].methods.append(method)
            else:
                # Method for a type not yet seen - add as standalone for now
                method.name = f"({receiver_type}).{method.name}"
                outline.functions.append(method)

        elif child.type == "type_declaration":
            for c in child.children:
                if c.type == "type_spec":
                    cls = _extract_go_type_spec(c)
                    if cls:
                        type_map[cls.name] = cls
                        outline.classes.append(cls)

    return outline


def _extract_go_imports(node, outline: FileOutline) -> None:
    """Extract imports from Go import_declaration."""
    for c in node.children:
        if c.type == "import_spec_list":
            for spec in c.children:
                if spec.type == "import_spec":
                    path = ""
                    for s in spec.children:
                        if s.type == "interpreted_string_literal":
                            path = node_text(s).strip('"')
                    if path:
                        outline.imports.append(ImportInfo(module=path, line=spec.start_point[0] + 1))
        elif c.type == "import_spec":
            path = ""
            for s in c.children:
                if s.type == "interpreted_string_literal":
                    path = node_text(s).strip('"')
            if path:
                outline.imports.append(ImportInfo(module=path, line=c.start_point[0] + 1))


def _extract_go_function(node) -> FunctionInfo:
    """Extract function info from Go function_declaration."""
    name = ""
    params = ""
    return_type = ""

    for c in node.children:
        if c.type == "identifier":
            name = node_text(c)
        elif c.type == "parameter_list":
            params = node_text(c)[1:-1]
        elif c.type in ("type_identifier", "pointer_type", "qualified_type", "parameter_list"):
            if name and not return_type:
                # This is the return type (comes after params)
                text = node_text(c)
                if (text.startswith("(") and c.type == "parameter_list") or c.type != "parameter_list":
                    return_type = text

    # Handle return type more carefully
    children = list(node.children)
    param_seen = False
    for c in children:
        if c.type == "parameter_list":
            if param_seen:
                return_type = node_text(c)
            param_seen = True
        elif param_seen and c.type not in ("block", "{", "}"):
            if c.type in ("type_identifier", "pointer_type", "qualified_type", "slice_type", "map_type", "array_type"):
                return_type = node_text(c)

    exported = name[:1].isupper() if name else False
    return FunctionInfo(
        name=name,
        line=node.start_point[0] + 1,
        end_line=node.end_point[0] + 1,
        params=params,
        return_type=return_type,
        exported=exported,
    )


def _extract_go_method(node) -> tuple[str, FunctionInfo]:
    """Extract method info from Go method_declaration. Returns (receiver_type, method)."""
    name = ""
    params = ""
    return_type = ""
    receiver_type = ""

    children = list(node.children)
    param_lists_seen = 0

    for c in children:
        if c.type == "parameter_list":
            param_lists_seen += 1
            if param_lists_seen == 1:
                # Receiver
                text = node_text(c)[1:-1]
                # Extract type from "s *Server" or "s Server"
                parts = text.split()
                if len(parts) >= 2:
                    receiver_type = parts[-1].lstrip("*")
                elif len(parts) == 1:
                    receiver_type = parts[0].lstrip("*")
            elif param_lists_seen == 2:
                params = node_text(c)[1:-1]
            else:
                # Third parameter_list = return tuple
                return_type = node_text(c)
        elif c.type == "field_identifier":
            name = node_text(c)
        elif param_lists_seen >= 2 and c.type in (
            "type_identifier",
            "pointer_type",
            "qualified_type",
            "slice_type",
            "map_type",
            "array_type",
        ):
            return_type = node_text(c)

    exported = name[:1].isupper() if name else False
    method = FunctionInfo(
        name=name,
        line=node.start_point[0] + 1,
        end_line=node.end_point[0] + 1,
        params=params,
        return_type=return_type,
        exported=exported,
    )
    return receiver_type, method


def _extract_go_type_spec(node) -> ClassInfo | None:
    """Extract struct/interface from Go type_spec."""
    name = ""
    kind = "class"

    for c in node.children:
        if c.type == "type_identifier":
            name = node_text(c)
        elif c.type == "struct_type":
            kind = "struct"
        elif c.type == "interface_type":
            kind = "interface"

    if not name:
        return None

    return ClassInfo(
        name=name,
        line=node.start_point[0] + 1,
        end_line=node.end_point[0] + 1,
        kind=kind,
    )


# --- PHP Extractor ---


def extract_php(tree, source_bytes: bytes) -> FileOutline:
    """Extract outline from PHP AST."""
    outline = FileOutline(file="", language="php", parser="tree-sitter")
    root = tree.root_node

    _walk_php_node(root, outline)
    return outline


def _walk_php_node(node, outline: FileOutline) -> None:
    """Walk PHP tree extracting functions and classes."""
    for child in node.children:
        if child.type == "function_definition":
            outline.functions.append(_extract_php_function(child))
        elif child.type == "class_declaration":
            outline.classes.append(_extract_php_class(child))
        elif child.type == "namespace_use_declaration":
            _extract_php_use(child, outline)
        elif child.type in ("program", "php_tag", "expression_statement", "compound_statement"):
            _walk_php_node(child, outline)


def _extract_php_use(node, outline: FileOutline) -> None:
    """Extract use statement from PHP."""
    for c in node.children:
        if c.type == "namespace_use_clause":
            name = ""
            for nc in c.children:
                if nc.type == "qualified_name":
                    name = node_text(nc)
            if name:
                outline.imports.append(ImportInfo(module=name, line=node.start_point[0] + 1))


def _extract_php_function(node) -> FunctionInfo:
    """Extract function from PHP function_definition."""
    name = ""
    params = ""
    return_type = ""

    for c in node.children:
        if c.type == "name":
            name = node_text(c)
        elif c.type == "formal_parameters":
            params = node_text(c)[1:-1]
        elif c.type in ("union_type", "named_type", "primitive_type", "nullable_type"):
            return_type = node_text(c)

    return FunctionInfo(
        name=name,
        line=node.start_point[0] + 1,
        end_line=node.end_point[0] + 1,
        params=params,
        return_type=return_type,
    )


def _extract_php_class(node) -> ClassInfo:
    """Extract class from PHP class_declaration."""
    name = ""
    methods: list[FunctionInfo] = []

    for c in node.children:
        if c.type == "name":
            name = node_text(c)
        elif c.type == "declaration_list":
            for member in c.children:
                if member.type == "method_declaration":
                    methods.append(_extract_php_method(member))

    return ClassInfo(
        name=name,
        line=node.start_point[0] + 1,
        end_line=node.end_point[0] + 1,
        methods=methods,
    )


def _extract_php_method(node) -> FunctionInfo:
    """Extract method from PHP method_declaration."""
    name = ""
    params = ""
    return_type = ""

    for c in node.children:
        if c.type == "name":
            name = node_text(c)
        elif c.type == "formal_parameters":
            params = node_text(c)[1:-1]
        elif c.type in ("union_type", "named_type", "primitive_type", "nullable_type"):
            return_type = node_text(c)

    return FunctionInfo(
        name=name,
        line=node.start_point[0] + 1,
        end_line=node.end_point[0] + 1,
        params=params,
        return_type=return_type,
    )


# --- Kotlin Extractor ---


def extract_kotlin(tree, source_bytes: bytes) -> FileOutline:
    """Extract outline from Kotlin AST."""
    outline = FileOutline(file="", language="kotlin", parser="tree-sitter")
    root = tree.root_node

    _walk_kotlin_node(root, outline, top_level=True)
    return outline


def _walk_kotlin_node(node, outline: FileOutline, top_level: bool = False) -> None:
    """Walk Kotlin tree extracting functions and classes."""
    for child in node.children:
        if child.type == "function_declaration" and top_level:
            outline.functions.append(_extract_kotlin_function(child))
        elif child.type == "class_declaration" and top_level:
            outline.classes.append(_extract_kotlin_class(child))
        elif child.type == "import_list":
            for imp in child.children:
                if imp.type == "import_header":
                    _extract_kotlin_import(imp, outline)
        elif child.type == "import_header":
            _extract_kotlin_import(child, outline)
        elif child.type in ("source_file",):
            _walk_kotlin_node(child, outline, top_level=True)


def _extract_kotlin_import(node, outline: FileOutline) -> None:
    """Extract import from Kotlin."""
    for c in node.children:
        if c.type == "identifier":
            outline.imports.append(ImportInfo(module=node_text(c), line=node.start_point[0] + 1))
            break


def _extract_kotlin_function(node) -> FunctionInfo:
    """Extract function from Kotlin function_declaration."""
    name = ""
    params = ""
    return_type = ""

    for c in node.children:
        if c.type in ("simple_identifier", "identifier") and not name:
            name = node_text(c)
        elif c.type == "function_value_parameters":
            params = node_text(c)[1:-1]
        elif c.type == "user_type":
            return_type = node_text(c)

    return FunctionInfo(
        name=name,
        line=node.start_point[0] + 1,
        end_line=node.end_point[0] + 1,
        params=params,
        return_type=return_type,
    )


def _extract_kotlin_class(node) -> ClassInfo:
    """Extract class from Kotlin class_declaration."""
    name = ""
    methods: list[FunctionInfo] = []

    for c in node.children:
        if c.type in ("type_identifier", "identifier") and not name:
            name = node_text(c)
        elif c.type == "class_body":
            for member in c.children:
                if member.type == "function_declaration":
                    methods.append(_extract_kotlin_function(member))

    return ClassInfo(
        name=name,
        line=node.start_point[0] + 1,
        end_line=node.end_point[0] + 1,
        methods=methods,
    )


# --- Swift Extractor ---


def extract_swift(tree, source_bytes: bytes) -> FileOutline:
    """Extract outline from Swift AST."""
    outline = FileOutline(file="", language="swift", parser="tree-sitter")
    root = tree.root_node

    _walk_swift_node(root, outline, top_level=True)
    return outline


def _walk_swift_node(node, outline: FileOutline, top_level: bool = False) -> None:
    """Walk Swift tree extracting functions and classes."""
    for child in node.children:
        if child.type == "function_declaration" and top_level:
            outline.functions.append(_extract_swift_function(child))
        elif child.type == "class_declaration" and top_level:
            outline.classes.append(_extract_swift_class(child))
        elif child.type == "protocol_declaration" and top_level:
            outline.classes.append(_extract_swift_class(child, kind="interface"))
        elif child.type == "import_declaration":
            _extract_swift_import(child, outline)
        elif child.type in ("source_file",):
            _walk_swift_node(child, outline, top_level=True)


def _extract_swift_import(node, outline: FileOutline) -> None:
    """Extract import from Swift."""
    text = node_text(node)
    parts = text.split()
    if len(parts) >= 2:
        outline.imports.append(ImportInfo(module=parts[1], line=node.start_point[0] + 1))


def _extract_swift_function(node) -> FunctionInfo:
    """Extract function from Swift function_declaration."""
    name = ""
    params = ""
    return_type = ""

    text = node_text(node)
    # Parse "func name(params) -> ReturnType"
    match = re.match(r"func\s+(\w+)\s*\(([^)]*)\)(?:\s*->\s*(\S+))?", text)
    if match:
        name = match.group(1)
        params = match.group(2)
        return_type = match.group(3) or ""

    return FunctionInfo(
        name=name,
        line=node.start_point[0] + 1,
        end_line=node.end_point[0] + 1,
        params=params,
        return_type=return_type,
    )


def _extract_swift_class(node, kind: str = "class") -> ClassInfo:
    """Extract class from Swift class_declaration."""
    name = ""
    methods: list[FunctionInfo] = []

    text = node_text(node)
    # Extract name from first line
    first_line = text.split("\n")[0]
    match = re.match(r"(?:class|struct|protocol|enum)\s+(\w+)", first_line)
    if match:
        name = match.group(1)

    # Walk children for methods
    for child in node.children:
        if child.type == "class_body":
            for member in child.children:
                if member.type == "function_declaration":
                    methods.append(_extract_swift_function(member))

    return ClassInfo(
        name=name,
        line=node.start_point[0] + 1,
        end_line=node.end_point[0] + 1,
        kind=kind,
        methods=methods,
    )


# --- Bash Extractor ---


def extract_bash(tree, source_bytes: bytes) -> FileOutline:
    """Extract outline from Bash AST."""
    outline = FileOutline(file="", language="bash", parser="tree-sitter")
    root = tree.root_node

    for child in root.children:
        if child.type == "function_definition":
            name = ""
            for c in child.children:
                if c.type == "word":
                    name = node_text(c)
            if name:
                outline.functions.append(
                    FunctionInfo(
                        name=name,
                        line=child.start_point[0] + 1,
                        end_line=child.end_point[0] + 1,
                    )
                )

    return outline


# --- VB6 Regex Parser ---


def extract_vb6(source: str) -> FileOutline:
    """Extract outline from VB6 source using regex parsing."""
    outline = FileOutline(file="", language="vb6", parser="regex")

    lines = source.split("\n")
    # Pattern for Sub/Function/Property declarations
    decl_pattern = re.compile(
        r"^(Public |Private |Friend )?(Sub|Function|Property (Get|Let|Set)) (\w+)\s*\(([^)]*)\)", re.IGNORECASE
    )
    end_pattern = re.compile(r"^End (Sub|Function|Property)", re.IGNORECASE)

    current_class: ClassInfo | None = None
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Class detection (for .cls files the class name is in header)
        if stripped.upper().startswith("ATTRIBUTE VB_NAME"):
            match = re.search(r'"([^"]+)"', stripped)
            if match:
                current_class = ClassInfo(
                    name=match.group(1),
                    line=1,
                    end_line=len(lines),
                )
                outline.classes.append(current_class)

        # Function/Sub/Property declarations
        match = decl_pattern.match(stripped)
        if match:
            visibility = (match.group(1) or "").strip()
            kind = match.group(2)
            name = match.group(4)
            params = match.group(5)

            start_line = i + 1

            # Find matching End
            end_line = start_line
            j = i + 1
            while j < len(lines):
                if end_pattern.match(lines[j].strip()):
                    end_line = j + 1
                    break
                j += 1
            else:
                end_line = len(lines)

            func = FunctionInfo(
                name=name,
                line=start_line,
                end_line=end_line,
                params=params,
                exported=visibility.lower() == "public",
            )

            if current_class:
                current_class.methods.append(func)
            else:
                outline.functions.append(func)

            i = j + 1
            continue

        i += 1

    return outline


# --- Regex Fallback Parsers ---


def regex_extract_python(source: str) -> FileOutline:
    """Regex fallback for Python."""
    outline = FileOutline(file="", language="python", parser="regex")
    lines = source.split("\n")

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Imports
        if stripped.startswith("import "):
            module = stripped[7:].split(" as ")[0].strip()
            outline.imports.append(ImportInfo(module=module, line=i + 1))
        elif stripped.startswith("from "):
            match = re.match(r"from ([\w.]+) import (.+)", stripped)
            if match:
                module = match.group(1)
                names = [n.strip().split(" as ")[0] for n in match.group(2).split(",")]
                outline.imports.append(ImportInfo(module=module, names=names, line=i + 1))

        # Functions
        match = re.match(r"^(async )?def (\w+)\(([^)]*)\)(?:\s*->\s*(.+?))?:", stripped)
        if match:
            outline.functions.append(
                FunctionInfo(
                    name=match.group(2),
                    line=i + 1,
                    end_line=i + 1,  # Cannot determine end with regex
                    params=match.group(3),
                    return_type=match.group(4) or "",
                    is_async=bool(match.group(1)),
                )
            )

        # Classes
        match = re.match(r"^class (\w+)", stripped)
        if match:
            outline.classes.append(ClassInfo(name=match.group(1), line=i + 1, end_line=i + 1))

    return outline


def regex_extract_go(source: str) -> FileOutline:
    """Regex fallback for Go."""
    outline = FileOutline(file="", language="go", parser="regex")
    lines = source.split("\n")

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Functions
        match = re.match(r"func (\w+)\(([^)]*)\)(.+)?\s*\{", stripped)
        if match:
            outline.functions.append(
                FunctionInfo(
                    name=match.group(1),
                    line=i + 1,
                    end_line=i + 1,
                    params=match.group(2),
                    return_type=(match.group(3) or "").strip(),
                    exported=match.group(1)[0].isupper(),
                )
            )

        # Methods
        match = re.match(r"func \((\w+)\s+\*?(\w+)\)\s*(\w+)\(([^)]*)\)(.+)?\s*\{", stripped)
        if match:
            outline.functions.append(
                FunctionInfo(
                    name=f"({match.group(2)}).{match.group(3)}",
                    line=i + 1,
                    end_line=i + 1,
                    params=match.group(4),
                    return_type=(match.group(5) or "").strip(),
                    exported=match.group(3)[0].isupper(),
                )
            )

        # Types
        match = re.match(r"type (\w+) (struct|interface)", stripped)
        if match:
            outline.classes.append(ClassInfo(name=match.group(1), line=i + 1, end_line=i + 1, kind=match.group(2)))

    return outline


def regex_extract_typescript(source: str) -> FileOutline:
    """Regex fallback for TypeScript/JavaScript."""
    outline = FileOutline(file="", language="typescript", parser="regex")
    lines = source.split("\n")

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Imports
        match = re.match(r"import\s+(?:\{([^}]+)\}|(\*\s+as\s+\w+)|\w+)\s+from\s+['\"]([^'\"]+)['\"]", stripped)
        if match:
            names = []
            if match.group(1):
                names = [n.strip() for n in match.group(1).split(",")]
            elif match.group(2):
                names = [match.group(2)]
            outline.imports.append(ImportInfo(module=match.group(3), names=names, line=i + 1))

        # Functions
        match = re.match(r"(export\s+)?(async\s+)?function\s+(\w+)\s*\(([^)]*)\)(?:\s*:\s*(.+?))?\s*\{", stripped)
        if match:
            outline.functions.append(
                FunctionInfo(
                    name=match.group(3),
                    line=i + 1,
                    end_line=i + 1,
                    params=match.group(4),
                    return_type=match.group(5) or "",
                    exported=bool(match.group(1)),
                    is_async=bool(match.group(2)),
                )
            )

        # Classes
        match = re.match(r"(export\s+)?class\s+(\w+)", stripped)
        if match:
            outline.classes.append(ClassInfo(name=match.group(2), line=i + 1, end_line=i + 1))

    return outline


def regex_extract_generic(source: str, language: str) -> FileOutline:
    """Generic regex fallback for unsupported languages."""
    outline = FileOutline(file="", language=language, parser="regex")
    lines = source.split("\n")

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Try common function patterns
        match = re.match(
            r"(?:pub(?:lic)?|private|protected|internal)?\s*(?:static\s+)?(?:fun|func|fn|def)\s+(\w+)", stripped
        )
        if match:
            outline.functions.append(FunctionInfo(name=match.group(1), line=i + 1, end_line=i + 1))

        # Try common class patterns
        match = re.match(
            r"(?:pub(?:lic)?|private|internal)?\s*(?:class|struct|interface|protocol|enum)\s+(\w+)", stripped
        )
        if match:
            outline.classes.append(ClassInfo(name=match.group(1), line=i + 1, end_line=i + 1))

    return outline


# --- Extractor dispatch ---

TREE_SITTER_EXTRACTORS: dict[str, Any] = {
    "python": extract_python,
    "javascript": extract_typescript,  # Same AST structure
    "typescript": extract_typescript,
    "go": extract_go,
    "php": extract_php,
    "kotlin": extract_kotlin,
    "swift": extract_swift,
    "bash": extract_bash,
}

REGEX_EXTRACTORS: dict[str, Any] = {
    "python": regex_extract_python,
    "go": regex_extract_go,
    "typescript": regex_extract_typescript,
    "javascript": regex_extract_typescript,
}


def parse_file(file_path: Path) -> FileOutline:
    """Parse a file and return its structural outline.

    Args:
        file_path: Path to the source file.

    Returns:
        FileOutline with extracted structure.

    Raises:
        ValueError: If language cannot be detected.
        OSError: If file cannot be read.
    """
    language = detect_language(file_path)
    if not language:
        raise ValueError(f"Cannot detect language for: {file_path}")

    source = file_path.read_text(encoding="utf-8", errors="replace")

    # VB6 always uses regex
    if language == "vb6":
        outline = extract_vb6(source)
        outline.file = str(file_path)
        return outline

    # Try tree-sitter first
    parser = get_parser(language)
    if parser:
        source_bytes = source.encode("utf-8")
        tree = parser.parse(source_bytes)
        extractor = TREE_SITTER_EXTRACTORS.get(language)
        if extractor:
            outline = extractor(tree, source_bytes)
            outline.file = str(file_path)
            outline.language = language
            return outline

    # Fallback to regex
    regex_extractor = REGEX_EXTRACTORS.get(language, lambda s: regex_extract_generic(s, language))
    outline = regex_extractor(source)
    outline.file = str(file_path)
    outline.language = language
    return outline


# --- Output Formatters ---


def outline_to_dict(outline: FileOutline) -> dict[str, Any]:
    """Convert FileOutline to JSON-serializable dict."""
    result: dict[str, Any] = {
        "file": outline.file,
        "language": outline.language,
        "parser": outline.parser,
    }

    if outline.imports:
        result["imports"] = [asdict(imp) for imp in outline.imports]

    if outline.functions:
        result["functions"] = [asdict(f) for f in outline.functions]

    if outline.classes:
        classes = []
        for cls in outline.classes:
            cls_dict: dict[str, Any] = {
                "name": cls.name,
                "line": cls.line,
                "end_line": cls.end_line,
                "kind": cls.kind,
            }
            if cls.methods:
                cls_dict["methods"] = [asdict(m) for m in cls.methods]
            classes.append(cls_dict)
        result["classes"] = classes

    return result


def format_text_outline(outline: FileOutline) -> str:
    """Format outline as compact text representation."""
    lines: list[str] = []
    lines.append(f"{outline.file} ({outline.language}, {outline.parser})")

    for imp in outline.imports:
        if imp.names:
            lines.append(f"  import {imp.module} {{{', '.join(imp.names)}}}  [L{imp.line}]")
        else:
            lines.append(f"  import {imp.module}  [L{imp.line}]")

    for cls in outline.classes:
        kind_prefix = cls.kind if cls.kind != "class" else "class"
        lines.append(f"  {kind_prefix} {cls.name}  [L{cls.line}-{cls.end_line}]")
        for method in cls.methods:
            ret = f": {method.return_type}" if method.return_type else ""
            async_prefix = "async " if method.is_async else ""
            lines.append(f"    {async_prefix}.{method.name}({method.params}){ret}  [L{method.line}-{method.end_line}]")

    for func in outline.functions:
        ret = f": {func.return_type}" if func.return_type else ""
        export = "export " if func.exported else ""
        async_prefix = "async " if func.is_async else ""
        lines.append(
            f"  {export}{async_prefix}function {func.name}({func.params}){ret}  [L{func.line}-{func.end_line}]"
        )

    return "\n".join(lines)


# --- CLI ---


def collect_files(path: Path, recursive: bool) -> list[Path]:
    """Collect source files from path (file or directory)."""
    if path.is_file():
        return [path]

    if path.is_dir() and recursive:
        files = []
        for ext in EXTENSION_MAP:
            files.extend(path.rglob(f"*{ext}"))
        return sorted(files)

    if path.is_dir():
        files = []
        for ext in EXTENSION_MAP:
            files.extend(path.glob(f"*{ext}"))
        return sorted(files)

    return []


def main() -> int:
    """Main entry point for code-outline CLI."""
    parser = argparse.ArgumentParser(
        description="Extract structural outlines from source files using tree-sitter.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("path", type=Path, help="Source file or directory to analyze")
    parser.add_argument(
        "--format",
        choices=["json", "outline"],
        default="json",
        help="Output format (default: json)",
    )
    parser.add_argument("--recursive", "-r", action="store_true", help="Recursively process directories")

    args = parser.parse_args()

    if not args.path.exists():
        print(f"Error: path does not exist: {args.path}", file=sys.stderr)
        return 2

    files = collect_files(args.path, args.recursive)
    if not files:
        print(f"Error: no supported source files found in: {args.path}", file=sys.stderr)
        return 1

    results: list[dict[str, Any]] = []
    errors: list[str] = []

    for file_path in files:
        try:
            outline = parse_file(file_path)
            if args.format == "outline":
                print(format_text_outline(outline))
                if file_path != files[-1]:
                    print()
            else:
                results.append(outline_to_dict(outline))
        except (ValueError, OSError) as e:
            errors.append(f"{file_path}: {e}")

    if args.format == "json":
        if len(results) == 1:
            print(json.dumps(results[0], indent=2))
        else:
            print(json.dumps(results, indent=2))

    if errors:
        for err in errors:
            print(f"Warning: {err}", file=sys.stderr)

    return 1 if not results and errors else 0


if __name__ == "__main__":
    sys.exit(main())
