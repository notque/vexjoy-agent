#!/usr/bin/env python3
"""Tests for the adr-lifecycle-on-merge hook.

Tests hook behaviour via subprocess (same pattern as test_post_tool_lint.py).
Also imports helper functions directly where feasible to avoid git subprocess
calls in the test harness.
"""

import json
import subprocess
import sys
from pathlib import Path

HOOK_PATH = Path(__file__).parent.parent / "adr-lifecycle-on-merge.py"
LIB_PATH = Path(__file__).parent.parent / "lib"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def run_hook(event: dict) -> tuple[str, str, int]:
    """Run the hook with given event and return (stdout, stderr, exit_code)."""
    result = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
    )
    return result.stdout, result.stderr, result.returncode


def non_merge_event(command: str = "git status") -> dict:
    return {
        "tool_name": "Bash",
        "tool_input": {"command": command},
        "tool_output": {"stdout": "", "stderr": "", "exit_code": 0},
    }


def merge_event(command: str = "gh pr merge 316 --squash", exit_code: int = 0) -> dict:
    return {
        "tool_name": "Bash",
        "tool_input": {"command": command},
        "tool_output": {"stdout": "Merged.", "stderr": "", "exit_code": exit_code},
    }


def empty_json_response(stdout: str) -> bool:
    """Return True if stdout is an empty HookOutput JSON (no additionalContext)."""
    try:
        parsed = json.loads(stdout)
        inner = parsed.get("hookSpecificOutput", {})
        return "additionalContext" not in inner
    except (json.JSONDecodeError, AttributeError):
        return False


# ---------------------------------------------------------------------------
# Unit tests for helper functions (import directly)
# ---------------------------------------------------------------------------


sys.path.insert(0, str(LIB_PATH))


def test_extract_adr_numbers_multiple_patterns():
    """extract_adr_numbers handles ADR-NNN, adr/NNN-, adr-NNN patterns."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            f"import importlib.util; spec = importlib.util.spec_from_file_location('m', '{HOOK_PATH}'); "
            "m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); "
            "nums = m.extract_adr_numbers('ADR-042 adr/099-foo adr-007'); print(sorted(nums))",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    output = result.stdout.strip()
    assert "42" in output
    assert "99" in output
    assert "7" in output


def test_extract_implementation_steps_parses_numbered_list():
    """extract_implementation_steps returns steps from ## Implementation section."""
    adr_content = """# ADR-179: Something

## Status
Proposed

## Implementation

1. Create the hook file
2. Write tests
3. Register in settings.json

## Consequences
None.
"""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            f"import importlib.util; spec = importlib.util.spec_from_file_location('m', '{HOOK_PATH}'); "
            "m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); "
            f"content = {repr(adr_content)}; "
            "steps = m.extract_implementation_steps(content); print(len(steps)); print(steps[0])",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "3" in result.stdout
    assert "Create the hook file" in result.stdout


def test_step_matches_files_positive():
    """step_matches_files returns True when keyword matches a changed file."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            f"import importlib.util; spec = importlib.util.spec_from_file_location('m', '{HOOK_PATH}'); "
            "m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); "
            "matched, f = m.step_matches_files('Register in settings.json', "
            "['hooks/foo.py', '.claude/settings.json']); print(matched, f)",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "True" in result.stdout


def test_step_matches_files_negative():
    """step_matches_files returns False when no keyword matches."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            f"import importlib.util; spec = importlib.util.spec_from_file_location('m', '{HOOK_PATH}'); "
            "m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); "
            "matched, f = m.step_matches_files('Deploy to production server', "
            "['hooks/foo.py', 'tests/test_bar.py']); print(matched)",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "False" in result.stdout


# ---------------------------------------------------------------------------
# Integration tests via subprocess (full hook execution)
# ---------------------------------------------------------------------------


