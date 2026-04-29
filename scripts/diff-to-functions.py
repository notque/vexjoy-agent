#!/usr/bin/env python3
"""Map git diff hunks to the functions they modify.

Usage:
    python3 scripts/diff-to-functions.py                    # unstaged changes
    python3 scripts/diff-to-functions.py --staged           # staged changes
    python3 scripts/diff-to-functions.py --ref main         # diff against ref
    python3 scripts/diff-to-functions.py --ref HEAD~3       # last 3 commits
    python3 scripts/diff-to-functions.py --format summary   # compact list

Exit codes: 0=success, 1=no changes, 2=script error
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# Language detection by file extension
EXTENSION_TO_LANGUAGE: dict[str, str] = {
    ".py": "python",
    ".go": "go",
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
    ".zsh": "bash",
    ".bas": "vb6",
    ".cls": "vb6",
    ".frm": "vb6",
}

# Tree-sitter node types that represent function/method definitions per language
FUNCTION_NODE_TYPES: dict[str, list[str]] = {
    "python": ["function_definition", "decorated_definition"],
    "go": ["function_declaration", "method_declaration"],
    "typescript": [
        "function_declaration",
        "method_definition",
        "arrow_function",
        "function",
    ],
    "javascript": [
        "function_declaration",
        "method_definition",
        "arrow_function",
        "function",
    ],
    "php": ["function_definition", "method_declaration"],
    "kotlin": ["function_declaration"],
    "swift": ["function_declaration"],
    "bash": ["function_definition"],
}

# Regex patterns for function detection (fallback when tree-sitter unavailable)
FUNCTION_PATTERNS: dict[str, re.Pattern[str]] = {
    "python": re.compile(
        r"^[ \t]*(?:async\s+)?def\s+(?P<name>\w+)\s*\((?P<params>[^)]*)\)",
        re.MULTILINE,
    ),
    "go": re.compile(
        r"^func\s+(?:\((?P<receiver>[^)]+)\)\s+)?(?P<name>\w+)\s*\((?P<params>[^)]*)\)",
        re.MULTILINE,
    ),
    "typescript": re.compile(
        r"^(?:export\s+)?(?:async\s+)?function\s+(?P<name>\w+)\s*\((?P<params>[^)]*)\)"
        r"|^\s*(?:(?:public|private|protected|static|async)\s+)*(?P<method>\w+)\s*\((?P<mparams>[^)]*)\)\s*[:{]",
        re.MULTILINE,
    ),
    "javascript": re.compile(
        r"^(?:export\s+)?(?:async\s+)?function\s+(?P<name>\w+)\s*\((?P<params>[^)]*)\)"
        r"|^\s*(?:(?:static|async)\s+)*(?P<method>\w+)\s*\((?P<mparams>[^)]*)\)\s*[{]",
        re.MULTILINE,
    ),
    "php": re.compile(
        r"^\s*(?:(?:public|private|protected|static)\s+)*function\s+(?P<name>\w+)\s*\((?P<params>[^)]*)\)",
        re.MULTILINE,
    ),
    "kotlin": re.compile(
        r"^\s*(?:(?:public|private|protected|internal|override|suspend|inline)\s+)*fun\s+(?P<name>\w+)\s*\((?P<params>[^)]*)\)",
        re.MULTILINE,
    ),
    "swift": re.compile(
        r"^\s*(?:(?:public|private|internal|fileprivate|open|override|static|class|@\w+)\s+)*func\s+(?P<name>\w+)\s*\((?P<params>[^)]*)\)",
        re.MULTILINE,
    ),
    "bash": re.compile(
        r"^(?:function\s+)?(?P<name>\w+)\s*\(\s*\)\s*\{",
        re.MULTILINE,
    ),
    "vb6": re.compile(
        r"^(?:Public|Private|Friend)?\s*(?:Static\s+)?(?:Sub|Function)\s+(?P<name>\w+)\s*\((?P<params>[^)]*)\)",
        re.MULTILINE | re.IGNORECASE,
    ),
}

# End patterns for languages with explicit block terminators
FUNCTION_END_PATTERNS: dict[str, re.Pattern[str]] = {
    "vb6": re.compile(r"^\s*End\s+(?:Sub|Function)", re.MULTILINE | re.IGNORECASE),
}


@dataclass
class FunctionInfo:
    """Represents a function/method found in source code."""

    name: str
    class_name: Optional[str] = None
    line: int = 0
    end_line: int = 0
    params: str = ""
    source: str = ""


@dataclass
class ChangedFunction:
    """A function that was modified in the diff."""

    file: str
    language: str
    function: str
    class_name: Optional[str]
    line: int
    end_line: int
    params: str
    source: str
    diff_lines: list[int] = field(default_factory=list)


@dataclass
class UnparseableFile:
    """A changed file that has no parseable functions."""

    file: str
    reason: str
    changed_line_count: int = 0


def detect_language(filepath: str) -> Optional[str]:
    """Detect programming language from file extension."""
    ext = Path(filepath).suffix.lower()
    return EXTENSION_TO_LANGUAGE.get(ext)


def parse_diff_output(diff_text: str) -> dict[str, list[int]]:
    """Parse unified diff output and extract changed line numbers per file.

    Args:
        diff_text: Raw output from git diff --unified=0.

    Returns:
        Dict mapping file paths to lists of changed line numbers (in the new file).
    """
    result: dict[str, list[int]] = {}
    current_file: Optional[str] = None

    for line in diff_text.splitlines():
        # Detect file path from +++ line (new file side)
        if line.startswith("+++ b/"):
            current_file = line[6:]
            if current_file not in result:
                result[current_file] = []
        elif line.startswith("+++ /dev/null"):
            # File was deleted
            current_file = None
        elif line.startswith("@@") and current_file is not None:
            # Parse hunk header: @@ -old_start,old_count +new_start,new_count @@
            match = re.search(r"\+(\d+)(?:,(\d+))?", line)
            if match:
                start = int(match.group(1))
                count = int(match.group(2)) if match.group(2) else 1
                # If count is 0, this is a pure deletion - no new lines to map
                if count > 0:
                    result[current_file].extend(range(start, start + count))

    return result


def find_functions_regex(source: str, language: str) -> list[FunctionInfo]:
    """Find function boundaries using regex patterns (fallback method).

    Args:
        source: Source code content.
        language: Programming language identifier.

    Returns:
        List of FunctionInfo with line ranges.
    """
    pattern = FUNCTION_PATTERNS.get(language)
    if not pattern:
        return []

    lines = source.splitlines()
    total_lines = len(lines)
    functions: list[FunctionInfo] = []

    for match in pattern.finditer(source):
        start_line = source[: match.start()].count("\n") + 1

        # Get function name from named groups
        name = match.group("name") if match.groupdict().get("name") else match.groupdict().get("method", "unknown")
        if not name:
            continue

        # Get params
        params = match.groupdict().get("params") or match.groupdict().get("mparams") or ""
        params = params.strip()

        # Determine class context for methods
        class_name = _find_enclosing_class(source, match.start(), language)

        # Find end of function
        end_line = _find_function_end(lines, start_line, total_lines, language)

        # Extract source
        func_source = "\n".join(lines[start_line - 1 : end_line])

        functions.append(
            FunctionInfo(
                name=name,
                class_name=class_name,
                line=start_line,
                end_line=end_line,
                params=params,
                source=func_source,
            )
        )

    return functions


def _find_enclosing_class(source: str, position: int, language: str) -> Optional[str]:
    """Find the class that encloses a given position in the source."""
    class_patterns = {
        "python": re.compile(r"^([ \t]*)class\s+(\w+)", re.MULTILINE),
        "typescript": re.compile(r"^([ \t]*)(?:export\s+)?class\s+(\w+)", re.MULTILINE),
        "javascript": re.compile(r"^([ \t]*)(?:export\s+)?class\s+(\w+)", re.MULTILINE),
        "php": re.compile(r"^([ \t]*)(?:abstract\s+)?class\s+(\w+)", re.MULTILINE),
        "kotlin": re.compile(r"^([ \t]*)(?:(?:open|abstract|data|sealed)\s+)?class\s+(\w+)", re.MULTILINE),
        "swift": re.compile(r"^([ \t]*)(?:(?:public|private|internal|open|final)\s+)?class\s+(\w+)", re.MULTILINE),
    }

    pattern = class_patterns.get(language)
    if not pattern:
        return None

    # For indentation-based languages, check that the function is indented more than the class
    indentation_languages = {"python"}

    # Get the indentation of the function at position
    line_start = source.rfind("\n", 0, position) + 1
    func_line = source[line_start:position] + source[position : source.find("\n", position)]
    func_indent = len(func_line) - len(func_line.lstrip())

    # Find the last class definition before this position where the function is inside it
    last_class = None
    for match in pattern.finditer(source[:position]):
        class_indent = len(match.group(1))
        class_name = match.group(2)
        if language in indentation_languages:
            # Function must be indented more than the class to be inside it
            if func_indent > class_indent:
                last_class = class_name
            else:
                last_class = None
        else:
            last_class = class_name

    return last_class


def _find_function_end(lines: list[str], start_line: int, total_lines: int, language: str) -> int:
    """Find the end line of a function starting at start_line.

    Uses language-specific heuristics:
    - Python: indentation-based
    - VB6: End Sub/Function
    - Brace languages: brace counting
    - Bash: brace counting
    """
    if language == "python":
        return _find_python_function_end(lines, start_line, total_lines)
    elif language == "vb6":
        return _find_vb6_function_end(lines, start_line, total_lines)
    elif language == "bash":
        return _find_brace_function_end(lines, start_line, total_lines)
    else:
        return _find_brace_function_end(lines, start_line, total_lines)


def _find_python_function_end(lines: list[str], start_line: int, total_lines: int) -> int:
    """Find end of Python function by indentation."""
    if start_line > total_lines:
        return start_line

    # Get the indentation of the def line
    def_line = lines[start_line - 1]
    def_indent = len(def_line) - len(def_line.lstrip())

    end_line = start_line
    for i in range(start_line, total_lines):
        line = lines[i]
        # Skip blank lines and comments
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            end_line = i + 1
            continue
        # If indentation is greater than def, still in function
        current_indent = len(line) - len(line.lstrip())
        if current_indent > def_indent:
            end_line = i + 1
        else:
            break

    return end_line


def _find_vb6_function_end(lines: list[str], start_line: int, total_lines: int) -> int:
    """Find end of VB6 function by End Sub/Function."""
    end_pattern = FUNCTION_END_PATTERNS["vb6"]
    for i in range(start_line, total_lines):
        if end_pattern.match(lines[i]):
            return i + 1
    return total_lines


def _find_brace_function_end(lines: list[str], start_line: int, total_lines: int) -> int:
    """Find end of function in brace-delimited languages."""
    brace_count = 0
    found_open = False

    for i in range(start_line - 1, total_lines):
        line = lines[i]
        # Simple brace counting (ignores braces in strings/comments)
        for char in line:
            if char == "{":
                brace_count += 1
                found_open = True
            elif char == "}":
                brace_count -= 1

        if found_open and brace_count <= 0:
            return i + 1

    return total_lines


def try_tree_sitter_parse(source: str, language: str) -> Optional[list[FunctionInfo]]:
    """Attempt to parse source with tree-sitter for accurate function boundaries.

    Args:
        source: Source code content.
        language: Programming language identifier.

    Returns:
        List of FunctionInfo if tree-sitter is available and parsing succeeds, None otherwise.
    """
    try:
        import tree_sitter
    except ImportError:
        return None

    # Language library names for tree-sitter
    ts_language_map = {
        "python": "python",
        "go": "go",
        "typescript": "typescript",
        "javascript": "javascript",
        "php": "php",
        "kotlin": "kotlin",
        "swift": "swift",
        "bash": "bash",
    }

    ts_lang_name = ts_language_map.get(language)
    if not ts_lang_name:
        return None

    try:
        import tree_sitter_languages

        parser = tree_sitter_languages.get_parser(ts_lang_name)
        tree = parser.parse(source.encode())
        return _extract_functions_from_tree(tree.root_node, source, language)
    except Exception:
        return None


def _extract_functions_from_tree(root_node: object, source: str, language: str) -> list[FunctionInfo]:
    """Walk tree-sitter AST and extract function definitions.

    Args:
        root_node: Tree-sitter root node.
        source: Source code for extracting text.
        language: Language for node type lookup.

    Returns:
        List of FunctionInfo from the AST.
    """
    node_types = FUNCTION_NODE_TYPES.get(language, [])
    lines = source.splitlines()
    functions: list[FunctionInfo] = []

    def walk(node: object) -> None:
        # Access node attributes dynamically since tree-sitter types vary
        node_type = getattr(node, "type", "")
        children = getattr(node, "children", [])

        if node_type in node_types:
            start_line = getattr(node, "start_point", (0, 0))[0] + 1
            end_line = getattr(node, "end_point", (0, 0))[0] + 1

            # Extract function name from child nodes
            name = "unknown"
            params = ""
            for child in children:
                child_type = getattr(child, "type", "")
                if child_type in ("identifier", "name", "property_identifier"):
                    name = getattr(child, "text", b"").decode("utf-8", errors="replace")
                elif child_type in ("parameters", "formal_parameters", "parameter_list"):
                    raw = getattr(child, "text", b"").decode("utf-8", errors="replace")
                    # Strip outer parens
                    params = raw.strip("()")

            func_source = "\n".join(lines[start_line - 1 : end_line])
            class_name = _find_class_ancestor(node, language)

            functions.append(
                FunctionInfo(
                    name=name,
                    class_name=class_name,
                    line=start_line,
                    end_line=end_line,
                    params=params,
                    source=func_source,
                )
            )
        else:
            for child in children:
                walk(child)

    walk(root_node)
    return functions


def _find_class_ancestor(node: object, language: str) -> Optional[str]:
    """Walk up tree-sitter AST to find enclosing class."""
    class_types = {"class_definition", "class_declaration", "class_specifier"}
    current = getattr(node, "parent", None)
    while current is not None:
        if getattr(current, "type", "") in class_types:
            for child in getattr(current, "children", []):
                if getattr(child, "type", "") in ("identifier", "name", "type_identifier"):
                    return getattr(child, "text", b"").decode("utf-8", errors="replace")
        current = getattr(current, "parent", None)
    return None


def find_functions_in_file(filepath: str, source: str) -> list[FunctionInfo]:
    """Find all functions in a file, using tree-sitter if available, else regex.

    Args:
        filepath: Path to the file (for language detection).
        source: File content.

    Returns:
        List of functions found in the file.
    """
    language = detect_language(filepath)
    if not language:
        return []

    # Try tree-sitter first
    ts_result = try_tree_sitter_parse(source, language)
    if ts_result is not None:
        return ts_result

    # Fall back to regex
    return find_functions_regex(source, language)


def map_lines_to_functions(functions: list[FunctionInfo], changed_lines: list[int]) -> dict[int, list[int]]:
    """Map changed line numbers to their containing functions.

    Args:
        functions: List of functions with line ranges.
        changed_lines: List of changed line numbers.

    Returns:
        Dict mapping function index to list of changed lines within it.
    """
    result: dict[int, list[int]] = {}

    for line_num in changed_lines:
        for i, func in enumerate(functions):
            if func.line <= line_num <= func.end_line:
                if i not in result:
                    result[i] = []
                result[i].append(line_num)
                break

    return result


def get_git_diff(ref: Optional[str] = None, staged: bool = False) -> str:
    """Run git diff and return the output.

    Args:
        ref: Git ref to diff against (e.g., 'main', 'HEAD~3').
        staged: Whether to show staged changes only.

    Returns:
        Raw git diff output string.
    """
    cmd = ["git", "diff", "--unified=0", "--no-color"]

    if ref:
        cmd.append(ref)
    elif staged:
        cmd.append("--staged")

    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    return result.stdout


def read_file_content(filepath: str) -> Optional[str]:
    """Read file content, returning None if file doesn't exist or is binary.

    Args:
        filepath: Path relative to git root.

    Returns:
        File content string or None.
    """
    # Find git root
    git_root_result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=False,
    )
    if git_root_result.returncode != 0:
        return None

    git_root = Path(git_root_result.stdout.strip())
    full_path = git_root / filepath

    if not full_path.exists():
        return None

    try:
        return full_path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None


def build_output(
    changed_functions: list[ChangedFunction],
    unparseable_files: list[UnparseableFile],
    ref: Optional[str],
    staged: bool,
) -> dict:
    """Build the JSON output structure.

    Args:
        changed_functions: List of modified functions.
        unparseable_files: List of files without parseable functions.
        ref: Git ref that was diffed against.
        staged: Whether staged changes were examined.

    Returns:
        Dict ready for JSON serialization.
    """
    diff_target = ref if ref else ("staged" if staged else "working tree")

    return {
        "ref": diff_target,
        "changed_functions": [
            {
                "file": cf.file,
                "language": cf.language,
                "function": cf.function,
                "class": cf.class_name,
                "line": cf.line,
                "end_line": cf.end_line,
                "params": cf.params,
                "source": cf.source,
                "diff_lines": cf.diff_lines,
            }
            for cf in changed_functions
        ],
        "changed_files_without_functions": [
            {"file": uf.file, "reason": uf.reason, "changed_line_count": uf.changed_line_count}
            for uf in unparseable_files
        ],
    }


def format_summary(
    changed_functions: list[ChangedFunction],
    unparseable_files: list[UnparseableFile],
    ref: Optional[str],
    staged: bool,
) -> str:
    """Format output as a compact text summary.

    Args:
        changed_functions: List of modified functions.
        unparseable_files: List of files without parseable functions.
        ref: Git ref that was diffed against.
        staged: Whether staged changes were examined.

    Returns:
        Formatted text summary string.
    """
    diff_target = ref if ref else ("staged" if staged else "working tree")
    lines = [f"Changed functions (diff against {diff_target}):"]

    # Group by file
    by_file: dict[str, list[ChangedFunction]] = {}
    for cf in changed_functions:
        if cf.file not in by_file:
            by_file[cf.file] = []
        by_file[cf.file].append(cf)

    for filepath, funcs in by_file.items():
        lines.append(f"  {filepath}:")
        for cf in funcs:
            display_name = f"{cf.class_name}.{cf.function}" if cf.class_name else cf.function
            # Truncate params for display
            params_display = cf.params
            if len(params_display) > 40:
                params_display = params_display[:37] + "..."
            lines.append(
                f"    {display_name}({params_display})  [L{cf.line}-{cf.end_line}, {len(cf.diff_lines)} lines changed]"
            )

    for uf in unparseable_files:
        lines.append(f"  {uf.file}: [{uf.reason}, {uf.changed_line_count} lines changed]")

    return "\n".join(lines)


def run(ref: Optional[str] = None, staged: bool = False, output_format: str = "json") -> int:
    """Main execution logic.

    Args:
        ref: Git ref to diff against.
        staged: Whether to show staged changes.
        output_format: 'json' or 'summary'.

    Returns:
        Exit code (0=success, 1=no changes, 2=error).
    """
    try:
        diff_text = get_git_diff(ref=ref, staged=staged)
    except Exception as e:
        print(f"Error running git diff: {e}", file=sys.stderr)
        return 2

    if not diff_text.strip():
        if output_format == "json":
            print(
                json.dumps(
                    {
                        "ref": ref or ("staged" if staged else "working tree"),
                        "changed_functions": [],
                        "changed_files_without_functions": [],
                    },
                    indent=2,
                )
            )
        else:
            diff_target = ref if ref else ("staged" if staged else "working tree")
            print(f"No changes found (diff against {diff_target})")
        return 1

    file_changes = parse_diff_output(diff_text)
    if not file_changes:
        return 1

    changed_functions: list[ChangedFunction] = []
    unparseable_files: list[UnparseableFile] = []

    for filepath, changed_lines in file_changes.items():
        if not changed_lines:
            continue

        language = detect_language(filepath)
        if not language:
            unparseable_files.append(
                UnparseableFile(
                    file=filepath,
                    reason="no parseable functions",
                    changed_line_count=len(changed_lines),
                )
            )
            continue

        source = read_file_content(filepath)
        if source is None:
            unparseable_files.append(
                UnparseableFile(
                    file=filepath,
                    reason="file not readable",
                    changed_line_count=len(changed_lines),
                )
            )
            continue

        functions = find_functions_in_file(filepath, source)
        if not functions:
            unparseable_files.append(
                UnparseableFile(
                    file=filepath,
                    reason="no functions detected",
                    changed_line_count=len(changed_lines),
                )
            )
            continue

        line_map = map_lines_to_functions(functions, changed_lines)

        # Collect functions that had changes
        for func_idx, diff_lines in line_map.items():
            func = functions[func_idx]
            changed_functions.append(
                ChangedFunction(
                    file=filepath,
                    language=language,
                    function=func.name,
                    class_name=func.class_name,
                    line=func.line,
                    end_line=func.end_line,
                    params=func.params,
                    source=func.source,
                    diff_lines=sorted(diff_lines),
                )
            )

        # Check for changes outside any function
        all_func_lines = set()
        for func in functions:
            all_func_lines.update(range(func.line, func.end_line + 1))

        outside_lines = [ln for ln in changed_lines if ln not in all_func_lines]
        if outside_lines and not line_map:
            # All changes are outside functions
            unparseable_files.append(
                UnparseableFile(
                    file=filepath,
                    reason="changes outside functions",
                    changed_line_count=len(outside_lines),
                )
            )

    if output_format == "summary":
        print(format_summary(changed_functions, unparseable_files, ref, staged))
    else:
        output = build_output(changed_functions, unparseable_files, ref, staged)
        print(json.dumps(output, indent=2))

    return 0


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Map git diff hunks to the functions they modify.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--ref",
        type=str,
        default=None,
        help="Git ref to diff against (e.g., main, HEAD~3)",
    )
    parser.add_argument(
        "--staged",
        action="store_true",
        help="Show staged changes only",
    )
    parser.add_argument(
        "--format",
        type=str,
        choices=["json", "summary"],
        default="json",
        dest="output_format",
        help="Output format (default: json)",
    )

    args = parser.parse_args()

    if args.ref and args.staged:
        print("Error: --ref and --staged are mutually exclusive", file=sys.stderr)
        return 2

    return run(ref=args.ref, staged=args.staged, output_format=args.output_format)


if __name__ == "__main__":
    sys.exit(main())
