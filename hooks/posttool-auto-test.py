#!/usr/bin/env python3
# hook-version: 1.0.0
"""PostToolUse Hook: Auto-run tests after source file edits.

Fires after successful Write/Edit on source files. Detects language from
file extension, runs the matching test command, and returns truncated
results as additionalContext so the agent sees failures immediately.

Non-blocking (informational only). Debounced at 10s. 15s timeout.
Sanitizes output to strip potential secrets before returning context.

ADR: adr/auto-test-after-edit-hook.md
"""

import fcntl
import json
import os
import re
import signal
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
_DEBOUNCE_LOCK = Path("/tmp/auto-test-last-run.lock")
_DEBOUNCE_SECONDS = 10
_TIMEOUT_SECONDS = 15
_MAX_OUTPUT_LINES = 20

# Patterns for lines that may contain secrets (matched case-insensitively)
_SECRET_LINE_RE = re.compile(
    r"^[A-Z][A-Z0-9_]*=",  # ANY_CAPS_KEY=value
)
_SECRET_KEY_WORDS = frozenset(
    {
        "PASSWORD",
        "TOKEN",
        "SECRET",
        "SECRET_KEY",
        "API_KEY",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "DATABASE_URL",
        "PRIVATE_KEY",
        "CREDENTIAL",
    }
)


def _should_skip_extension(file_path: str) -> bool:
    """Return True if the file extension is in the skip list."""
    ext = Path(file_path).suffix.lower()
    return ext in _SKIP_EXTENSIONS or ext == ""


def _debounce_check_and_update() -> bool:
    """Atomically check debounce and update if not debounced.

    Uses fcntl.flock so two concurrent hooks cannot both pass the check.
    Returns True if this invocation should proceed (not debounced).
    Returns False if debounced (caller should skip).
    """
    try:
        fd = os.open(str(_DEBOUNCE_LOCK), os.O_CREAT | os.O_RDWR, 0o644)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            # Read existing timestamp
            now = time.time()
            try:
                if _DEBOUNCE_FILE.exists():
                    last_run = float(_DEBOUNCE_FILE.read_text().strip())
                    if (now - last_run) < _DEBOUNCE_SECONDS:
                        return False
            except (ValueError, OSError):
                pass
            # Not debounced — claim the slot
            _DEBOUNCE_FILE.write_text(str(now))
            return True
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)
    except OSError:
        # If locking fails, proceed anyway (fail-open for hooks)
        return True


def _get_test_command(file_path: str) -> list[list[str]] | None:
    """Map file extension to test commands as argument lists.

    Returns a list of command arg-lists, or None for unsupported languages.
    Each inner list is passed to subprocess with shell=False.
    """
    ext = Path(file_path).suffix.lower()

    if ext == ".py":
        has_pyproject = Path("pyproject.toml").exists()
        ruff_cmd = ["ruff", "check", file_path]
        if has_pyproject:
            ruff_cmd.extend(["--config", "pyproject.toml"])
        pytest_cmd = ["python", "-m", "pytest", "--lf", "-x", "-q", "--tb=short"]
        return [ruff_cmd, pytest_cmd]
    if ext == ".go":
        pkg_dir = str(Path(file_path).parent)
        return [["go", "test", f"./{pkg_dir}/..."]]

    return None


def _sanitize_output(text: str) -> str:
    """Strip lines that may contain secrets or env-var assignments."""
    safe_lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        # Skip lines matching ALL_CAPS_KEY=value pattern
        if _SECRET_LINE_RE.match(stripped):
            # Check if the key portion contains a known secret keyword
            key = stripped.split("=", 1)[0]
            if any(word in key.upper() for word in _SECRET_KEY_WORDS):
                safe_lines.append(f"{key}=<REDACTED>")
                continue
        safe_lines.append(line)
    return "\n".join(safe_lines)


def _run_single_command(cmd: list[str], cwd: str) -> tuple[int, str]:
    """Run a single command with timeout, killing the process group on timeout."""
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        cwd=cwd,
        start_new_session=True,
    )
    try:
        stdout, _ = proc.communicate(timeout=_TIMEOUT_SECONDS)
        return proc.returncode, stdout or ""
    except subprocess.TimeoutExpired:
        # Kill the entire process group to avoid orphans
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except OSError:
            pass
        proc.wait(timeout=5)
        return -1, f"Command timed out (>{_TIMEOUT_SECONDS}s)"


def _run_tests(commands: list[list[str]]) -> tuple[bool, str]:
    """Run test commands sequentially. Returns (all_passed, truncated_output)."""
    cwd = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
    all_output: list[str] = []
    all_passed = True

    for cmd in commands:
        returncode, output = _run_single_command(cmd, cwd)
        all_output.append(output)
        if returncode != 0:
            all_passed = False

    combined = "\n".join(all_output)
    sanitized = _sanitize_output(combined)
    lines = sanitized.strip().splitlines()
    truncated = "\n".join(lines[-_MAX_OUTPUT_LINES:])
    return all_passed, truncated


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

    # Language detection (before debounce to avoid claiming the slot for unsupported files)
    commands = _get_test_command(file_path)
    if commands is None:
        return

    # Atomic debounce check-and-update
    if not _debounce_check_and_update():
        return

    # Run tests
    success, output = _run_tests(commands)

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
