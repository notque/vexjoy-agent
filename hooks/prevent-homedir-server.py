#!/usr/bin/env python3
# hook-version: 1.1.0
"""
PreToolUse:Bash Hook: Home Directory HTTP Server Safety Gate

Blocks `python3 -m http.server` (and python/SimpleHTTPServer variants) when
the effective working directory is the user's home directory.

WHY: Running http.server from the home directory serves ~/.ssh, ~/.git-credentials,
and all personal files publicly. This is a hard block — the server must be
started from inside a project subdirectory.

SAFE conditions (allow through):
- Command does NOT contain http.server / SimpleHTTPServer
- Command uses --directory pointing to a non-home path
- Command starts with `cd ~/someproject` (changes into a project first)
- Effective CWD is not the home directory (is a subdirectory)

BLOCKED conditions:
- http.server/SimpleHTTPServer in command
- AND no --directory flag pointing to a non-home path
- AND effective CWD is the bare home directory

Exit codes:
  0 — always (non-blocking requirement); block is communicated via JSON output
"""

import json
import os
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants — all derived dynamically, no hardcoded paths
# ---------------------------------------------------------------------------

PROTECTED_HOME = str(Path.home())
EVENT_NAME = "PreToolUse"
DEBUG_LOG = "/tmp/claude_hook_debug.log"

# Patterns that indicate an http server invocation
HTTP_SERVER_PATTERNS = [
    r"\bpython3?\s+.*-m\s+http\.server\b",
    r"\bpython3?\s+.*-m\s+SimpleHTTPServer\b",
    r"\bhttp\.server\b",
    r"\bSimpleHTTPServer\b",
]

# --directory flag pointing somewhere — we need to verify where it points
DIRECTORY_FLAG_RE = re.compile(
    r"--directory\s+['\"]?([^\s'\"]+)['\"]?"
)

# cd into a subdir of home first (must have at least one subdir level)
CD_INTO_SUBDIR_RE = re.compile(
    r"\bcd\s+['\"]?(" + re.escape(PROTECTED_HOME) + r"/[^'\";\s]+)['\"]?"
)


def _debug(msg: str) -> None:
    """Non-blocking debug log."""
    try:
        with open(DEBUG_LOG, "a") as f:
            f.write(f"[prevent-homedir-server] {msg}\n")
    except Exception:
        pass


def _deny(reason: str) -> None:
    """Emit permissionDecision:deny and exit 0 (non-blocking)."""
    output = {
        "hookSpecificOutput": {
            "hookEventName": EVENT_NAME,
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }
    print(json.dumps(output))
    sys.exit(0)


def _allow() -> None:
    """Allow the tool call through — emit empty output."""
    print("{}")
    sys.exit(0)


def _is_http_server_command(command: str) -> bool:
    """Return True if the command invokes http.server or SimpleHTTPServer."""
    for pattern in HTTP_SERVER_PATTERNS:
        if re.search(pattern, command):
            return True
    return False


def _extract_directory_flag(command: str) -> str | None:
    """Return the --directory argument value, or None if absent."""
    m = DIRECTORY_FLAG_RE.search(command)
    return m.group(1) if m else None


def _directory_flag_is_safe(directory_value: str) -> bool:
    """Return True if --directory points outside the protected home."""
    # Normalize: resolve ~ shorthand
    if directory_value.startswith("~"):
        directory_value = PROTECTED_HOME + directory_value[1:]
    try:
        resolved = Path(directory_value).resolve()
        home = Path(PROTECTED_HOME).resolve()
        if resolved == home:
            return False  # Exactly home — dangerous
        if str(resolved).startswith(str(home) + "/"):
            return True  # Subdir of home — safe
        return True  # Outside home entirely — safe
    except Exception:
        return False  # Can't resolve — err on the side of caution


def _command_cds_into_subdir(command: str) -> bool:
    """Return True if the command cd's into a subdir of home before serving."""
    return bool(CD_INTO_SUBDIR_RE.search(command))


def main() -> None:
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            _allow()

        data = json.loads(raw)

        # Normalize: support both 'tool_input' (Claude) and 'input' (other runtimes)
        tool_input = data.get("tool_input") or data.get("input") or {}
        command = tool_input.get("command", "")

        # Only act on http.server invocations
        if not _is_http_server_command(command):
            _allow()

        _debug(f"http.server command detected: {command[:120]}")

        # --- Check 1: --directory flag pointing to a safe path ---
        dir_flag = _extract_directory_flag(command)
        if dir_flag is not None:
            if _directory_flag_is_safe(dir_flag):
                _debug(f"allow: --directory={dir_flag} is safe")
                _allow()
            else:
                _debug(f"block: --directory={dir_flag} points to home")
                _deny(
                    f"BLOCKED: http.server with --directory={dir_flag} would serve "
                    f"the home directory publicly.\n\n"
                    f"This exposes ~/.ssh, ~/.git-credentials, and all personal files.\n\n"
                    f"Fix: cd into your project directory first, e.g.:\n"
                    f"  cd ~/myproject && python3 -m http.server 8080"
                )

        # --- Check 2: command explicitly cd's into a safe subdir first ---
        if _command_cds_into_subdir(command):
            _debug("allow: command cd's into a subdir first")
            _allow()

        # --- Check 3: inspect the session CWD ---
        # Claude Code exposes cwd via the event envelope.
        # Fall back to CLAUDE_CWD env var or os.getcwd() (hook process CWD
        # reflects the session CWD in Claude Code).
        session_cwd = (
            data.get("cwd")
            or data.get("session", {}).get("cwd")
            or os.environ.get("CLAUDE_CWD")
            or os.getcwd()
        )

        _debug(f"session_cwd={session_cwd}")

        cwd_norm = str(session_cwd).rstrip("/")
        home_norm = PROTECTED_HOME.rstrip("/")

        if cwd_norm == home_norm:
            _debug(f"block: CWD is home ({session_cwd})")
            _deny(
                f"BLOCKED: http.server would serve your home directory publicly.\n\n"
                f"Current directory: {session_cwd}\n\n"
                f"Why this is dangerous: serving your home directory exposes:\n"
                f"  - ~/.ssh/  (SSH private keys)\n"
                f"  - ~/.git-credentials  (stored Git tokens)\n"
                f"  - All dotfiles and personal projects\n\n"
                f"Fix: cd into your project directory first, then start the server:\n"
                f"  cd ~/myproject\n"
                f"  python3 -m http.server 8080"
            )

        # CWD is a subdir or somewhere else entirely — allow
        _debug(f"allow: CWD {session_cwd} is not home")
        _allow()

    except json.JSONDecodeError as e:
        _debug(f"JSON parse error: {e}")
        _allow()
    except Exception as e:
        _debug(f"unexpected error: {e}")
        _allow()


if __name__ == "__main__":
    main()
