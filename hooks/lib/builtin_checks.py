#!/usr/bin/env python3
"""
Built-in Code Quality Checks

Zero-dependency checks that work without external tools.
Provides baseline quality checking when ruff/eslint/etc aren't installed.

These checks catch the most common issues that GitHub Copilot flags:
- Unused variables and imports
- Syntax errors
- Common anti-patterns
- Security concerns
"""

import ast
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class Issue:
    """A code quality issue."""

    file: str
    line: int
    column: int
    code: str
    message: str
    severity: str = "warning"  # error, warning, info


class PythonChecker:
    """Built-in Python code checker using AST."""

    def __init__(self):
        self.issues: list[Issue] = []

    def check_file(self, file_path: Path) -> list[Issue]:
        """Check a Python file for common issues."""
        self.issues = []
        self.file_path = str(file_path)

        try:
            content = file_path.read_text()
            self.lines = content.split("\n")
        except Exception as e:
            self.issues.append(
                Issue(
                    file=self.file_path,
                    line=0,
                    column=0,
                    code="E000",
                    message=f"Could not read file: {e}",
                    severity="warning",
                )
            )
            return self.issues

        # Syntax check first
        try:
            tree = ast.parse(content, filename=str(file_path))
        except SyntaxError as e:
            self.issues.append(
                Issue(
                    file=self.file_path,
                    line=e.lineno or 1,
                    column=e.offset or 0,
                    code="E999",
                    message=f"SyntaxError: {e.msg}",
                    severity="error",
                )
            )
            return self.issues

        # AST-based checks
        self._check_unused_imports(tree)
        self._check_unused_variables(tree)
        self._check_bare_except(tree)
        self._check_assert_usage(tree)

        # Line-based checks (use self.lines set in check_file)
        self._check_print_statements()
        self._check_todo_comments()
        self._check_long_lines()
        self._check_trailing_whitespace()

        return self.issues

    def _check_unused_imports(self, tree: ast.AST):
        """Find imports that are never used."""
        # Collect all imports
        imports = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.asname or alias.name
                    imports[name] = node.lineno
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name == "*":
                        continue
                    name = alias.asname or alias.name
                    imports[name] = node.lineno

        # Check which imports are used
        for name, lineno in imports.items():
            # Simple check: is the name used anywhere after the import?
            pattern = rf"\b{re.escape(name)}\b"
            lines_after_import = "\n".join(self.lines[lineno:])
            if not re.search(pattern, lines_after_import):
                self.issues.append(
                    Issue(
                        file=self.file_path,
                        line=lineno,
                        column=0,
                        code="F401",
                        message=f"'{name}' imported but unused",
                        severity="warning",
                    )
                )

    def _check_unused_variables(self, tree: ast.AST):
        """Find variables that are assigned but never used."""
        # This is a simplified check - only catches obvious cases
        assigned = {}
        used = set()

        class VariableVisitor(ast.NodeVisitor):
            def visit_Name(self, node):
                if isinstance(node.ctx, ast.Store):
                    # Skip if name starts with _ (intentionally unused)
                    if not node.id.startswith("_"):
                        assigned[node.id] = node.lineno
                elif isinstance(node.ctx, ast.Load):
                    used.add(node.id)
                self.generic_visit(node)

            def visit_FunctionDef(self, node):
                # Don't check function arguments
                self.generic_visit(node)

        VariableVisitor().visit(tree)

        for name, lineno in assigned.items():
            if name not in used:
                self.issues.append(
                    Issue(
                        file=self.file_path,
                        line=lineno,
                        column=0,
                        code="F841",
                        message=f"Local variable '{name}' is assigned but never used",
                        severity="warning",
                    )
                )

    def _check_bare_except(self, tree: ast.AST):
        """Find bare except clauses without specific exception type."""
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                if node.type is None:
                    self.issues.append(
                        Issue(
                            file=self.file_path,
                            line=node.lineno,
                            column=0,
                            code="E722",
                            message="Bare 'except:' clause - specify exception type",
                            severity="warning",
                        )
                    )

    def _check_assert_usage(self, tree: ast.AST):
        """Flag assert statements (removed in optimized mode)."""
        for node in ast.walk(tree):
            if isinstance(node, ast.Assert):
                self.issues.append(
                    Issue(
                        file=self.file_path,
                        line=node.lineno,
                        column=0,
                        code="S101",
                        message="Use of assert detected - may be removed in optimized mode",
                        severity="info",
                    )
                )

    def _check_print_statements(self):
        """Find print() statements (likely debug code)."""
        for i, line in enumerate(self.lines, 1):
            # Skip comments
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue
            # Look for print(
            if re.search(r"\bprint\s*\(", line):
                self.issues.append(
                    Issue(
                        file=self.file_path,
                        line=i,
                        column=0,
                        code="T201",
                        message="print() found - remove debug statement before commit",
                        severity="info",
                    )
                )

    def _check_todo_comments(self):
        """Find TODO/FIXME comments."""
        for i, line in enumerate(self.lines, 1):
            if re.search(r"#\s*(TODO|FIXME|XXX|HACK)\b", line, re.IGNORECASE):
                self.issues.append(
                    Issue(
                        file=self.file_path,
                        line=i,
                        column=0,
                        code="T100",
                        message="TODO/FIXME comment found",
                        severity="info",
                    )
                )

    def _check_long_lines(self, max_length: int = 120):
        """Find lines exceeding max length."""
        for i, line in enumerate(self.lines, 1):
            if len(line) > max_length:
                self.issues.append(
                    Issue(
                        file=self.file_path,
                        line=i,
                        column=max_length,
                        code="E501",
                        message=f"Line too long ({len(line)} > {max_length})",
                        severity="warning",
                    )
                )

    def _check_trailing_whitespace(self):
        """Find trailing whitespace."""
        for i, line in enumerate(self.lines, 1):
            if line.endswith(" ") or line.endswith("\t"):
                self.issues.append(
                    Issue(
                        file=self.file_path,
                        line=i,
                        column=len(line),
                        code="W291",
                        message="Trailing whitespace",
                        severity="info",
                    )
                )


