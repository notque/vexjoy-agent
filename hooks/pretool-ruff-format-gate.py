#!/usr/bin/env python3
# hook-version: 1.0.0
"""
PreToolUse:Bash Hook: Ruff Format Gate

Blocks git push when ruff format --check finds formatting violations.
Forces agents to run ruff format before pushing, preventing CI failures.

This is a HARD GATE — exits 0 with JSON permissionDecision:deny to block the Bash tool.

Detection logic:
- Tool is Bash
- Command contains 'git push'
- pyproject.toml with [tool.ruff] exists in project root
- ruff format --check . --config pyproject.toml exits non-zero

Allow-through conditions:
- Command does not contain 'git push'
- No pyproject.toml with [tool.ruff] section (non-Python project)
- ruff format --check passes (no violations)
- RUFF_FORMAT_GATE_BYPASS=1 env var

Exit code semantics:
- Always exits 0 (non-blocking requirement)
- Deny signal delivered via JSON permissionDecision:deny on stdout
"""

import json
import os
import re
import subprocess
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from stdin_timeout import read_stdin

_BYPASS_ENV = "RUFF_FORMAT_GATE_BYPASS"


def _find_project_root(cwd: str | None) -> Path | None:
    """Walk up from cwd to find the nearest pyproject.toml with [tool.ruff]."""
    if not cwd:
        return None
    candidate = Path(cwd).resolve()
    for _ in range(6):  # Max 6 levels up
        toml = candidate / "pyproject.toml"
        if toml.is_file():
            try:
                content = toml.read_text(encoding="utf-8")
                if "[tool.ruff]" in content:
                    return candidate
            except OSError:
                pass
        parent = candidate.parent
        if parent == candidate:
            break
        candidate = parent
    return None


def _extract_push_cwd(command: str, default_cwd: str | None) -> str | None:
    """Extract the effective cwd from a git push command string.

    Detects:
    - ``cd <path> && git push``
    - ``git -C <path> push``
    """
    m = re.match(r'cd\s+(?:"([^"]+)"|(\S+))\s*(?:&&|;)', command.lstrip())
    if m:
        p = (m.group(1) or m.group(2) or "").strip()
        if p:
            return p

    m = re.search(r'\bgit\s+-C\s+(?:"([^"]+)"|(\S+))', command)
    if m:
        return m.group(1) or m.group(2)

    return default_cwd


def _run_ruff_format_check(project_root: Path) -> tuple[int, str]:
    """Run ruff format --check in project_root.

    Returns (return_code, combined_output).
    """
    try:
        result = subprocess.run(
            ["ruff", "format", "--check", ".", "--config", "pyproject.toml"],
            capture_output=True,
            text=True,
            timeout=15,
            cwd=str(project_root),
        )
        output = (result.stdout + result.stderr).strip()
        return result.returncode, output
    except FileNotFoundError:
        # ruff not installed — fail open, don't block
        return 0, ""
    except subprocess.TimeoutExpired:
        return 0, ""
    except OSError:
        return 0, ""


def main() -> None:
    debug = os.environ.get("CLAUDE_HOOKS_DEBUG")

    raw = read_stdin(timeout=2)
    try:
        event = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    if not isinstance(event, dict):
        sys.exit(0)

    command = event.get("tool_input", {}).get("command", "")
    if not command:
        sys.exit(0)

    # Only fire on git push commands
    if not re.search(r"\bgit\s+push\b", command):
        sys.exit(0)

    # Bypass env var
    if os.environ.get(_BYPASS_ENV) == "1":
        if debug:
            print("[ruff-format-gate] Bypassed via RUFF_FORMAT_GATE_BYPASS=1", file=sys.stderr)
        sys.exit(0)

    default_cwd = event.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR")
    effective_cwd = _extract_push_cwd(command, default_cwd)

    project_root = _find_project_root(effective_cwd)
    if project_root is None:
        if debug:
            print("[ruff-format-gate] No pyproject.toml with [tool.ruff] found — allowing through", file=sys.stderr)
        sys.exit(0)

    if debug:
        print(f"[ruff-format-gate] Running ruff format --check in {project_root}", file=sys.stderr)

    returncode, output = _run_ruff_format_check(project_root)

    if returncode == 0:
        if debug:
            print("[ruff-format-gate] ruff format --check passed — allowing push", file=sys.stderr)
        sys.exit(0)

    # Violations found — block the push
    print(
        f"[ruff-format-gate] BLOCKED: ruff format --check found violations. Run: ruff format . --config pyproject.toml",
        file=sys.stderr,
    )
    if output and debug:
        print(f"[ruff-format-gate] ruff output: {output}", file=sys.stderr)

    deny_reason = (
        "ruff format --check found formatting violations. "
        "Run `ruff format . --config pyproject.toml` to fix them, then push again. "
        "Bypass with RUFF_FORMAT_GATE_BYPASS=1 if this is a false positive."
    )
    if output:
        # Include a snippet of ruff's output in the reason for visibility
        snippet = output[:300] + ("..." if len(output) > 300 else "")
        deny_reason = f"{deny_reason}\n\nruff output:\n{snippet}"

    deny_output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": deny_reason,
        }
    }
    print(json.dumps(deny_output))
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise  # Let sys.exit(0) propagate normally
    except Exception as e:
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            traceback.print_exc(file=sys.stderr)
        else:
            print(f"[ruff-format-gate] Error: {type(e).__name__}: {e}", file=sys.stderr)
        # Crashed hook must fail open — never block tools.
    finally:
        sys.exit(0)
