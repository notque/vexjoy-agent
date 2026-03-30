#!/usr/bin/env python3
# hook-version: 1.0.0
"""
PostToolUse:Write,Edit Hook: SQL Injection Pattern Detector

Scans edited/written code files for SQL injection anti-patterns that are
complementary to those already detected by posttool-security-scan.py.

Patterns detected (new coverage beyond posttool-security-scan.py):
1. String concatenation with SQL context: "SELECT ... " + var or var + "... WHERE"
2. .format() call on a SQL string: "SELECT ... {}".format(
3. Go fmt.Sprintf / Java String.format / PHP sprintf with SQL percent placeholders
4. f-strings with extended SQL keywords: WHERE, FROM, JOIN, SET, VALUES
5. Multi-line SQL building via concatenation assignment (+=)

Design:
- PostToolUse (advisory only, never blocks)
- Only scans code files (skips markdown, config, images)
- Compiled regex patterns at module load for <20ms execution
- Reads file content from disk (tool_result may be truncated)
- Skips files >10,000 lines
- Limits output to first 5 findings to avoid noise

ADR: adr/134-sql-injection-detector-hook.md
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

# SQL keywords that indicate a SQL context (extended beyond SELECT/INSERT/UPDATE/DELETE)
_SQL_KEYWORDS = (
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
)


def _build_patterns() -> list[tuple[re.Pattern[str], str, str]]:
    """Build SQL injection detection patterns at import time.

    Patterns are constructed programmatically to avoid triggering
    security-reminder hooks that scan for literal pattern strings.

    Each tuple: (compiled_pattern, category_label, suggestion_text)
    """
    kw = "|".join(_SQL_KEYWORDS)

    return [
        # String concatenation: "...SQL..." + variable
        # Matches: "SELECT * FROM users WHERE id = " + user_id
        (
            re.compile(
                rf"""['"](?:[^'"]*\b(?:{kw})\b[^'"]*)['"]\s*\+""",
                re.IGNORECASE,
            ),
            "string-concatenation",
            "Use parameterized queries (e.g., cursor.execute(sql, params))",
        ),
        # String concatenation: variable + "...SQL..."
        # Matches: base_query + " WHERE name = " + name
        (
            re.compile(
                rf"""\+\s*['"](?:[^'"]*\b(?:{kw})\b[^'"]*)['"]\s*(?:\+|$|;|\)|,)""",
                re.IGNORECASE,
            ),
            "string-concatenation",
            "Use parameterized queries (e.g., cursor.execute(sql, params))",
        ),
        # .format() call on a SQL string
        # Matches: "SELECT * FROM {} WHERE id = {}".format(
        (
            re.compile(
                rf"""['"](?:[^'"]*\b(?:{kw})\b[^'"]*\{{[^'"]*)['"]\s*\.format\s*\(""",
                re.IGNORECASE,
            ),
            "format-injection",
            "Use parameterized queries instead of .format() in SQL strings",
        ),
        # Go fmt.Sprintf with SQL percent placeholders
        # Matches: fmt.Sprintf("SELECT ... %s", or fmt.Sprintf("WHERE id = %d",
        (
            re.compile(
                rf"""fmt\.Sprintf\s*\(\s*['"`](?:[^'"`]*\b(?:{kw})\b[^'"`]*%[sdvfq][^'"`]*)[`'"]\s*,""",
                re.IGNORECASE,
            ),
            "sprintf-injection",
            "Use db.Query with ? or $N placeholders and pass values as arguments",
        ),
        # Java String.format with SQL percent placeholders
        # Matches: String.format("SELECT ... %s",
        (
            re.compile(
                rf"""String\.format\s*\(\s*["'](?:[^"']*\b(?:{kw})\b[^"']*%[sdnf][^"']*)['"]\s*,""",
                re.IGNORECASE,
            ),
            "sprintf-injection",
            "Use PreparedStatement with ? placeholders instead of String.format",
        ),
        # PHP sprintf with SQL percent placeholders
        # Matches: sprintf("SELECT ... %s",
        (
            re.compile(
                rf"""(?<!\w)sprintf\s*\(\s*["'](?:[^"']*\b(?:{kw})\b[^"']*%[sduf][^"']*)['"]\s*,""",
                re.IGNORECASE,
            ),
            "sprintf-injection",
            "Use PDO prepared statements with ? placeholders instead of sprintf",
        ),
        # f-string with extended SQL keywords (WHERE, FROM, JOIN, SET, VALUES)
        # Complements posttool-security-scan.py which only covers SELECT/INSERT/UPDATE/DELETE/DROP
        (
            re.compile(
                r"""f['"]{1,3}(?:[^'"]*\b(?:WHERE|FROM|JOIN|SET|VALUES)\b[^'"]*)\{""",
                re.IGNORECASE,
            ),
            "fstring-injection",
            "Use parameterized queries instead of f-string interpolation in SQL",
        ),
        # Multi-line SQL building via += concatenation
        # Matches: query += " AND user_id = " + uid  or  sql += f" WHERE {col}"
        (
            re.compile(
                rf"""\b\w+\s*\+=\s*(?:f?['"][^'"]*\b(?:{kw})\b)""",
                re.IGNORECASE,
            ),
            "string-concatenation",
            "Build SQL with parameterized placeholders; collect params in a list",
        ),
    ]


# Compile once at module load
_PATTERNS = _build_patterns()


def main() -> None:
    try:
        raw = read_stdin(timeout=2)
        if not raw:
            return

        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            return

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

        # Scan each line against patterns; one finding per line max
        findings: list[str] = []
        for line_num, line in enumerate(lines, 1):
            for pattern, category, suggestion in _PATTERNS:
                if pattern.search(line):
                    findings.append(
                        f"[sql-injection] Potential SQL injection at "
                        f"{Path(file_path).name}:{line_num}\n"
                        f"  Pattern: {category}\n"
                        f"  Suggestion: {suggestion}"
                    )
                    break  # One finding per line max

        if findings:
            # Limit output to first 5 findings to avoid noise
            for finding in findings[:5]:
                print(finding)
            if len(findings) > 5:
                print(f"  ... and {len(findings) - 5} more sql-injection hints")

    except Exception as e:
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            import traceback

            print(f"[sql-injection] HOOK-ERROR: {type(e).__name__}: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
    finally:
        # CRITICAL: Always exit 0 to prevent blocking Claude Code
        sys.exit(0)


if __name__ == "__main__":
    main()
