#!/usr/bin/env python3
# hook-version: 1.0.0
"""PostToolUse Hook: Auto-run tests after source file edits.

Fires after successful Write/Edit on source files. Detects language from
file extension, runs the matching test command, and returns truncated
results as additionalContext so the agent sees failures immediately.

Non-blocking (informational only). Debounced at 10s. 30s timeout.

ADR: adr/auto-test-after-edit-hook.md
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from stdin_timeout import read_stdin

# Extensions to skip (non-source files)
_SKIP_EXTENSIONS: set[str] = {
    ".md",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".cfg",
    ".txt",
    ".csv",
    ".lock",
    ".gitignore",
}

_DEBOUNCE_FILE = Path("/tmp/auto-test-last-run")
_DEBOUNCE_SECONDS = 10
_TIMEOUT_SECONDS = 30
_MAX_OUTPUT_LINES = 20


def _should_skip_extension(file_path: str) -> bool:
    """Return True if the file extension is in the skip list."""
    ext = Path(file_path).suffix.lower()
    return ext in _SKIP_EXTENSIONS or ext == ""


def _is_debounced() -> bool:
    """Return True if last test run was less than _DEBOUNCE_SECONDS ago."""
    try:
        if _DEBOUNCE_FILE.exists():
            last_run = float(_DEBOUNCE_FILE.read_text().strip())
            return (time.time() - last_run) < _DEBOUNCE_SECONDS
    except (ValueError, OSError):
        pass
    return False


def _update_debounce() -> None:
    """Write current timestamp to debounce file."""
    try:
        _DEBOUNCE_FILE.write_text(str(time.time()))
    except OSError:
        pass


def _get_test_command(file_path: str) -> str | None:
    """Map file extension to a test command. Returns None for unsupported languages."""
    ext = Path(file_path).suffix.lower()

    if ext == ".py":
        # Check if pyproject.toml exists for ruff config
        has_pyproject = Path("pyproject.toml").exists()
        ruff_config = " --config pyproject.toml" if has_pyproject else ""
        return (
            f"ruff check {file_path}{ruff_config} 2>&1 | tail -20; "
            f"python -m pytest --lf -x -q --tb=short 2>&1 | tail -20"
        )
    if ext == ".go":
        pkg_dir = str(Path(file_path).parent)
        return f"go test ./{pkg_dir}/... 2>&1 | tail -20"

    return None


def _run_tests(command: str) -> tuple[bool, str]:
    """Run test command with timeout. Returns (success, truncated_output)."""
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_SECONDS,
            cwd=os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()),
        )
        output = result.stdout + result.stderr
        lines = output.strip().splitlines()
        truncated = "\n".join(lines[-_MAX_OUTPUT_LINES:])
        return result.returncode == 0, truncated
    except subprocess.TimeoutExpired:
        return False, f"Tests timed out (>{_TIMEOUT_SECONDS}s), skipping auto-test"


def _format_result(file_path: str, success: bool, output: str) -> dict:
    """Format test results as additionalContext JSON."""
    filename = Path(file_path).name
    status = "PASS" if success else "FAIL"
    context = f"Auto-test results for {filename}:\n{status}\n{output}"
    return {"additionalContext": context}


def main() -> None:
    """Parse stdin, check conditions, run tests, emit results."""
    raw = read_stdin(timeout=2)
    if not raw:
        return

    try:
        event = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return

    # Extract file path from tool input
    tool_input = event.get("tool_input", event.get("input", {}))
    file_path = tool_input.get("file_path", "")

    if not file_path:
        return

    # Skip non-source files
    if _should_skip_extension(file_path):
        return

    # Debounce
    if _is_debounced():
        return

    # Language detection
    command = _get_test_command(file_path)
    if command is None:
        return

    # Run tests
    _update_debounce()
    success, output = _run_tests(command)

    # Emit results
    result = _format_result(file_path, success, output)
    print(json.dumps(result))


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        print(f"[auto-test] HOOK-CRASH: {type(e).__name__}: {e}", file=sys.stderr)
    finally:
        sys.exit(0)