class JavaScriptChecker:
    """Built-in JavaScript/TypeScript checker using regex patterns."""

    def __init__(self):
        self.issues: list[Issue] = []

    def check_file(self, file_path: Path) -> list[Issue]:
        """Check a JavaScript/TypeScript file for common issues."""
        self.issues = []
        self.file_path = str(file_path)

        try:
            content = file_path.read_text()
            self.lines = content.split("\n")
        except Exception as e:
            self.issues.append(
                Issue(
                    file=self.file_path,
                    line=0,
                    column=0,
                    code="E000",
                    message=f"Could not read file: {e}",
                    severity="warning",
                )
            )
            return self.issues

        self._check_var_usage()
        self._check_console_log()
        self._check_double_equals()
        self._check_todo_comments()

        return self.issues

    def _check_var_usage(self):
        """Flag use of var (prefer let/const)."""
        for i, line in enumerate(self.lines, 1):
            if re.search(r"\bvar\s+\w+", line):
                self.issues.append(
                    Issue(
                        file=self.file_path,
                        line=i,
                        column=0,
                        code="no-var",
                        message="Use 'let' or 'const' instead of 'var'",
                        severity="warning",
                    )
                )

    def _check_console_log(self):
        """Find console.log statements."""
        for i, line in enumerate(self.lines, 1):
            if re.search(r"\bconsole\.(log|debug|info|warn|error)\s*\(", line):
                self.issues.append(
                    Issue(
                        file=self.file_path,
                        line=i,
                        column=0,
                        code="no-console",
                        message="console.log found - remove debug statement",
                        severity="info",
                    )
                )

    def _check_double_equals(self):
        """Flag == instead of ===."""
        for i, line in enumerate(self.lines, 1):
            # Skip comments
            stripped = line.lstrip()
            if stripped.startswith("//") or stripped.startswith("/*"):
                continue

            # Match == that is not preceded by ! or = and not followed by =
            # Use word boundary approach: find == and verify context
            for match in re.finditer(r"==", line):
                pos = match.start()
                # Check character before (if exists)
                if pos > 0 and line[pos - 1] in "!=":
                    continue  # Part of !== or ===
                # Check character after
                end_pos = match.end()
                if end_pos < len(line) and line[end_pos] == "=":
                    continue  # Part of ===

                self.issues.append(
                    Issue(
                        file=self.file_path,
                        line=i,
                        column=pos,
                        code="eqeqeq",
                        message="Use '===' instead of '==' for strict equality",
                        severity="warning",
                    )
                )
                break  # One warning per line is enough

    def _check_todo_comments(self):
        """Find TODO/FIXME comments."""
        for i, line in enumerate(self.lines, 1):
            if re.search(r"//\s*(TODO|FIXME|XXX|HACK)\b", line, re.IGNORECASE):
                self.issues.append(
                    Issue(
                        file=self.file_path,
                        line=i,
                        column=0,
                        code="todo-comment",
                        message="TODO/FIXME comment found",
                        severity="info",
                    )
                )


