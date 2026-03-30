#!/usr/bin/env python3
"""
Tests for the sql-injection-detector hook.

Run with: python3 hooks/tests/test_sql_injection_detector.py

Verifies:
- Python f-string with SQL keyword → warning
- Python + concatenation with SQL → warning
- Python .format() with SQL → warning
- Parameterized query → NO warning
- Go fmt.Sprintf with SQL → warning
- Non-SQL f-string → NO warning
- Non-code file → silent
- Missing file path → silent
- File not on disk → silent
- Malformed JSON → exit 0 (non-blocking)
- First 5 findings capped, overflow reported
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

HOOK_PATH = Path(__file__).parent.parent / "sql-injection-detector.py"


def run_hook(event: dict) -> tuple[str, str, int]:
    """Run the hook with given event and return (stdout, stderr, exit_code)."""
    result = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
    )
    return result.stdout, result.stderr, result.returncode


def run_hook_with_file(content: str, extension: str = ".py") -> tuple[str, str, int]:
    """Write content to a temp file then run the hook against it."""
    with tempfile.NamedTemporaryFile(suffix=extension, mode="w", delete=False, dir="/tmp") as f:
        f.write(content)
        tmp_path = f.name

    try:
        event = {
            "type": "PostToolUse",
            "tool_name": "Write",
            "tool_input": {"file_path": tmp_path},
        }
        return run_hook(event)
    finally:
        Path(tmp_path).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_python_fstring_sql_warning():
    """Python f-string with SQL keyword should emit a warning."""
    code = 'query = f"SELECT * FROM users WHERE id = {user_id}"\n'
    stdout, _, code_rc = run_hook_with_file(code)
    assert code_rc == 0
    assert "[sql-injection]" in stdout


def test_python_concatenation_sql_warning():
    """Python + concatenation with SQL context should emit a warning."""
    code = 'sql = "SELECT * FROM users WHERE name = " + name\n'
    stdout, _, rc = run_hook_with_file(code)
    assert rc == 0
    assert "[sql-injection]" in stdout
    assert "string-concatenation" in stdout


def test_python_format_sql_warning():
    """Python .format() on a SQL string should emit a warning."""
    code = 'query = "SELECT * FROM {} WHERE id = {}".format(table, user_id)\n'
    stdout, _, rc = run_hook_with_file(code)
    assert rc == 0
    assert "[sql-injection]" in stdout
    assert "format-injection" in stdout


def test_parameterized_query_no_warning():
    """Proper parameterized query should NOT emit a warning."""
    code = "sql = 'SELECT * FROM users WHERE id = ?'\ncursor.execute(sql, (user_id,))\n"
    stdout, _, rc = run_hook_with_file(code)
    assert rc == 0
    assert "[sql-injection]" not in stdout


def test_go_fmt_sprintf_warning():
    """Go fmt.Sprintf with SQL percent placeholders should emit a warning."""
    code = 'query := fmt.Sprintf("SELECT * FROM users WHERE id = %s", userID)\n'
    stdout, _, rc = run_hook_with_file(code, extension=".go")
    assert rc == 0
    assert "[sql-injection]" in stdout
    assert "sprintf-injection" in stdout


def test_non_sql_fstring_no_warning():
    """f-string that doesn't contain SQL keywords should NOT emit a warning."""
    code = 'msg = f"Hello, {name}! Welcome to {place}."\n'
    stdout, _, rc = run_hook_with_file(code)
    assert rc == 0
    assert "[sql-injection]" not in stdout


def test_non_code_file_silent():
    """Non-code file (e.g. .md) should be silently skipped."""
    with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False, dir="/tmp") as f:
        f.write('query = "SELECT * FROM users WHERE id = " + user_id\n')
        tmp_path = f.name

    try:
        event = {
            "type": "PostToolUse",
            "tool_name": "Write",
            "tool_input": {"file_path": tmp_path},
        }
        stdout, _, rc = run_hook(event)
        assert rc == 0
        assert stdout == ""
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def test_missing_file_path_silent():
    """Missing file_path in tool_input should produce no output."""
    event = {
        "type": "PostToolUse",
        "tool_name": "Write",
        "tool_input": {},
    }
    stdout, _, rc = run_hook(event)
    assert rc == 0
    assert stdout == ""


def test_file_not_on_disk_silent():
    """Nonexistent file should be silently skipped."""
    event = {
        "type": "PostToolUse",
        "tool_name": "Write",
        "tool_input": {"file_path": "/tmp/does_not_exist_xyz123.py"},
    }
    stdout, _, rc = run_hook(event)
    assert rc == 0
    assert stdout == ""


def test_malformed_json_exits_zero():
    """Malformed JSON input should not crash — hook must exit 0."""
    result = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input="this is not json",
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0


def test_findings_capped_at_five():
    """More than 5 findings should be capped with an overflow line."""
    lines = []
    for i in range(8):
        lines.append(f'sql{i} = "SELECT * FROM t WHERE a = " + val{i}')
    code = "\n".join(lines) + "\n"
    stdout, _, rc = run_hook_with_file(code)
    assert rc == 0
    assert "[sql-injection]" in stdout
    assert "more sql-injection hints" in stdout


def test_java_string_format_warning():
    """Java String.format with SQL placeholders should emit a warning."""
    code = 'String q = String.format("SELECT * FROM users WHERE id = %s", userId);\n'
    stdout, _, rc = run_hook_with_file(code, extension=".java")
    assert rc == 0
    assert "[sql-injection]" in stdout
    assert "sprintf-injection" in stdout


def test_fstring_where_clause_warning():
    """f-string with WHERE (not in SELECT set) should emit a warning."""
    code = 'q = f"WHERE user_id = {uid} AND active = 1"\n'
    stdout, _, rc = run_hook_with_file(code)
    assert rc == 0
    assert "[sql-injection]" in stdout
    assert "fstring-injection" in stdout


def test_multiline_sql_concat_warning():
    """Multi-line SQL building via += should emit a warning."""
    code = 'query += " WHERE user_id = " + str(uid)\n'
    stdout, _, rc = run_hook_with_file(code)
    assert rc == 0
    assert "[sql-injection]" in stdout


if __name__ == "__main__":
    tests = [
        test_python_fstring_sql_warning,
        test_python_concatenation_sql_warning,
        test_python_format_sql_warning,
        test_parameterized_query_no_warning,
        test_go_fmt_sprintf_warning,
        test_non_sql_fstring_no_warning,
        test_non_code_file_silent,
        test_missing_file_path_silent,
        test_file_not_on_disk_silent,
        test_malformed_json_exits_zero,
        test_findings_capped_at_five,
        test_java_string_format_warning,
        test_fstring_where_clause_warning,
        test_multiline_sql_concat_warning,
    ]

    print("Running sql-injection-detector hook tests...\n")
    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            print(f"  \u2713 {test.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  \u2717 {test.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"  \u2717 {test.__name__}: Exception - {e}")
            failed += 1

    print(f"\n{passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)
