#!/usr/bin/env python3
"""Deterministic request classifier for /do routing.

Classifies requests by complexity, creation intent, interview-mode
signals, and parallel patterns. Returns JSON.

Usage:
    python3 scripts/do-classify.py --request "run go tests"
    python3 scripts/do-classify.py --request "build a new agent" --json-compact
"""

from __future__ import annotations

import argparse
import json
import re
import sys

# --- Trivial detection ---

_READ_VERBS = r"(?:read|show|cat|display|open|view|look\s+at|what'?s\s+in|check)"
FILE_PATH_RE = re.compile(
    rf"{_READ_VERBS}\s+[`\"']?([/~][\w./\-]+(?:\.\w+)?)[`\"']?",
    re.IGNORECASE,
)
BARE_PATH_RE = re.compile(r"^[`\"']?([/~][\w./\-]+\.\w+)[`\"']?\s*$")

# --- Creation detection ---

CREATION_VERBS = frozenset(
    {
        "create",
        "scaffold",
        "build",
        "add new",
        "new",
        "implement new",
        "generate",
        "initialize",
        "bootstrap",
    }
)
CREATION_TARGETS = frozenset(
    {
        "agent",
        "skill",
        "pipeline",
        "hook",
        "feature",
        "plugin",
        "workflow",
        "voice profile",
        "component",
        "service",
        "module",
    }
)
ANTI_CREATION = frozenset(
    {
        "debug",
        "review",
        "fix",
        "refactor",
        "explain",
        "audit",
    }
)

# --- Interview-mode detection ---

INTERVIEW_VERBS = frozenset(
    {
        "build",
        "design",
        "make",
        "figure out",
        "set up",
    }
)
# Concrete nouns that indicate the user knows what they want — suppress interview
CONCRETE_NOUNS = frozenset(
    {
        "tests",
        "test",
        "pr",
        "changes",
        "branch",
        "commit",
        "audit",
        "review",
        "vulnerabilities",
        "bug",
        "typo",
        "error",
        "failure",
        "failures",
        "endpoint",
        "api",
        "deploy",
        "migration",
        "database",
        "schema",
        "ci",
    }
)
CONCRETE_RE = re.compile(r"line\s+\d+|`\w+`|\.go\b|\.py\b|\.ts\b|\.js\b|\.md\b")
FILE_REF_RE = re.compile(r"[/\\]\w+\.\w+|`[^`]+`")

# --- Complexity escalation ---

ESCALATORS: dict[str, str] = {
    # Complex signals
    "system-wide": "Complex",
    "entire": "Complex",
    "security audit": "Complex",
    # Medium signals
    "architecture": "Medium",
    "migration": "Medium",
    "refactor": "Medium",
    "redesign": "Medium",
    "rewrite": "Medium",
    "migrate": "Medium",
    "comprehensive": "Medium",
    "across": "Medium",
}

# --- Parallel detection ---

NUMBERED_LIST_RE = re.compile(r"(?:^|\n)\s*\d+[.)]\s")


def classify(request: str) -> dict:
    """Classify a user request for /do routing."""
    req_lower = request.lower().strip()
    words = req_lower.split()
    word_count = len(words)

    result: dict = {
        "complexity": "Simple",
        "is_creation": False,
        "is_interview": False,
        "is_parallel": False,
        "parallel_type": None,
        "creation_verbs": [],
        "reasoning": "",
    }

    # --- Trivial: exact file path read ---
    if FILE_PATH_RE.search(req_lower) or BARE_PATH_RE.match(req_lower):
        action_words = {"read", "show", "cat", "display", "open", "view", "check"}
        if any(w in words[:3] for w in action_words) or BARE_PATH_RE.match(req_lower):
            result["complexity"] = "Trivial"
            result["reasoning"] = "user named exact file path to read"
            return result

    # --- Creation detection ---
    found_verbs = [v for v in CREATION_VERBS if v in req_lower]
    has_target = any(t in req_lower for t in CREATION_TARGETS)
    if found_verbs and has_target:
        if not any(w in words[:2] for w in ANTI_CREATION):
            result["is_creation"] = True
            result["creation_verbs"] = found_verbs

    # --- Interview mode ---
    # Only fires when: short + vague verb + no concrete target + not creation
    has_file_ref = bool(FILE_REF_RE.search(request))
    has_interview_verb = any(v in req_lower for v in INTERVIEW_VERBS)
    has_concrete = bool(CONCRETE_RE.search(request))
    has_concrete_noun = bool(set(words) & CONCRETE_NOUNS)
    if (
        word_count < 15
        and has_interview_verb
        and not has_file_ref
        and not has_concrete
        and not has_concrete_noun
        and not result["is_creation"]
    ):
        result["is_interview"] = True

    # --- Parallel detection ---
    numbered_list = bool(NUMBERED_LIST_RE.search(request))
    has_semicolons = req_lower.count(";") >= 1
    has_sequence = "first" in words and ("then" in words or "after" in words)
    and_clauses = req_lower.count(" and ") >= 2

    if numbered_list or has_semicolons or and_clauses:
        result["is_parallel"] = True
        result["parallel_type"] = "independent-subtasks"
    elif has_sequence:
        result["is_parallel"] = True
        result["parallel_type"] = "sequential"

    # --- Complexity escalation ---
    for signal, level in ESCALATORS.items():
        if signal in req_lower:
            current = result["complexity"]
            rank = {"Simple": 0, "Medium": 1, "Complex": 2}
            if rank.get(level, 0) > rank.get(current, 0):
                result["complexity"] = level

    # Multiple file paths → Medium+
    if len(re.findall(r"[\w/]+\.\w+", request)) >= 3:
        if result["complexity"] == "Simple":
            result["complexity"] = "Medium"

    # Creation requests → at least Medium (new artifacts need planning)
    if result["is_creation"] and result["complexity"] == "Simple":
        result["complexity"] = "Medium"

    # Explicit file count mentions → Medium+
    file_count_match = re.search(r"(\d+)\s+files?", req_lower)
    if file_count_match and int(file_count_match.group(1)) >= 5:
        if result["complexity"] == "Simple":
            result["complexity"] = "Medium"

    # --- Reasoning ---
    parts = [f"complexity={result['complexity']}"]
    if result["is_creation"]:
        parts.append(f"creation({','.join(result['creation_verbs'])})")
    if result["is_interview"]:
        parts.append("interview-mode")
    if result["is_parallel"]:
        parts.append(f"parallel({result['parallel_type']})")
    result["reasoning"] = "; ".join(parts)

    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Classify request for /do routing")
    parser.add_argument("--request", required=True, help="User request text")
    parser.add_argument("--json-compact", action="store_true", help="Compact JSON output")
    args = parser.parse_args()

    result = classify(args.request)
    indent = None if args.json_compact else 2
    print(json.dumps(result, indent=indent))
    return 0


if __name__ == "__main__":
    sys.exit(main())
