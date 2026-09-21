#!/usr/bin/env python3
# hook-version: 4.0.0
"""Persist mandatory /d and /do obligations before optional classification.

Classification timeouts never remove the pending obligation. Stop and native
Agent/Task dispatch are gated separately by router-required-gate.py.
"""

import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))

from hook_utils import context_output, empty_output, hook_error
from stdin_timeout import read_stdin

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from router_gate import clear_required_router, continue_required_router, get_required_router, set_required_router
from router_gate import session_id as current_session_id

EVENT_NAME = "UserPromptSubmit"

DETECT_PATTERN = re.compile(r"^\s*[/\$](do|d)(?=\s|$)\s*", re.IGNORECASE)
ENVELOPE_PATTERN = re.compile(
    r"^\s*<command-name>\s*/?(do|d)\s*</command-name>.*?"
    r"<command-args>(.*?)</command-args>",
    re.IGNORECASE | re.DOTALL,
)


def extract_router(prompt: str) -> tuple[str, str] | None:
    match = DETECT_PATTERN.match(prompt)
    if match:
        return match.group(1).lower(), prompt[match.end() :].strip()
    match = ENVELOPE_PATTERN.match(prompt)
    if match:
        return match.group(1).lower(), match.group(2).strip()
    return None


JEV_ROUTE_TIMEOUT_SECONDS = 20  # per-script timeout for route


def extract_prompt(event: dict) -> str:
    """Extract the raw user prompt text.

    Defensive multi-field lookup: this repo's own UserPromptSubmit hooks
    disagree with each other on the field name (``prompt`` top-level in most,
    ``tool_input.prompt`` in codex-auto-review.py, ``userMessage`` in
    pipeline-context-detector.py) -- rather than picking one and silently
    breaking on a schema this hook wasn't tested against, check all three in
    priority order. Top-level ``prompt`` first: majority convention among the
    actively-maintained hooks in this repo.
    """
    if not isinstance(event, dict):
        return ""
    for key in ("prompt", "message", "userMessage"):
        value = event.get(key)
        if isinstance(value, str) and value:
            return value
    tool_input = event.get("tool_input")
    if isinstance(tool_input, dict):
        value = tool_input.get("prompt")
        if isinstance(value, str):
            return value
    return ""


def extract_request_text(prompt: str) -> str | None:
    """Return router arguments, or None for a nonrouter prompt."""
    invocation = extract_router(prompt)
    return invocation[1] if invocation else None


def run_jev_route(request_text: str, session_id: str = "", cwd: str = "") -> dict | None:
    """Run jev-route.py directly (list-argv subprocess -- no shell, so no
    quoting risk from ``request_text``).

    Returns a parsed JEV_RESULT or None on classification failure. The
    separately persisted mandatory validation obligation remains pending.

    ``session_id`` reaches the call log through ``JEV_SESSION_ID``, so spend can
    be read per session. ``cwd`` is the repository the request is about; the
    router detects its languages and frameworks from marker files and sends
    them as state facts.
    """
    script = Path(__file__).resolve().parent.parent / "scripts" / "jev-route.py"
    if not script.is_file():
        return None
    try:
        proc = subprocess.run(
            [
                sys.executable,
                str(script),
                "--request",
                request_text,
                "--json-compact",
                *(["--cwd", cwd] if cwd else []),
            ],
            capture_output=True,
            text=True,
            timeout=JEV_ROUTE_TIMEOUT_SECONDS,
            check=False,
            env={**os.environ, "JEV_SESSION_ID": session_id} if session_id else None,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    try:
        result = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None
    return result if isinstance(result, dict) else None


def build_injection(jev_result: dict) -> str:
    """Build the additionalContext string from JEV_RESULT."""
    return (
        "[jev-route-injector] JEV_RESULT precomputed by this hook before your first token this "
        "turn -- do NOT run scripts/jev-route.py again for this request; skills/meta/d/SKILL.md "
        f"Phase 1 gates on this being present. JEV_RESULT = {json.dumps(jev_result)}"
    )


def main() -> None:
    raw = read_stdin(timeout=5)
    if not raw or not raw.strip():
        empty_output(EVENT_NAME).print_and_exit()
        return

    try:
        event = json.loads(raw)
    except json.JSONDecodeError:
        empty_output(EVENT_NAME).print_and_exit()
        return

    prompt = extract_prompt(event)
    if not prompt:
        empty_output(EVENT_NAME).print_and_exit()
        return

    session = event.get("session_id") or current_session_id()
    invocation = extract_router(prompt)
    continuation = False
    if invocation is None:
        marker = get_required_router(session) if session else None
        if marker and (marker.get("pending") or marker.get("status") in {"checked_blocked", "dispatch_ready"}):
            continue_required_router(session, prompt)
            invocation = (marker["router"], prompt)
            continuation = True
        else:
            if session:
                clear_required_router(session)
            empty_output(EVENT_NAME).print_and_exit()
            return
    if not isinstance(session, str) or not session:
        print(
            json.dumps(
                {"decision": "block", "reason": "Router requires a session ID to enforce mandatory intent checks."}
            )
        )
        return
    router, request_text = invocation
    # Persist before a subprocess can time out, crash, or return a fallback.
    if not continuation:
        set_required_router(session, router, prompt)
    mandatory = (
        f"[router-required] /{router}: ALL skill phases are mandatory. "
        "Before dispatch or a final answer, restate the requested outcome and constraints, "
        "then run scripts/build-dispatch.py with router, request_verbatim unchanged, "
        "and task_spec.intent. It runs the actual proposed-intent Jev check. "
        "Use --router-finalize for direct/trivial answers. A baseline classification is "
        "NOT intent validation. Fallback, timeout, trivial, and force routes cannot skip it. "
        f"Use JEV_SESSION_ID={shlex.quote(session)} for router commands."
    )
    if continuation:
        mandatory += (
            " This is a continuation of an unfinished router task. Preserve its original outcome; "
            "include every prior pending user request verbatim in task_spec.prior_context, "
            "and use this latest message unchanged as request_verbatim. Reclassify with that context; "
            "the prior route receipt does not cover this new turn."
        )
    cwd = event.get("cwd")
    result = (
        run_jev_route(request_text, session, cwd if isinstance(cwd, str) else "")
        if router == "d" and request_text and not continuation
        else None
    )
    if result is not None:
        mandatory += "\n" + build_injection(result)
    elif router == "d" and not continuation:
        mandatory += "\nClassification unavailable: run /do routing; the intent obligation remains pending."
    context_output(EVENT_NAME, mandatory).print_and_exit()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        hook_error("jev-route-injector-userprompt", exc)
        print(
            json.dumps(
                {
                    "decision": "block",
                    "reason": "Mandatory router state could not be recorded; repair the hook before continuing.",
                }
            )
        )
    finally:
        sys.exit(0)
