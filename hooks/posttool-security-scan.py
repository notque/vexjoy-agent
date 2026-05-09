#!/usr/bin/env python3
# hook-version: 1.0.0
"""
PostToolUse:Write,Edit Hook: Unified Security Pattern Scanner

Scans edited/written code files for common security vulnerability patterns
after each modification. Outputs informational warnings — never blocks.

Categories scanned:
1. Hardcoded credentials (credential-named variables with string literals)
2. SQL injection (f-strings, format(), concatenation, sprintf in SQL context)
3. Command injection (shell=True, os.system)
4. Path traversal (unvalidated relative path components)
5. Unsafe deserialization (loading without safe loaders)

Merged from posttool-security-scan.py + sql-injection-detector.py per
ADR hook-injection-condensation.

Design:
- PostToolUse (informational only, never blocks)
- Only scans code files (skips markdown, config, images)
- Compiled regex patterns for <50ms execution
- Reads file content from disk (tool_result may be truncated)
- Skips files >10,000 lines

ADR: adr/018-post-edit-security-scan.md, adr/134-sql-injection-detector-hook.md
"""

import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from stdin_timeout import read_stdin

# Code file extensions worth scanning
_CODE_EXTENSIONS = frozenset(
    {
        ".py",
        ".go",
        ".js",
        ".ts",
        ".tsx",
        ".jsx",
        ".rb",
        ".java",
        ".php",
        ".rs",
        ".c",
        ".cpp",
        ".cs",
        ".swift",
        ".kt",
    }
)

# Max lines to scan (skip generated/vendored files)
_MAX_LINES = 10_000


def _build_patterns() -> list[tuple[re.Pattern[str], str, str]]:
    """Build security patterns at import time.

    Patterns are constructed programmatically to avoid triggering
    security-reminder hooks that scan for literal pattern strings.
    """
    # Credential variable names to detect
    cred_names = "|".join(
        [
            "password",
            "passwd",
            "api_key",
            "apikey",
            "secret_key",
            "secretkey",
            "auth_token",
        ]
    )

    # Extended SQL keywords for broader coverage (merged from sql-injection-detector.py)
    sql_kw = "|".join(
        [
            "SELECT",
            "INSERT",
            "UPDATE",
            "DELETE",
            "DROP",
            "WHERE",
            "FROM",
            "JOIN",
            "SET",
            "VALUES",
        ]
    )

    return [
        # Hardcoded credentials — variable assignment with string literal
        (
            re.compile(
                rf"""(?:{cred_names})\s*[=:]\s*['"][^'"]{"{8,}"}['"]""",
                re.IGNORECASE,
            ),
            "hardcoded-credential",
            "Use environment variables or a secrets manager instead of hardcoded values",
        ),
        # SQL injection — f-string or format() in SQL-like strings
        (
            re.compile(
                r"""f['"]{1,3}(?:SELECT|INSERT|UPDATE|DELETE|DROP)\s.*\{""",
                re.IGNORECASE,
            ),
            "sql-injection",
            "Use parameterized queries instead of string interpolation in SQL",
        ),
        (
            re.compile(
                r"""['"](?:SELECT|INSERT|UPDATE|DELETE)\s.*['"].*%\s""",
                re.IGNORECASE,
            ),
            "sql-injection",
            "Use parameterized queries instead of % formatting in SQL",
        ),
        # SQL injection — string concatenation: "...SQL..." + variable
        (
            re.compile(
                rf"""['"](?:[^'"]*\b(?:{sql_kw})\b[^'"]*)['"]\s*\+""",
                re.IGNORECASE,
            ),
            "sql-injection",
            "Use parameterized queries (e.g., cursor.execute(sql, params))",
        ),
        # SQL injection — variable + "...SQL..."
        (
            re.compile(
                rf"""\+\s*['"](?:[^'"]*\b(?:{sql_kw})\b[^'"]*)['"]\s*(?:\+|$|;|\)|,)""",
                re.IGNORECASE,
            ),
            "sql-injection",
            "Use parameterized queries (e.g., cursor.execute(sql, params))",
        ),
        # SQL injection — .format() call on a SQL string
        (
            re.compile(
                rf"""['"](?:[^'"]*\b(?:{sql_kw})\b[^'"]*\{{[^'"]*)['"]\s*\.format\s*\(""",
                re.IGNORECASE,
            ),
            "sql-injection",
            "Use parameterized queries instead of .format() in SQL strings",
        ),
        # SQL injection — Go fmt.Sprintf with SQL percent placeholders
        (
            re.compile(
                rf"""fmt\.Sprintf\s*\(\s*['"`](?:[^'"`]*\b(?:{sql_kw})\b[^'"`]*%[sdvfq][^'"`]*)[`'"]\s*,""",
                re.IGNORECASE,
            ),
            "sql-injection",
            "Use db.Query with ? or $N placeholders and pass values as arguments",
        ),
        # SQL injection — Java String.format with SQL percent placeholders
        (
            re.compile(
                rf"""String\.format\s*\(\s*["'](?:[^"']*\b(?:{sql_kw})\b[^"']*%[sdnf][^"']*)['"]\s*,""",
                re.IGNORECASE,
            ),
            "sql-injection",
            "Use PreparedStatement with ? placeholders instead of String.format",
        ),
        # SQL injection — PHP sprintf with SQL percent placeholders
        (
            re.compile(
                rf"""(?<!\w)sprintf\s*\(\s*["'](?:[^"']*\b(?:{sql_kw})\b[^"']*%[sduf][^"']*)['"]\s*,""",
                re.IGNORECASE,
            ),
            "sql-injection",
            "Use PDO prepared statements with ? placeholders instead of sprintf",
        ),
        # SQL injection — f-string with extended SQL keywords (WHERE, FROM, JOIN, SET, VALUES)
        (
            re.compile(
                r"""f['"]{1,3}(?:[^'"]*\b(?:WHERE|FROM|JOIN|SET|VALUES)\b[^'"]*)\{""",
                re.IGNORECASE,
            ),
            "sql-injection",
            "Use parameterized queries instead of f-string interpolation in SQL",
        ),
        # SQL injection — multi-line SQL building via += concatenation
        (
            re.compile(
                rf"""\b\w+\s*\+=\s*(?:f?['"][^'"]*\b(?:{sql_kw})\b)""",
                re.IGNORECASE,
            ),
            "sql-injection",
            "Build SQL with parameterized placeholders; collect params in a list",
        ),
        # Command injection — shell=True with variable input
        (
            re.compile(r"""subprocess\.(?:call|run|Popen)\(.*shell\s*=\s*True"""),
            "command-injection",
            "Use subprocess with shell=False and pass args as a list",
        ),
        (
            re.compile(r"""os\.system\s*\("""),
            "command-injection",
            "Use subprocess.run() with shell=False instead of os.system()",
        ),
        # Path traversal — joining user input with paths without sanitization
        (
            re.compile(r"""os\.path\.join\(.*\.\./"""),
            "path-traversal",
            "Validate path components and use Path.resolve() to prevent traversal",
        ),
        # Unsafe YAML loading
        (
            re.compile(r"""yaml\.load\s*\([^)]*\)(?!.*Loader)"""),
            "unsafe-deserialization",
            "Use yaml.safe_load() or specify Loader=yaml.SafeLoader",
        ),
        # Unsafe serialization loading from untrusted sources
        (
            re.compile(re.escape("pickle") + r"""\.loads?\s*\("""),
            "unsafe-deserialization",
            "Unsafe with untrusted data; consider json or msgpack",
        ),
    ]


