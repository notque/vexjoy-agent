#!/usr/bin/env python3
# hook-version: 3.0.0
"""
UserPromptSubmit hook -- pre-run jev-route.py on a /do invocation and inject
JEV_RESULT before the model generates a single token.

Why this exists (2026-09-16): skills/meta/do/SKILL.md's Phase 1 prose said
"call jev-route.py first, no thinking" -- that is compliance by request, not
enforcement. It already failed once: the model skipped the script call
entirely on a meta-question and reasoned about routing itself instead. A
stronger sentence in the skill file does not fix a model-choice failure mode;
a mechanism that runs before the model has a choice does.

This hook detects a raw ``/do ...`` invocation at UserPromptSubmit (the
earliest hook point in the turn, before /do's own instructions are read),
runs ``scripts/jev-route.py`` itself, and injects the resulting JSON as
additionalContext. By the time the model's first token for this turn is
generated, JEV_RESULT already exists in context -- Phase 1 of
skills/meta/do/SKILL.md then reads it instead of running the script, for
the case this hook successfully detects and completes in time.

Honest limit, not overclaimed: this is real, mechanical enforcement for a
detected, on-time /do invocation -- the classification happens outside the
model's control, deterministically, before generation starts. It is NOT
100%% immunity: an invocation shape the regex below does not recognize, or a
hook failure/timeout, silently falls through to Phase 1's own prose-driven
script call (same behavior as before this hook existed) -- this hook fails
open in every failure mode, it never blocks the prompt. See
docs/injected-context-contracts.md's ``[jev-route-injector]`` entry for the
full contract, and skills/meta/do/SKILL.md Phase 1 for how the injected
result is consumed.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))

from hook_utils import context_output, empty_output, hook_error
from stdin_timeout import read_stdin

EVENT_NAME = "UserPromptSubmit"

# Matches a /do invocation at the start of the prompt: "/do", "/do <request>",
# "/do\n<request>". \b after "do" prevents matching "/docs" or "/download" etc.
DETECT_PATTERN = re.compile(r"^\s*/do\b\s*", re.IGNORECASE)

JEV_ROUTE_TIMEOUT_SECONDS = 20  # per-script timeout for route


def extract_prompt(event: dict) -> str:
    """Extract the raw user prompt text.

    Defensive multi-field lookup: this repo's own UserPromptSubmit hooks
    disagree with each other on the field name (``prompt`` top-level in most,
    ``tool_input.prompt`` in codex-auto-review.py, ``userMessage`` in
    pipeline-context-detector.py) -- rather than picking one and silently
    breaking on a schema this hook wasn't tested against, check all three in
    priority order. Top-level ``prompt`` first: majority convention among the
    actively-maintained hooks in this repo as of 2026-09-16.
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
    """Return the request text after ``/do``, or None if not a /do invocation."""
    m = DETECT_PATTERN.match(prompt)
    if not m:
        return None
    return prompt[m.end() :].strip()


def run_jev_route(request_text: str) -> dict | None:
    """Run jev-route.py directly (list-argv subprocess -- no shell, so no
    quoting risk from ``request_text``).

    Returns the parsed JEV_RESULT dict, or None on any failure -- every
    failure path here means "fail open," not "block."
    """
    script = Path(__file__).resolve().parent.parent / "scripts" / "jev-route.py"
    if not script.is_file():
        return None
    try:
        proc = subprocess.run(
            [sys.executable, str(script), "--request", request_text, "--json-compact"],
            capture_output=True,
            text=True,
            timeout=JEV_ROUTE_TIMEOUT_SECONDS,
            check=False,
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
        "turn -- do NOT run scripts/jev-route.py again for this request; skills/meta/do/SKILL.md "
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

    request_text = extract_request_text(prompt)
    if request_text is None or not request_text:
        # Not a /do invocation, or /do with no request text to classify.
        empty_output(EVENT_NAME).print_and_exit()
        return

    jev_result = run_jev_route(request_text)
    if jev_result is None:
        # Fail open: Phase 1's own prose-driven script call is the fallback,
        # unchanged from before this hook existed.
        empty_output(EVENT_NAME).print_and_exit()
        return

    context_output(EVENT_NAME, build_injection(jev_result)).print_and_exit()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        hook_error("jev-route-injector-userprompt", exc)
    finally:
        sys.exit(0)