class ShellChecker:
    """Built-in shell script checker."""

    def __init__(self):
        self.issues: list[Issue] = []

    def check_file(self, file_path: Path) -> list[Issue]:
        """Check a shell script for common issues."""
        self.issues = []
        self.file_path = str(file_path)

        try:
            content = file_path.read_text()
            self.lines = content.split("\n")
        except Exception as e:
            self.issues.append(
                Issue(
                    file=self.file_path,
                    line=0,
                    column=0,
                    code="E000",
                    message=f"Could not read file: {e}",
                    severity="warning",
                )
            )
            return self.issues

        self._check_shebang()
        self._check_unquoted_variables()
        self._check_backticks()

        return self.issues

    def _check_shebang(self):
        """Check for proper shebang."""
        if self.lines and not self.lines[0].startswith("#!"):
            self.issues.append(
                Issue(
                    file=self.file_path,
                    line=1,
                    column=0,
                    code="SC2148",
                    message="Missing shebang (#!/bin/bash or #!/bin/sh)",
                    severity="warning",
                )
            )

    def _check_unquoted_variables(self):
        """Flag unquoted variable expansions.

        Uses a simplified heuristic: find $VAR patterns and check if they
        appear to be inside double quotes by counting quote characters.
        This is not perfect (can't handle escaped quotes or nested quotes)
        but catches the most common cases.
        """
        for i, line in enumerate(self.lines, 1):
            # Skip comments
            if line.lstrip().startswith("#"):
                continue

            # Find all $VAR occurrences
            for match in re.finditer(r"\$[A-Za-z_][A-Za-z0-9_]*", line):
                var_pos = match.start()
                # Count unescaped double quotes before this position
                prefix = line[:var_pos]
                # Remove escaped quotes for counting
                prefix_clean = prefix.replace('\\"', "")
                quote_count = prefix_clean.count('"')

                # If odd number of quotes before, we're inside quotes (safe)
                # If even number, we're outside quotes (potentially unsafe)
                if quote_count % 2 == 0:
                    self.issues.append(
                        Issue(
                            file=self.file_path,
                            line=i,
                            column=var_pos,
                            code="SC2086",
                            message="Double quote variable to prevent globbing",
                            severity="warning",
                        )
                    )
                    break  # One warning per line is enough

    def _check_backticks(self):
        """Flag backticks (prefer $())."""
        for i, line in enumerate(self.lines, 1):
            if "`" in line and not line.lstrip().startswith("#"):
                self.issues.append(
                    Issue(
                        file=self.file_path,
                        line=i,
                        column=0,
                        code="SC2006",
                        message="Use $(...) instead of backticks for command substitution",
                        severity="info",
                    )
                )


def get_checker(language: str) -> Optional[object]:
    """Get the appropriate checker for a language."""
    checkers = {
        "python": PythonChecker,
        "javascript": JavaScriptChecker,
        "typescript": JavaScriptChecker,
        "shell": ShellChecker,
    }
    checker_class = checkers.get(language)
    return checker_class() if checker_class else None


def run_builtin_checks(files: list[Path], language: str) -> list[Issue]:
    """Run built-in checks on files.

    Args:
        files: List of file paths to check
        language: Language name

    Returns:
        List of issues found
    """
    checker = get_checker(language)
    if not checker:
        return []

    all_issues = []
    for file_path in files:
        issues = checker.check_file(file_path)
        all_issues.extend(issues)

    return all_issues


def format_issues(issues: list[Issue]) -> str:
    """Format issues for display."""
    if not issues:
        return "No issues found."

    lines = []
    for issue in issues:
        lines.append(f"{issue.file}:{issue.line}:{issue.column}: {issue.code} {issue.message}")

    return "\n".join(lines)


# CLI for testing
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python3 builtin_checks.py <file.py>")
        sys.exit(1)

    file_path = Path(sys.argv[1])
    if not file_path.exists():
        print(f"File not found: {file_path}")
        sys.exit(1)

    # Detect language from extension
    ext_to_lang = {
        ".py": "python",
        ".js": "javascript",
        ".jsx": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".sh": "shell",
        ".bash": "shell",
    }
    language = ext_to_lang.get(file_path.suffix, "unknown")

    issues = run_builtin_checks([file_path], language)

    if issues:
        print(format_issues(issues))
        sys.exit(1)
    else:
        print("No issues found.")
        sys.exit(0)
