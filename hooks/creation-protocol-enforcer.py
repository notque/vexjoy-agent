#!/usr/bin/env python3
# hook-version: 1.0.0
"""
PreToolUse:Agent Hook: Creation Protocol Enforcer

Soft-warns when an Agent dispatch appears to be for a creation request
but no ADR has been written yet this session (i.e. .adr-session.json
does not exist or was last modified more than 900 seconds ago).

This is a SOFT WARN — exit 0 only (never blocks).

Detection logic:
- Tool is Agent
- tool_input["prompt"] contains creation keywords
- .adr-session.json in project root either does not exist or is stale (>900s)

Allow-through conditions:
- Tool is not Agent
- No creation keywords found in prompt
- .adr-session.json exists and was modified within the last 900 seconds
- ADR_PROTOCOL_BYPASS=1 env var
"""

import json
import os
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from stdin_timeout import read_stdin

_BYPASS_ENV = "ADR_PROTOCOL_BYPASS"
_ADR_SESSION_FILE = ".adr-session.json"
_STALENESS_THRESHOLD_SECONDS = 900

_CREATION_KEYWORDS = [
    "create",
    "scaffold",
    "build a new",
    "build a ",
    "add a new",
    "add new",
    "new agent",
    "new skill",
    "new pipeline",
    "new hook",
    "new feature",
    "new workflow",
    "new plugin",
    "implement new",
    "i need a ",
    "i need an ",
    "we need a ",
    "we need an ",
]

_WARNING_LINES = [
    "[creation-protocol-enforcer] Creation request detected but no recent ADR session found.",
    "/do Phase 4 Step 0 requires: (1) Write ADR at adr/{name}.md, (2) Register via adr-query.py register, THEN dispatch agent.",
    "If ADR was already written, set ADR_PROTOCOL_BYPASS=1 to suppress this warning.",
]


def _has_creation_keywords(prompt: str) -> bool:
    """Return True if the prompt contains any creation keyword (case-insensitive)."""
    lower = prompt.lower()
    return any(kw in lower for kw in _CREATION_KEYWORDS)


def _adr_session_is_recent(base_dir: Path) -> bool:
    """Return True if .adr-session.json exists and was modified within the threshold."""
    adr_session_path = base_dir / _ADR_SESSION_FILE
    if not adr_session_path.exists():
        return False
    try:
        mtime = os.path.getmtime(adr_session_path)
        age = time.time() - mtime
        return age <= _STALENESS_THRESHOLD_SECONDS
    except OSError:
        return False


def main() -> None:
    """Run the creation protocol enforcement check."""
    debug = os.environ.get("CLAUDE_HOOKS_DEBUG")

    raw = read_stdin(timeout=2)
    try:
        event = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    # Filter: only act on Agent tool dispatches.
    tool_name = event.get("tool_name", "")
    if tool_name != "Agent":
        sys.exit(0)

    # Bypass env var.
    if os.environ.get(_BYPASS_ENV) == "1":
        if debug:
            print(
                f"[creation-protocol-enforcer] Bypassed via {_BYPASS_ENV}=1",
                file=sys.stderr,
            )
        sys.exit(0)

    tool_input = event.get("tool_input", {})
    prompt = tool_input.get("prompt", "")
    if not prompt:
        sys.exit(0)

    # Check for creation keywords.
    if not _has_creation_keywords(prompt):
        if debug:
            print(
                "[creation-protocol-enforcer] No creation keywords found — allowing through",
                file=sys.stderr,
            )
        sys.exit(0)

    # Resolve project root.
    cwd_str = event.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR", ".")
    base_dir = Path(cwd_str).resolve()

    # Check whether a recent ADR session exists.
    if _adr_session_is_recent(base_dir):
        if debug:
            print(
                "[creation-protocol-enforcer] Recent .adr-session.json found — allowing through",
                file=sys.stderr,
            )
        sys.exit(0)

    # No recent ADR session — emit soft warning to stdout (context injection).
    print("\n".join(_WARNING_LINES))
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            traceback.print_exc(file=sys.stderr)
        else:
            print(
                f"[creation-protocol-enforcer] Error: {type(e).__name__}: {e}",
                file=sys.stderr,
            )
        # Fail open — never exit non-zero on unexpected errors.
        sys.exit(0)
