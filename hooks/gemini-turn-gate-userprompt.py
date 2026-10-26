#!/usr/bin/env python3
# hook-version: 1.0.0
"""PreInvocation / UserPromptSubmit Hook: Gemini Turn Gate

Detects incoming user prompts, evaluates task complexity, initializes
session-level routing state, and injects a Turn-1 routing directive for
Gemini models before execution begins.
"""

from __future__ import annotations

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
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from hook_utils import context_output, empty_output, hook_error
from stdin_timeout import read_stdin

EVENT_NAME = "UserPromptSubmit"
_BYPASS_ENV = "GEMINI_TURN_GATE_BYPASS"

# Trivial / conversational phrases that do not require full routing ceremonies
CONTINUATION_PATTERN = re.compile(
    r"^\s*(?:yes|no|y|n|ok|okay|proceed|continue|approved|go ahead|looks good|lgtm|thanks|thank you)\b[.!]*\s*$",
    re.IGNORECASE,
)
TRIVIAL_COMMAND_PATTERN = re.compile(
    r"^\s*/(?:help|clear|exit|quit|compact)\b",
    re.IGNORECASE,
)

_SAFE_ID_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _state_dir() -> Path:
    env_dir = os.environ.get("VEXJOY_ROUTING_STATE_DIR")
    if env_dir:
        return Path(env_dir)
    return Path(tempfile.gettempdir()) / "vexjoy-routing-state"


def _state_path(session_id: str) -> Path:
    safe_id = _SAFE_ID_RE.sub("_", session_id.strip() or "default")[:80]
    return _state_dir() / f"routing-state-{safe_id}.json"


def extract_prompt_text(event: dict) -> str:
    """Extract raw user prompt text from diverse harness event shapes."""
    if not isinstance(event, dict):
        return ""
    for key in ("prompt", "message", "userMessage"):
        val = event.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    tool_input = event.get("tool_input")
    if isinstance(tool_input, dict):
        val = tool_input.get("prompt")
        if isinstance(val, str) and val.strip():
            return val.strip()
    return ""


def save_routing_state(session_id: str, state: dict) -> None:
    """Atomically record routing state for the active turn."""
    path = _state_path(session_id)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)
    except OSError:
        pass


def is_non_trivial_task(prompt: str) -> bool:
    """Classify if the prompt is an actionable engineering or analysis task."""
    if not prompt:
        return False
    if CONTINUATION_PATTERN.match(prompt):
        return False
    if TRIVIAL_COMMAND_PATTERN.match(prompt):
        return False
    # Explicit routing triggers or multi-word requests are non-trivial
    if prompt.startswith(("/do", "/d", "/plan", "/goal", "/teamwork")):
        return True
    # If the prompt contains action words, code references, or is >= 4 words
    words = prompt.split()
    if len(words) >= 4:
        return True
    return False


def main() -> None:
    if os.environ.get(_BYPASS_ENV) == "1":
        return

    raw = read_stdin()
    if not raw:
        empty_output(EVENT_NAME)
        return

    try:
        event = json.loads(raw)
    except json.JSONDecodeError as exc:
        hook_error(EVENT_NAME, f"invalid input JSON: {exc}")
        return

    session_id = str(event.get("session_id") or event.get("conversationId") or "default")
    prompt = extract_prompt_text(event)

    if not prompt:
        empty_output(EVENT_NAME)
        return

    non_trivial = is_non_trivial_task(prompt)
    state = {
        "session_id": session_id,
        "prompt": prompt[:200],
        "routed": not non_trivial,
        "non_trivial": non_trivial,
        "timestamp": time.time(),
    }
    save_routing_state(session_id, state)

    if non_trivial:
        directive = (
            "[VEXJOY ROUTING MANDATE] Non-trivial task detected. "
            "In Turn 1, output the 4-Phase Classification and ROUTING banner as visible user-facing text "
            "before calling execution tools. For all Simple+ tasks (Simple, Medium, Complex), dispatch a subagent "
            "via define_subagent (from agents/<name>.md if not already defined) and invoke_subagent. "
            "Only Trivial tasks (single user-named file typo/fix) may execute directly in the main thread. "
            "Do not defer routing to post-execution."
        )
        out = context_output(EVENT_NAME, directive)
        sys.stdout.write(out.to_json())
    else:
        empty_output(EVENT_NAME)


if __name__ == "__main__":
    main()
