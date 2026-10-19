#!/usr/bin/env python3
# hook-version: 4.0.1
"""
UserPromptSubmit hook -- pre-run jev-route.py on a /d invocation and inject
JEV_RESULT before the model generates a single token.

A skill instruction to "run the route script first" depends on the model
choosing to comply. This hook runs the script before the model has a choice.

This hook detects a raw ``/d ...`` invocation at UserPromptSubmit (the
earliest hook point in the turn, before /d's own instructions are read),
runs ``scripts/jev-route.py`` itself, and injects the resulting JSON as
additionalContext. JEV_RESULT holds the deterministic part of the route: the
safety force route (pr-workflow, security) when pre-route.py matches one, the
Jev attachment evidence, and the project facts. The session model picks the
agent, skill, and pipeline itself in Phase 1 of skills/meta/d/SKILL.md.

Honest limit, not overclaimed: this is real, mechanical enforcement for a
detected, on-time /d invocation -- the guard and the Jev attachment call
happen outside the model's control, deterministically, before generation
starts. It is NOT 100%% immunity: an invocation shape the regex below does
not recognize, or a hook failure/timeout, silently falls through to Phase 1's
own prose-driven script call -- this hook fails open in every failure mode,
it never blocks the prompt. See docs/injected-context-contracts.md's
``[jev-route-injector]`` entry for the full contract.
"""

import sys  # vexjoy-pyguard

if sys.version_info < (3, 10):  # vexjoy-pyguard advisory
    import os

    if not os.environ.get("VEXJOY_PYGUARD_REEXEC"):
        os.environ["VEXJOY_PYGUARD_REEXEC"] = "1"
        for _d in [*os.environ.get("PATH", "").split(os.pathsep), "/opt/homebrew/bin", "/usr/local/bin", "/usr/bin"]:
            for _v in ("14", "13", "12", "11", "10"):
                _p = os.path.join(_d, "python3." + _v)
                if _d and "/shims" not in _d and os.access(_p, os.X_OK):
                    os.execv(_p, [_p, *sys.argv])
    sys.stderr.write(
        "[vexjoy] hook %s needs Python 3.10+, got %s (%s); run ./install.sh in vexjoy-agent from a terminal"
        " outside Claude Code (gated tool calls stay blocked until then)\n"
        % (__file__.rsplit("/", 1)[-1], sys.version.split()[0], sys.executable)
    )
    sys.exit(0)

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))

from hook_utils import context_output, empty_output, hook_error
from stdin_timeout import read_stdin

EVENT_NAME = "UserPromptSubmit"

# Matches a /d invocation at the start of the prompt: "/d", "/d <request>",
# "/d\n<request>". \b after "d" prevents matching "/do" or "/design" etc.
DETECT_PATTERN = re.compile(r"^\s*/d\b\s*", re.IGNORECASE)

# A Vercel attempt gets four seconds. Three attempts plus two maximum
# Retry-After delays (5s each) take at most 22s, leaving two seconds for Python
# startup, JSON work, and process teardown under the host's 26s hook timeout.
JEV_ROUTE_ATTEMPT_TIMEOUT_SECONDS = 4
JEV_ROUTE_TIMEOUT_SECONDS = 24


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
    """Return the request text after ``/d``, or None if not a /d invocation."""
    m = DETECT_PATTERN.match(prompt)
    if not m:
        return None
    return prompt[m.end() :].strip()


def run_jev_route(request_text: str, session_id: str = "", cwd: str = "") -> dict | None:
    """Run jev-route.py directly (list-argv subprocess -- no shell, so no
    quoting risk from ``request_text``, which travels in a temp file).

    Returns the parsed JEV_RESULT dict, or None on any failure -- every
    failure path here means "fail open," not "block."

    ``session_id`` reaches the call log through ``JEV_SESSION_ID``, so spend can
    be read per session. ``cwd`` is the repository the request is about; the
    router detects its languages and frameworks from marker files and sends
    them as state facts.
    """
    script = Path(__file__).resolve().parent.parent / "scripts" / "jev-route.py"
    if not script.is_file():
        return None
    # The prompt goes in a private temp file, not argv: argv is readable by every
    # local user in `ps`, and a prompt can hold a pasted secret or start with "-".
    tmp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as tmp:
            tmp.write(request_text)
            tmp_path = tmp.name
        proc = subprocess.run(
            [
                sys.executable,
                str(script),
                "--request-file",
                tmp_path,
                "--json-compact",
                "--timeout",
                str(JEV_ROUTE_ATTEMPT_TIMEOUT_SECONDS),
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
    finally:
        if tmp_path:
            try:
                Path(tmp_path).unlink(missing_ok=True)
            except OSError:
                pass
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
        "Phase 1 gates on this being present. It holds the safety force route, the attachment evidence, "
        "and the project facts. It does NOT pick the agent, skill, or pipeline: you pick them in Phase 1 "
        "with the /do rules, then run scripts/jev-route.py --finalize. Phase 2 still requires you to write "
        "PROPOSED_INTENT and run scripts/jev-intent-align.py on that text before any routing banner or "
        "dispatch. JEV_RESULT = "
        f"{json.dumps(jev_result)}"
    )


_BYPASS_ENV = "JEV_ROUTE_INJECTOR_USERPROMPT_BYPASS"


def main() -> None:
    if os.environ.get(_BYPASS_ENV) == "1":
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            print(
                "[jev-route-injector-userprompt] Bypassed via JEV_ROUTE_INJECTOR_USERPROMPT_BYPASS=1", file=sys.stderr
            )
        sys.exit(0)

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
        # Not a /d invocation, or /d with no request text to classify.
        empty_output(EVENT_NAME).print_and_exit()
        return

    session_id = event.get("session_id") if isinstance(event, dict) else ""
    cwd = event.get("cwd")
    jev_result = run_jev_route(
        request_text,
        session_id if isinstance(session_id, str) else "",
        cwd if isinstance(cwd, str) else "",
    )
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
