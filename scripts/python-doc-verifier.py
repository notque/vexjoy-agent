#!/usr/bin/env python3
"""
Deterministic documentation verification for Python source files.

Validates generated documentation against the actual Python source code to
ensure accuracy, completeness, and structural quality. Used by the
python-doc-generator skill's VERIFY phase.

Usage:
    python3 scripts/python-doc-verifier.py verify --source FILE.py --doc DOC.md
    python3 scripts/python-doc-verifier.py extract --source FILE.py
    python3 scripts/python-doc-verifier.py check-structure --doc DOC.md

Exit codes:
    0 = all checks pass
    1 = verification failures found
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# =============================================================================
# Data Structures
# =============================================================================


@dataclass
class FunctionInfo:
    """Extracted information about a Python function or method."""

    name: str
    lineno: int
    args: list[str]
    returns: str | None
    decorators: list[str]
    docstring: str | None
    is_method: bool = False
    is_private: bool = False
    is_async: bool = False

    @property
    def is_public(self) -> bool:
        return not self.name.startswith("_")


@dataclass
class ClassInfo:
    """Extracted information about a Python class."""

    name: str
    lineno: int
    bases: list[str]
    docstring: str | None
    methods: list[FunctionInfo]
    is_dataclass: bool = False

    @property
    def public_methods(self) -> list[FunctionInfo]:
        return [m for m in self.methods if m.is_public]


@dataclass
class ModuleInfo:
    """Extracted information about a Python module."""

    path: str
    docstring: str | None
    imports: list[str]
    global_constants: list[str]
    functions: list[FunctionInfo]
    classes: list[ClassInfo]
    has_main: bool = False
    has_argparse: bool = False
    has_cli_entry: bool = False
    shebang: bool = False
    total_lines: int = 0

    @property
    def public_functions(self) -> list[FunctionInfo]:
        return [f for f in self.functions if f.is_public]

    @property
    def all_public_names(self) -> list[str]:
        names = [f.name for f in self.public_functions]
        for cls in self.classes:
            names.append(cls.name)
            names.extend(m.name for m in cls.public_methods)
        return names


@dataclass
class VerificationResult:
    """Result of verifying documentation against source."""

    source_file: str
    doc_file: str
    passed: bool
    score: float  # 0.0 to 1.0
    checks: list[dict[str, Any]]
    missing_functions: list[str]
    missing_classes: list[str]
    missing_constants: list[str]
    undocumented_args: list[str]
    structure_issues: list[str]
    accuracy_issues: list[str]
    summary: str


# =============================================================================
# Source Code Extraction (AST-based)
# =============================================================================


def extract_module_info(source_path: Path) -> ModuleInfo:
    """Parse a Python file and extract all documentable elements via AST."""
    content = source_path.read_text(encoding="utf-8", errors="replace")
    lines = content.splitlines()

    try:
        tree = ast.parse(content, filename=str(source_path))
    except SyntaxError as e:
        return ModuleInfo(
            path=str(source_path),
            docstring=f"SYNTAX ERROR: {e}",
            imports=[],
            global_constants=[],
            functions=[],
            classes=[],
            total_lines=len(lines),
        )

    module_doc = ast.get_docstring(tree)
    imports = _extract_imports(tree)
    constants = _extract_constants(tree, lines)
    functions = _extract_functions(tree)
    classes = _extract_classes(tree)
    has_main = _has_main_guard(content)
    has_argparse = "argparse" in content
    has_cli_entry = has_main and has_argparse
    shebang = content.startswith("#!")

    return ModuleInfo(
        path=str(source_path),
        docstring=module_doc,
        imports=imports,
        global_constants=constants,
        functions=functions,
        classes=classes,
        has_main=has_main,
        has_argparse=has_argparse,
        has_cli_entry=has_cli_entry,
        shebang=shebang,
        total_lines=len(lines),
    )


def _extract_imports(tree: ast.Module) -> list[str]:
    """Extract import statements."""
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                imports.append(f"{module}.{alias.name}")
    return imports


def _extract_constants(tree: ast.Module, lines: list[str]) -> list[str]:
    """Extract module-level constants (UPPER_CASE assignments)."""
    constants = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id.isupper():
                    constants.append(target.id)
    return constants


def _extract_functions(tree: ast.Module) -> list[FunctionInfo]:
    """Extract top-level function definitions."""
    functions = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append(_parse_function(node))
    return functions


def _extract_classes(tree: ast.Module) -> list[ClassInfo]:
    """Extract class definitions with their methods."""
    classes = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef):
            classes.append(_parse_class(node))
    return classes


def _parse_function(node: ast.FunctionDef | ast.AsyncFunctionDef) -> FunctionInfo:
    """Parse a function definition into FunctionInfo."""
    args = []
    for arg in node.args.args:
        if arg.arg != "self":
            args.append(arg.arg)

    # Get return annotation if present
    returns = None
    if node.returns:
        returns = ast.unparse(node.returns)

    decorators = []
    for dec in node.decorator_list:
        if isinstance(dec, ast.Name):
            decorators.append(dec.id)
        elif isinstance(dec, ast.Attribute):
            decorators.append(ast.unparse(dec))
        else:
            decorators.append(ast.unparse(dec))

    return FunctionInfo(
        name=node.name,
        lineno=node.lineno,
        args=args,
        returns=returns,
        decorators=decorators,
        docstring=ast.get_docstring(node),
        is_private=node.name.startswith("_"),
        is_async=isinstance(node, ast.AsyncFunctionDef),
    )


def _parse_class(node: ast.ClassDef) -> ClassInfo:
    """Parse a class definition into ClassInfo."""
    bases = [ast.unparse(b) for b in node.bases]

    methods = []
    for item in node.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            func = _parse_function(item)
            func.is_method = True
            methods.append(func)

    is_dataclass = any(
        (isinstance(d, ast.Name) and d.id == "dataclass") or (isinstance(d, ast.Attribute) and d.attr == "dataclass")
        for d in node.decorator_list
    )

    return ClassInfo(
        name=node.name,
        lineno=node.lineno,
        bases=bases,
        docstring=ast.get_docstring(node),
        methods=methods,
        is_dataclass=is_dataclass,
    )


def _has_main_guard(content: str) -> bool:
    """Check if file has if __name__ == '__main__' guard."""
    return bool(re.search(r'if\s+__name__\s*==\s*["\']__main__["\']', content))


# =============================================================================
# Documentation Verification
# =============================================================================


def verify_documentation(source_path: Path, doc_path: Path) -> VerificationResult:
    """Verify documentation against source code."""
    module = extract_module_info(source_path)
    doc_content = doc_path.read_text(encoding="utf-8", errors="replace")
    doc_lower = doc_content.lower()

    checks: list[dict[str, Any]] = []
    missing_functions: list[str] = []
    missing_classes: list[str] = []
    missing_constants: list[str] = []
    undocumented_args: list[str] = []
    structure_issues: list[str] = []
    accuracy_issues: list[str] = []

    # --- Check 1: All public functions mentioned ---
    for func in module.public_functions:
        mentioned = func.name.lower() in doc_lower or func.name in doc_content
        if not mentioned:
            missing_functions.append(func.name)
        checks.append(
            {
                "check": f"function_{func.name}_mentioned",
                "passed": mentioned,
                "detail": f"Public function '{func.name}' {'found' if mentioned else 'MISSING'} in docs",
            }
        )

    # --- Check 2: All classes mentioned ---
    for cls in module.classes:
        mentioned = cls.name.lower() in doc_lower or cls.name in doc_content
        if not mentioned:
            missing_classes.append(cls.name)
        checks.append(
            {
                "check": f"class_{cls.name}_mentioned",
                "passed": mentioned,
                "detail": f"Class '{cls.name}' {'found' if mentioned else 'MISSING'} in docs",
            }
        )

    # --- Check 3: Public class methods mentioned ---
    for cls in module.classes:
        for method in cls.public_methods:
            mentioned = method.name.lower() in doc_lower or method.name in doc_content
            if not mentioned:
                missing_functions.append(f"{cls.name}.{method.name}")
            checks.append(
                {
                    "check": f"method_{cls.name}_{method.name}_mentioned",
                    "passed": mentioned,
                    "detail": f"Method '{cls.name}.{method.name}' {'found' if mentioned else 'MISSING'} in docs",
                }
            )

    # --- Check 4: Module-level constants mentioned ---
    for const in module.global_constants:
        mentioned = const in doc_content
        if not mentioned:
            missing_constants.append(const)
        checks.append(
            {
                "check": f"constant_{const}_mentioned",
                "passed": mentioned,
                "detail": f"Constant '{const}' {'found' if mentioned else 'MISSING'} in docs",
            }
        )

    # --- Check 5: Function arguments documented ---
    for func in module.public_functions:
        if func.name in doc_content:
            for arg in func.args:
                if arg in ("self", "cls"):
                    continue
                mentioned = arg in doc_content
                if not mentioned:
                    undocumented_args.append(f"{func.name}({arg})")
                checks.append(
                    {
                        "check": f"arg_{func.name}_{arg}",
                        "passed": mentioned,
                        "detail": f"Arg '{arg}' of '{func.name}' {'found' if mentioned else 'MISSING'} in docs",
                    }
                )

    # --- Check 6: CLI usage documented (if applicable) ---
    if module.has_cli_entry:
        has_usage = any(kw in doc_lower for kw in ["usage", "command", "cli", "arguments", "python3 scripts/"])
        checks.append(
            {
                "check": "cli_usage_documented",
                "passed": has_usage,
                "detail": "CLI usage section " + ("found" if has_usage else "MISSING"),
            }
        )
        if not has_usage:
            structure_issues.append("Script has CLI entry point but docs lack usage section")

    # --- Check 7: Structure quality ---
    has_headers = bool(re.findall(r"^#{1,3}\s+\w", doc_content, re.MULTILINE))
    has_overview = any(kw in doc_lower for kw in ["overview", "purpose", "summary", "description"])
    has_examples = any(kw in doc_lower for kw in ["example", "```", "usage"])

    if not has_headers:
        structure_issues.append("No markdown headers found")
    if not has_overview:
        structure_issues.append("No overview/purpose section")
    if not has_examples:
        structure_issues.append("No examples or code blocks")

    checks.append(
        {
            "check": "has_headers",
            "passed": has_headers,
            "detail": "Markdown headers " + ("present" if has_headers else "MISSING"),
        }
    )
    checks.append(
        {
            "check": "has_overview",
            "passed": has_overview,
            "detail": "Overview section " + ("present" if has_overview else "MISSING"),
        }
    )
    checks.append(
        {
            "check": "has_examples",
            "passed": has_examples,
            "detail": "Examples/code blocks " + ("present" if has_examples else "MISSING"),
        }
    )

    # --- Check 8: Accuracy spot-checks ---
    # Verify function signatures mentioned in docs actually match source
    for func in module.public_functions:
        # Look for the function signature pattern in docs
        sig_pattern = re.compile(rf"{func.name}\s*\([^)]*\)", re.IGNORECASE)
        matches = sig_pattern.findall(doc_content)
        for match in matches:
            # Extract arg names from doc signature
            doc_args = re.findall(r"\b(\w+)\b", match)
            doc_args = [a for a in doc_args if a != func.name]
            # Check for args in docs that don't exist in source
            for da in doc_args:
                if da not in func.args and da not in ("self", "cls", "args", "kwargs"):
                    # Only flag if it looks like a parameter name
                    if (
                        da.islower()
                        and len(da) > 1
                        and da not in ("str", "int", "bool", "list", "dict", "none", "true", "false", "optional")
                    ):
                        accuracy_issues.append(
                            f"Doc mentions arg '{da}' for {func.name} but it's not in source signature"
                        )

    # --- Compute score ---
    total_checks = len(checks)
    passed_checks = sum(1 for c in checks if c["passed"])
    score = passed_checks / total_checks if total_checks > 0 else 0.0

    # Penalize for structural and accuracy issues
    penalty = len(structure_issues) * 0.05 + len(accuracy_issues) * 0.1
    score = max(0.0, score - penalty)

    overall_passed = score >= 0.7 and len(accuracy_issues) == 0

    # Build summary
    summary_parts = [
        f"Score: {score:.1%} ({passed_checks}/{total_checks} checks passed)",
    ]
    if missing_functions:
        summary_parts.append(f"Missing functions: {', '.join(missing_functions)}")
    if missing_classes:
        summary_parts.append(f"Missing classes: {', '.join(missing_classes)}")
    if missing_constants:
        summary_parts.append(f"Missing constants: {', '.join(missing_constants)}")
    if structure_issues:
        summary_parts.append(f"Structure issues: {'; '.join(structure_issues)}")
    if accuracy_issues:
        summary_parts.append(f"Accuracy issues: {'; '.join(accuracy_issues)}")

    return VerificationResult(
        source_file=str(source_path),
        doc_file=str(doc_path),
        passed=overall_passed,
        score=score,
        checks=checks,
        missing_functions=missing_functions,
        missing_classes=missing_classes,
        missing_constants=missing_constants,
        undocumented_args=undocumented_args,
        structure_issues=structure_issues,
        accuracy_issues=accuracy_issues,
        summary="\n".join(summary_parts),
    )


def check_doc_structure(doc_path: Path) -> dict[str, Any]:
    """Check documentation structure quality without source comparison."""
    content = doc_path.read_text(encoding="utf-8", errors="replace")
    content_lower = content.lower()

    issues = []
    sections_found = re.findall(r"^(#{1,3})\s+(.+)", content, re.MULTILINE)
    headers = [h[1].strip() for h in sections_found]

    expected_sections = [
        ("overview", ["overview", "purpose", "summary", "description", "about"]),
        ("api_reference", ["api", "functions", "methods", "classes", "interface", "reference"]),
        ("examples", ["example", "usage", "getting started", "quick start"]),
    ]

    for section_name, keywords in expected_sections:
        found = any(any(kw in h.lower() for kw in keywords) for h in headers)
        if not found:
            found = any(kw in content_lower for kw in keywords)
        if not found:
            issues.append(f"Missing recommended section: {section_name}")

    # Check for code blocks
    code_blocks = re.findall(r"```\w*\n.*?```", content, re.DOTALL)
    if not code_blocks:
        issues.append("No code blocks found")

    # Check reasonable length
    word_count = len(content.split())
    if word_count < 100:
        issues.append(f"Very short ({word_count} words) -- may be incomplete")
    elif word_count > 10000:
        issues.append(f"Very long ({word_count} words) -- may need trimming")

    return {
        "file": str(doc_path),
        "headers": headers,
        "code_blocks": len(code_blocks),
        "word_count": word_count,
        "issues": issues,
        "passed": len(issues) == 0,
    }


# =============================================================================
# CLI
# =============================================================================


def cmd_extract(args: argparse.Namespace) -> int:
    """Extract documentable elements from a Python source file."""
    source_path = Path(args.source)
    if not source_path.exists():
        print(json.dumps({"error": f"File not found: {source_path}"}))
        return 1

    module = extract_module_info(source_path)

    output = {
        "path": module.path,
        "total_lines": module.total_lines,
        "module_docstring": module.docstring,
        "has_main": module.has_main,
        "has_argparse": module.has_argparse,
        "has_cli_entry": module.has_cli_entry,
        "shebang": module.shebang,
        "imports": module.imports,
        "constants": module.global_constants,
        "public_functions": [
            {
                "name": f.name,
                "line": f.lineno,
                "args": f.args,
                "returns": f.returns,
                "decorators": f.decorators,
                "has_docstring": f.docstring is not None,
                "docstring_preview": (f.docstring or "")[:200],
                "is_async": f.is_async,
            }
            for f in module.public_functions
        ],
        "private_functions": [
            {
                "name": f.name,
                "line": f.lineno,
                "args": f.args,
                "has_docstring": f.docstring is not None,
            }
            for f in module.functions
            if f.is_private
        ],
        "classes": [
            {
                "name": c.name,
                "line": c.lineno,
                "bases": c.bases,
                "is_dataclass": c.is_dataclass,
                "has_docstring": c.docstring is not None,
                "public_methods": [
                    {
                        "name": m.name,
                        "args": m.args,
                        "returns": m.returns,
                        "has_docstring": m.docstring is not None,
                    }
                    for m in c.public_methods
                ],
            }
            for c in module.classes
        ],
    }

    if args.human:
        _print_human_extract(output)
    else:
        print(json.dumps(output, indent=2))
    return 0


def _print_human_extract(info: dict) -> None:
    """Human-readable extraction output."""
    print(f"Module: {info['path']}")
    print(f"Lines: {info['total_lines']}")
    print(f"CLI tool: {'yes' if info['has_cli_entry'] else 'no'}")
    print()

    if info["constants"]:
        print("Constants:")
        for c in info["constants"]:
            print(f"  {c}")
        print()

    if info["public_functions"]:
        print("Public Functions:")
        for f in info["public_functions"]:
            args_str = ", ".join(f["args"])
            ret = f" -> {f['returns']}" if f["returns"] else ""
            async_prefix = "async " if f["is_async"] else ""
            doc_flag = " [documented]" if f["has_docstring"] else " [NO DOCSTRING]"
            print(f"  {async_prefix}{f['name']}({args_str}){ret}{doc_flag}")
        print()

    if info["classes"]:
        print("Classes:")
        for c in info["classes"]:
            bases = f"({', '.join(c['bases'])})" if c["bases"] else ""
            dc = " @dataclass" if c["is_dataclass"] else ""
            print(f"  {c['name']}{bases}{dc}")
            for m in c["public_methods"]:
                args_str = ", ".join(m["args"])
                ret = f" -> {m['returns']}" if m["returns"] else ""
                print(f"    .{m['name']}({args_str}){ret}")
        print()

    if info["private_functions"]:
        print(f"Private functions: {len(info['private_functions'])}")


def cmd_verify(args: argparse.Namespace) -> int:
    """Verify documentation against source."""
    source_path = Path(args.source)
    doc_path = Path(args.doc)

    if not source_path.exists():
        print(json.dumps({"error": f"Source not found: {source_path}"}))
        return 1
    if not doc_path.exists():
        print(json.dumps({"error": f"Doc not found: {doc_path}"}))
        return 1

    result = verify_documentation(source_path, doc_path)

    if args.human:
        print(f"Verification: {'PASS' if result.passed else 'FAIL'}")
        print(f"Score: {result.score:.1%}")
        print()
        print(result.summary)
        if result.checks:
            print()
            failed = [c for c in result.checks if not c["passed"]]
            if failed:
                print(f"Failed checks ({len(failed)}):")
                for c in failed:
                    print(f"  - {c['detail']}")
    else:
        output = {
            "passed": result.passed,
            "score": round(result.score, 3),
            "source": result.source_file,
            "doc": result.doc_file,
            "missing_functions": result.missing_functions,
            "missing_classes": result.missing_classes,
            "missing_constants": result.missing_constants,
            "undocumented_args": result.undocumented_args,
            "structure_issues": result.structure_issues,
            "accuracy_issues": result.accuracy_issues,
            "summary": result.summary,
            "checks": result.checks,
        }
        print(json.dumps(output, indent=2))

    return 0 if result.passed else 1


def cmd_check_structure(args: argparse.Namespace) -> int:
    """Check documentation structure."""
    doc_path = Path(args.doc)
    if not doc_path.exists():
        print(json.dumps({"error": f"File not found: {doc_path}"}))
        return 1

    result = check_doc_structure(doc_path)

    if args.human:
        print(f"Structure check: {'PASS' if result['passed'] else 'FAIL'}")
        print(f"Headers: {', '.join(result['headers']) or 'none'}")
        print(f"Code blocks: {result['code_blocks']}")
        print(f"Word count: {result['word_count']}")
        if result["issues"]:
            print("Issues:")
            for issue in result["issues"]:
                print(f"  - {issue}")
    else:
        print(json.dumps(result, indent=2))

    return 0 if result["passed"] else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Python documentation against source code")

    subparsers = parser.add_subparsers(dest="command", required=True)

    # Shared arguments
    human_help = "Human-readable output (default: JSON)"

    # extract command
    p_extract = subparsers.add_parser("extract", help="Extract documentable elements")
    p_extract.add_argument("--source", required=True, help="Python source file")
    p_extract.add_argument("--human", action="store_true", help=human_help)

    # verify command
    p_verify = subparsers.add_parser("verify", help="Verify docs against source")
    p_verify.add_argument("--source", required=True, help="Python source file")
    p_verify.add_argument("--doc", required=True, help="Documentation file")
    p_verify.add_argument("--human", action="store_true", help=human_help)

    # check-structure command
    p_struct = subparsers.add_parser("check-structure", help="Check doc structure")
    p_struct.add_argument("--doc", required=True, help="Documentation file")
    p_struct.add_argument("--human", action="store_true", help=human_help)

    args = parser.parse_args()

    if args.command == "extract":
        return cmd_extract(args)
    elif args.command == "verify":
        return cmd_verify(args)
    elif args.command == "check-structure":
        return cmd_check_structure(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
