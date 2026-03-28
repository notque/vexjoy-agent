#!/usr/bin/env python3
"""
Tests for the post-tool-lint-hint hook.

Run with: python3 hooks/tests/test_post_tool_lint.py
"""

import json
import subprocess
import sys
from pathlib import Path

HOOK_PATH = Path(__file__).parent.parent / "posttool-lint-hint.py"


def setup():
    """Clean up all seen extensions files before each test."""
    for f in Path("/tmp").glob("claude_lint_hints_seen_*.txt"):
        f.unlink(missing_ok=True)


def run_hook(event: dict) -> tuple[str, str, int]:
    """Run the hook with given event and return (stdout, stderr, exit_code)."""
    result = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
    )
    return result.stdout, result.stderr, result.returncode


def test_hints_for_python_files():
    """Hook should hint about ruff for Python files."""
    setup()
    event = {
        "type": "PostToolUse",
        "tool_name": "Write",
        "tool_input": {"file_path": "/some/path/script.py"},
    }
    stdout, stderr, code = run_hook(event)

    assert code == 0
    assert "[lint-hint]" in stdout
    assert "ruff" in stdout


def test_hints_for_go_files():
    """Hook should hint about gofmt for Go files."""
    setup()
    event = {
        "type": "PostToolUse",
        "tool_name": "Edit",
        "tool_input": {"file_path": "/some/path/main.go"},
    }
    stdout, stderr, code = run_hook(event)

    assert code == 0
    assert "[lint-hint]" in stdout
    assert "gofmt" in stdout


def test_hints_only_once_per_extension():
    """Hook should only hint once per extension per session."""
    setup()
    event = {
        "type": "PostToolUse",
        "tool_name": "Write",
        "tool_input": {"file_path": "/some/path/first.py"},
    }

    # First call should hint
    stdout1, _, _ = run_hook(event)
    assert "[lint-hint]" in stdout1

    # Second call with same extension should be silent
    event["tool_input"]["file_path"] = "/some/path/second.py"
    stdout2, _, _ = run_hook(event)
    assert stdout2 == ""


def test_ignores_non_lintable_files():
    """Hook should be silent for file types without linters."""
    setup()
    event = {
        "type": "PostToolUse",
        "tool_name": "Write",
        "tool_input": {"file_path": "/some/path/readme.md"},
    }
    stdout, stderr, code = run_hook(event)

    assert code == 0
    assert stdout == ""


def test_ignores_read_tool():
    """Read tool filtering is now handled by matcher 'Write|Edit' in settings.json.

    When called directly (without matcher), the hook processes any tool_name.
    This test verifies the hook still exits 0 (non-blocking) for any input.
    """
    setup()
    event = {
        "type": "PostToolUse",
        "tool_name": "Read",
        "tool_input": {"file_path": "/some/path/script.py"},
    }
    stdout, stderr, code = run_hook(event)

    assert code == 0
    # Note: hook may produce output since tool_name filter was moved to matcher


def test_handles_missing_file_path():
    """Hook should handle missing file_path gracefully."""
    setup()
    event = {
        "type": "PostToolUse",
        "tool_name": "Write",
        "tool_input": {},
    }
    stdout, stderr, code = run_hook(event)

    assert code == 0
    assert stdout == ""


if __name__ == "__main__":
    tests = [
        test_hints_for_python_files,
        test_hints_for_go_files,
        test_hints_only_once_per_extension,
        test_ignores_non_lintable_files,
        test_ignores_read_tool,
        test_handles_missing_file_path,
    ]

    print("Running PostToolUse hook tests...\n")
    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            print(f"  ✓ {test.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  ✗ {test.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"  ✗ {test.__name__}: Exception - {e}")
            failed += 1

    print(f"\n{passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)