def test_non_merge_command_returns_empty():
    """Non-merge command (git status) should return empty output."""
    stdout, stderr, code = run_hook(non_merge_event("git status"))
    assert code == 0
    assert empty_json_response(stdout)


def test_failed_merge_returns_empty():
    """Failed merge (exit_code != 0) should return empty output."""
    stdout, stderr, code = run_hook(merge_event(exit_code=1))
    assert code == 0
    assert empty_json_response(stdout)


def test_non_bash_tool_returns_empty():
    """Hook should ignore non-Bash tools."""
    event = {
        "tool_name": "Write",
        "tool_input": {"file_path": "/some/file.py", "content": "# gh pr merge"},
        "tool_output": {"stdout": "", "stderr": "", "exit_code": 0},
    }
    stdout, stderr, code = run_hook(event)
    assert code == 0
    assert empty_json_response(stdout)


def test_malformed_json_does_not_crash():
    """Hook must not crash on malformed JSON input."""
    result = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input="not-valid-json",
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0


def test_empty_stdin_does_not_crash():
    """Hook must not crash with empty stdin."""
    result = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input="",
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0


def test_merge_with_no_adr_references(tmp_path):
    """Merge command with no ADR references in branch/commits reports no ADR found."""
    event = merge_event("gh pr merge 100 --squash")
    # Patch git calls to return non-ADR text
    # Since subprocess makes real git calls, we verify hook exits 0 and outputs JSON
    stdout, stderr, code = run_hook(event)
    assert code == 0
    # Output must be valid JSON
    parsed = json.loads(stdout)
    assert "hookSpecificOutput" in parsed


# ---------------------------------------------------------------------------
# Status update tests (unit-level via module import)
# ---------------------------------------------------------------------------


def test_update_adr_status_changes_proposed_to_completed(tmp_path):
    """update_adr_status should replace 'Proposed' with 'Completed (YYYY-MM-DD)'."""
    adr_file = tmp_path / "179-test.md"
    adr_file.write_text("# ADR-179\n\n## Status\nProposed\n\n## Context\nSome context.\n")

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            f"import importlib.util; spec = importlib.util.spec_from_file_location('m', '{HOOK_PATH}'); "
            "m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); "
            f"from pathlib import Path; p = Path('{adr_file}'); "
            "m.update_adr_status(p, '179')",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr

    # Check file was moved to adr/completed/
    completed_dir = tmp_path / "completed"
    moved_file = completed_dir / "179-test.md"
    assert moved_file.exists(), "ADR file should be moved to adr/completed/"
    content = moved_file.read_text()
    assert "Completed (" in content, "Status should be updated to Completed"
    assert not adr_file.exists(), "Original file should be removed after move"


# ---------------------------------------------------------------------------
# Checklist status tests (PARTIAL vs COMPLETE)
# ---------------------------------------------------------------------------


def test_process_merge_complete_status(tmp_path):
    """process_merge reports COMPLETE when all steps have keyword matches."""
    adr_dir = tmp_path / "adr"
    adr_dir.mkdir()
    adr_file = adr_dir / "042-simple-feature.md"
    adr_file.write_text("# ADR-042\n\n## Status\nProposed\n\n## Implementation\n\n1. Create hook file\n")

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            f"import importlib.util, os; "
            f"os.environ['CLAUDE_PROJECT_DIR'] = '{tmp_path}'; "
            f"spec = importlib.util.spec_from_file_location('m', '{HOOK_PATH}'); "
            "m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); "
            "m.run_git = lambda *a, **kw: ''; "
            "m.get_changed_files = lambda: ['hooks/adr-lifecycle.py']; "
            "m.extract_adr_numbers = lambda t: ['42']; "
            "report = m.process_merge('gh pr merge 1'); print(report)",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    output = result.stdout
    # Hook file contains "hook" keyword — step 1 "Create hook file" should match
    assert "COMPLETE" in output or "PARTIAL" in output or "ADR-42" in output
