#!/usr/bin/env python3
"""Deterministic enhancement selector for /do routing.

Given request text, complexity, and selected agent+skill, returns
enhancements, thinking directives, anti-rationalization patterns,
and worker model selection. Returns JSON.

Usage:
    python3 scripts/do-enhance.py --request "review go code" --complexity Simple
    python3 scripts/do-enhance.py --request "security audit" --complexity Medium --json-compact
"""

from __future__ import annotations

import argparse
import json
import sys

# --- Enhancement signal mapping ---

_ENHANCEMENT_SIGNALS: dict[str, str] = {
    "comprehensive": "parallel-reviewers",
    "thorough": "parallel-reviewers",
    "full review": "parallel-reviewers",
    "with tests": "test-driven-development",
    "production ready": "verification-before-completion",
    "research needed": "research-coordinator-engineer",
    "investigate first": "research-coordinator-engineer",
    "investigate": "research-coordinator-engineer",
}

_LOCAL_SIGNALS = frozenset(
    {
        "local only",
        "no push",
        "keep it local",
        "don't commit",
        "stay local",
        "don't push",
    }
)

# --- Anti-rationalization patterns ---

_ANTI_RAT: dict[str, list[str]] = {
    "code": ["anti-rationalization-core", "verification-checklist"],
    "review": ["anti-rationalization-core", "anti-rationalization-review"],
    "security": ["anti-rationalization-core", "anti-rationalization-security"],
    "test": ["anti-rationalization-core", "anti-rationalization-testing"],
    "debug": ["anti-rationalization-core", "verification-checklist"],
}

_TASK_TYPE_WORDS: dict[str, frozenset[str]] = {
    "security": frozenset({"security", "vulnerability", "permissions", "injection"}),
    "review": frozenset({"review", "audit"}),
    "test": frozenset({"test", "testing", "coverage"}),
    "debug": frozenset({"debug", "investigate", "diagnose", "troubleshoot"}),
    "code": frozenset(
        {
            "fix",
            "implement",
            "add",
            "change",
            "modify",
            "update",
            "refactor",
            "build",
            "create",
        }
    ),
}

# --- Thinking directives ---

_THINKING_SLOW_SIGNALS = frozenset(
    {
        "security audit",
        "security review",
        "vulnerability",
        "schema migration",
        "architectural decision",
        "api design",
        "database design",
        "encryption",
    }
)

# These match on WORD BOUNDARIES (checked against split words, not substrings)
# to avoid "read" matching inside "ready", "list" inside "listen", etc.
_THINKING_FAST_WORDS = frozenset(
    {
        "lookup",
        "status",
        "rename",
    }
)

_THINKING_SLOW = "Think carefully and step-by-step before responding; this problem is harder than it looks."
_THINKING_FAST = "Prioritize responding quickly rather than thinking deeply. When in doubt, respond directly."

# --- Model dispatch ---

_EXTRACTION_VERBS = frozenset(
    {
        "list",
        "count",
        "extract",
        "inventory",
        "search",
        "check",
        "find",
        "grep",
    }
)
_ANALYSIS_VERBS = frozenset(
    {
        "review",
        "audit",
        "assess",
        "analyze",
        "debug",
        "investigate",
        "evaluate",
    }
)


def enhance(
    request: str,
    complexity: str,
    agent: str | None = None,
    skill: str | None = None,
) -> dict:
    """Select enhancements for a classified request."""
    req_lower = request.lower()
    words = set(req_lower.split())

    result: dict = {
        "enhancements": [],
        "anti_rationalization": [],
        "thinking_directive": None,
        "thinking_tag": None,
        "model_dispatch": "direct",
        "local_only": False,
        "worker_model": "sonnet",
    }

    # --- Enhancement signals ---
    for signal, enhancement in _ENHANCEMENT_SIGNALS.items():
        if signal in req_lower and enhancement not in result["enhancements"]:
            result["enhancements"].append(enhancement)

    # --- Local-only ---
    if any(s in req_lower for s in _LOCAL_SIGNALS):
        result["local_only"] = True

    # --- Anti-rationalization ---
    # Check task types in priority order (security first)
    for task_type in ("security", "review", "test", "debug", "code"):
        if words & _TASK_TYPE_WORDS[task_type]:
            result["anti_rationalization"] = _ANTI_RAT[task_type]
            break

    # --- Thinking directive ---
    is_slow = any(s in req_lower for s in _THINKING_SLOW_SIGNALS)
    is_fast = bool(words & _THINKING_FAST_WORDS)

    if is_slow:
        result["thinking_directive"] = _THINKING_SLOW
        result["thinking_tag"] = "thinking:slow"
    elif is_fast or complexity == "Simple":
        result["thinking_directive"] = _THINKING_FAST
        result["thinking_tag"] = "thinking:fast"
    elif complexity == "Complex":
        result["thinking_directive"] = _THINKING_SLOW
        result["thinking_tag"] = "thinking:slow"
    # Medium: no directive (adaptive)

    # --- Model dispatch (Complex with multiple data sources) ---
    if complexity == "Complex":
        if words & _EXTRACTION_VERBS:
            result["model_dispatch"] = "parallel-haiku"
        elif words & _ANALYSIS_VERBS:
            result["model_dispatch"] = "direct"

    # --- Worker model selection ---
    if complexity == "Complex" or is_slow:
        result["worker_model"] = "opus"
    else:
        result["worker_model"] = "sonnet"

    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Select enhancements for /do routing")
    parser.add_argument("--request", required=True, help="User request text")
    parser.add_argument("--complexity", required=True, help="Trivial|Simple|Medium|Complex")
    parser.add_argument("--agent", default=None, help="Selected agent name")
    parser.add_argument("--skill", default=None, help="Selected skill name")
    parser.add_argument("--json-compact", action="store_true", help="Compact JSON output")
    args = parser.parse_args()

    result = enhance(args.request, args.complexity, args.agent, args.skill)
    indent = None if args.json_compact else 2
    print(json.dumps(result, indent=indent))
    return 0


if __name__ == "__main__":
    sys.exit(main())
