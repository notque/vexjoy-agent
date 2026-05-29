#!/usr/bin/env python3
"""Detect the running harness from environment variables (env proxy).

Emits JSON: {"harness": "claude-code|codex|gemini|factory|reasonix|unknown",
             "workflow_capable": bool}

Anthropic's native ``Workflow`` tool (deterministic JS orchestration) is
Claude Code-only. Codex, Gemini, Factory, and Reasonix do not have it; the
toolkit's prose pipelines run everywhere. ``workflow_capable`` is the
env-derived proxy ``harness == "claude-code"``.

PROXY, NOT AUTHORITY. A subprocess cannot introspect the session's tool list,
only the environment. So this script answers "which harness am I in?" and the
orchestrator LLM adds the authoritative gate: "is the `Workflow` tool actually
in my tool list?". Both must be true to take the native path. See
adr/harness-conditional-workflow-dispatch.md (R1).

Detection markers (distinctive entrypoint/session/home vars — never generic
API-key vars like GEMINI_API_KEY, which are commonly set under any harness):
  claude-code : CLAUDECODE, CLAUDE_CODE_ENTRYPOINT, CLAUDE_CODE_SESSION_ID
  codex       : CODEX_HOME, CODEX_HOOKS_DIR
  gemini      : GEMINI_CLI
  factory     : FACTORY_SESSION_ID, FACTORY_HOME, DROID_SESSION_ID, DROID_HOME
  reasonix    : (no env marker) — keyed off the ``_`` invocation var, since
                reasonix sets no session/home var and spawns hooks with the
                ambient env inherited (src/hooks.ts:206-212).
Mirrors hooks/lib/hook_utils.py:detect_cli(), extended with factory + the
Claude Code session markers.

Pure stdlib. Exit 0 always. Never raises.

Usage:
    python3 scripts/detect-workflow-capability.py            # JSON to stdout
    python3 scripts/detect-workflow-capability.py --harness  # bare harness id
"""

from __future__ import annotations

import json
import os
import sys

HARNESSES = ("claude-code", "codex", "gemini", "factory", "reasonix", "unknown")

# Marker var -> harness. Claude Code is checked first so it wins when env from
# a Claude Code session leaks other harnesses' vars (config copied around).
_MARKERS: list[tuple[str, tuple[str, ...]]] = [
    ("claude-code", ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT", "CLAUDE_CODE_SESSION_ID")),
    ("codex", ("CODEX_HOME", "CODEX_HOOKS_DIR")),
    ("gemini", ("GEMINI_CLI",)),
    ("factory", ("FACTORY_SESSION_ID", "FACTORY_HOME", "DROID_SESSION_ID", "DROID_HOME")),
]


def detect_harness(env: dict | None) -> str:
    """Return the harness id implied by ``env``. Never raises.

    A marker counts as present when its value is truthy (set and non-empty).
    Returns "unknown" when no distinctive marker is present.
    """
    try:
        if not env:
            return "unknown"
        for harness, keys in _MARKERS:
            for key in keys:
                if env.get(key):
                    return harness
        # Reasonix exposes no distinctive env marker. Fall back to the ``_``
        # invocation var (path of the invoking binary), the same best-effort
        # mechanism used for gemini/codex in detect_cli().
        if "reasonix" in env.get("_", "").lower():
            return "reasonix"
    except Exception:
        return "unknown"
    return "unknown"


def workflow_capable(harness: str) -> bool:
    """Env-derived proxy for native Workflow availability."""
    return harness == "claude-code"


def main(argv: list[str]) -> int:
    harness = detect_harness(dict(os.environ))
    if "--harness" in argv:
        print(harness)
        return 0
    print(json.dumps({"harness": harness, "workflow_capable": workflow_capable(harness)}))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception:
        # Exit-0 contract: a detection signal never blocks the orchestrator.
        print(json.dumps({"harness": "unknown", "workflow_capable": False}))
        sys.exit(0)
