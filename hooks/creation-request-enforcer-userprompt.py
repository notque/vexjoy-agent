#!/usr/bin/env python3
# hook-version: 1.0.0
"""
UserPromptSubmit Hook: Creation Request ADR Enforcer

Fires at UserPromptSubmit time — BEFORE the model begins processing — and checks
whether the user's prompt contains creation keywords. If a creation request is
detected without a recent ADR session, it injects a strong context message
reminding Claude that an ADR is mandatory before any other action.

This hook complements the PreToolUse:Agent creation-protocol-enforcer.py by
catching the requirement earlier in the pipeline, before routing has occurred.

Allow-through conditions:
- No creation keywords found in prompt
- .adr-session.json exists and was modified within the last 900 seconds
- ADR_PROTOCOL_BYPASS=1 env var is set
"""

import json
import os
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from hook_utils import context_output, empty_output
from stdin_timeout import read_stdin

_BYPASS_ENV = "ADR_PROTOCOL_BYPASS"
_ADR_SESSION_FILE = ".adr-session.json"
_STALENESS_THRESHOLD_SECONDS = 900
_EVENT_NAME = "UserPromptSubmit"

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

_WARNING_TEXT = """\
[creation-enforcer] CREATION REQUEST DETECTED — ADR IS MANDATORY BEFORE ANY OTHER ACTION

You MUST complete these steps BEFORE dispatching any agent or writing any files:
1. Write ADR at adr/{name}.md (use kebab-case name describing what you're creating)
2. Register: python3 scripts/adr-query.py register --adr adr/{name}.md
3. Only THEN proceed to routing and agent dispatch.

Skipping this step will be blocked by the pretool-adr-creation-gate hook.\
"""


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
    """Run the UserPromptSubmit creation enforcement check."""
    debug = os.environ.get("CLAUDE_HOOKS_DEBUG")

    raw = read_stdin(timeout=2)
    try:
        event = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        empty_output(_EVENT_NAME).print_and_exit()

    # Bypass env var.
    if os.environ.get(_BYPASS_ENV) == "1":
        if debug:
            print(
                f"[creation-enforcer] Bypassed via {_BYPASS_ENV}=1",
                file=sys.stderr,
            )
        empty_output(_EVENT_NAME).print_and_exit()

    # UserPromptSubmit event uses the "prompt" field for the user message.
    prompt = event.get("prompt", "") if isinstance(event, dict) else ""
    if not prompt:
        empty_output(_EVENT_NAME).print_and_exit()

    # Check for creation keywords.
    if not _has_creation_keywords(prompt):
        if debug:
            print(
                "[creation-enforcer] No creation keywords found — allowing through",
                file=sys.stderr,
            )
        empty_output(_EVENT_NAME).print_and_exit()

    # Resolve project root.
    cwd_str = event.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR", ".")
    base_dir = Path(cwd_str).resolve()

    # Check whether a recent ADR session exists.
    if _adr_session_is_recent(base_dir):
        if debug:
            print(
                "[creation-enforcer] Recent .adr-session.json found — allowing through",
                file=sys.stderr,
            )
        empty_output(_EVENT_NAME).print_and_exit()

    if debug:
        print(
            "[creation-enforcer] Creation keywords found, no recent ADR session — injecting warning",
            file=sys.stderr,
        )

    # No recent ADR session — inject strong advisory context.
    context_output(_EVENT_NAME, _WARNING_TEXT).print_and_exit()


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
                f"[creation-enforcer] Error: {type(e).__name__}: {e}",
                file=sys.stderr,
            )
        # Fail open — never exit non-zero on unexpected errors.
        sys.exit(0)