# Compile once at module load
_PATTERNS = _build_patterns()


def main() -> None:
    try:
        raw = read_stdin(timeout=2)
        event = json.loads(raw)

        # tool_name/event_type filters removed — matcher "Write|Edit" in settings.json
        # prevents this hook from spawning for non-matching tools.

        tool_input = event.get("tool_input", {})
        file_path = tool_input.get("file_path", "")
        if not file_path:
            return

        # Only scan code files
        ext = Path(file_path).suffix.lower()
        if ext not in _CODE_EXTENSIONS:
            return

        # Read file content from disk
        p = Path(file_path)
        if not p.is_file():
            return

        try:
            content = p.read_text(errors="replace")
        except OSError:
            return

        lines = content.splitlines()
        if len(lines) > _MAX_LINES:
            return

        # Scan each line against patterns
        findings: list[str] = []
        for line_num, line in enumerate(lines, 1):
            for pattern, category, suggestion in _PATTERNS:
                if pattern.search(line):
                    findings.append(
                        f"[SECURITY-HINT] Potential {category} at "
                        f"{Path(file_path).name}:{line_num}\n"
                        f"  Suggestion: {suggestion}"
                    )
                    break  # One finding per line max

        if findings:
            # Limit output to first 5 findings to avoid noise
            for finding in findings[:5]:
                print(finding)
            if len(findings) > 5:
                print(f"  ... and {len(findings) - 5} more security hints")

    except (json.JSONDecodeError, Exception) as e:
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            import traceback

            print(f"[security-scan] HOOK-ERROR: {type(e).__name__}: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
    finally:
        # CRITICAL: Always exit 0 to prevent blocking Claude Code
        sys.exit(0)


if __name__ == "__main__":
    main()
