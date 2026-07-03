#!/usr/bin/env python3
"""Deterministic /do Phase 4 dispatch-preamble builder (ADR: router-improvement-program, C4).

Takes one routing decision as JSON and prints the complete dispatch-prompt
preamble the router prepends to the agent prompt. Hand-assembly of these
blocks dropped mandatory injections; this script is the single source of
truth for every one of them ("LLMs orchestrate, programs execute"):

  1. `[do-route]` marker line — full grammar: agent/skill/complexity/model,
     health gate inputs (`health= n= fail= action=` or `health=-`),
     optional `alts={...}`, optional `stack={...}`. model= is required for
     medium/complex (errors on omission); trivial/simple get `model=-`.
     Emitted in the exact shape hooks/routing-decision-recorder.py parses.
  2. Thinking directive by complexity, with slow/fast category overrides.
  3. Token-budget line (input value, else `orchestration.token_budget`
     from .claude/settings.json, default 500000).
  4. Task Specification block from the provided fields.
  5. The four MANDATORY verbatim injections: reference loading,
     completeness, Dense-Complete Writing, base instructions.
  6. Optional worktree rules and LOCAL-ONLY block, on flags.

Input schema (missing optional fields degrade gracefully — block omitted):

    {
      "agent": "python-general-engineer",          // required
      "skill": "test-driven-development",          // optional; empty => skill=-
      "complexity": "medium",                      // required enum, case-insensitive:
                                                   // trivial|simple|medium|complex
      "model": "opus",                             // required for medium/complex;
                                                   // optional for trivial/simple
                                                   // (sonnet|opus|fable|gpt-5.5|codex)
      "health": {"confidence": 0.72, "n": 6,       // optional; absent/blank
                 "failure": 0, "action": "keep",   // confidence => health=-
                 "alts": ["a:b", "c:d"]},
      "stack": ["s1", "s2"],                       // optional
      "task_spec": {"intent": "...", "constraints": "...", "acceptance": "...",
                    "files": "...", "operator_context": "..."},
      "flags": {"worktree": false, "local_only": false,
                "thinking_override": "slow"|"fast"|null},
      "token_remaining": 480000                    // optional
    }

Usage:
    python3 scripts/build-dispatch.py --json '<routing decision JSON>'
    python3 scripts/build-dispatch.py --json-file /tmp/route.json   # "-" = stdin

Exit codes:
    0 — preamble printed to stdout
    2 — invalid input (message on stderr, nothing on stdout)

Stdlib only. Deterministic: same input, same output, byte for byte.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SETTINGS_PATH = REPO_ROOT / ".claude" / "settings.json"
DEFAULT_TOKEN_BUDGET = 500000

# ---------------------------------------------------------------------------
# Verbatim injection texts — the ONE place they live. skills/meta/do/SKILL.md
# Phase 4 Step 2 points here instead of quoting them. Changing a word here
# changes every dispatched prompt; keep in lockstep with the files each cites.
# ---------------------------------------------------------------------------

INJ_REFERENCE_LOADING = (
    "Before starting work, read your agent .md file to find the Reference Loading Table. "
    "Load EVERY reference file whose signal matches this task. "
    "Load greedily — if multiple signals match, load all matching references."
)

INJ_COMPLETENESS = "Deliver the finished product. Ship the complete thing."

INJ_DENSE_COMPLETE = (
    "Write to the Dense-Complete Writing standard — your structural guide for everything you do. "
    "It governs your output, code comments, any skill or reference files you write, "
    "AND every one of your thinking turns: "
    "(1) shortest accurate word; "
    "(2) cut every word that carries no instruction, rule, or decision; "
    "(3) plain English, not jargon; "
    "(4) concrete over abstract; "
    "(5) heavy qualifications in separate short sentences; "
    "(6) Completeness: treat content as fixed and wording as negotiable: "
    "carry every required point through the draft, then choose the shortest plain words "
    "that say those points exactly. "
    "Say everything the task needs and not one word more. Report what changed, not how. "
    "Full rules: `skills/shared-patterns/dense-complete-writing.md`."
)

INJ_BASE_INSTRUCTIONS = "Before starting work, also load `agents/base-instructions.md` for universal operational rules."

THINKING_FAST = "Prioritize responding quickly rather than thinking deeply. When in doubt, respond directly."

THINKING_SLOW = "Think carefully and step-by-step before responding; this problem is harder than it looks."

WORKTREE_RULES = (
    "Worktree rules: Verify CWD contains .claude/worktrees/. Create feature branch before edits. "
    "Skip task_plan.md. Stage specific files only."
)

# Injection template from skills/shared-patterns/local-only.md.
LOCAL_ONLY_BLOCK = (
    "**LOCAL-ONLY MODE.** Do not push, commit, create PRs, or deploy. "
    "All work stays on disk. Read-only git is fine. The user will decide when to commit."
)

# ---------------------------------------------------------------------------
# Marker grammar. Charsets mirror hooks/routing-decision-recorder.py exactly,
# so every emitted marker is parseable by the real recorder — the round-trip
# tests (scripts/tests/test_build_dispatch.py) assert it against that parser.
# ---------------------------------------------------------------------------

VALID_COMPLEXITY = ("trivial", "simple", "medium", "complex")
VALID_MODELS = ("sonnet", "opus", "fable", "gpt-5.5", "codex")
# Complexities that REQUIRE an explicit model pick (omission inherits the
# session main-loop model — a silent cost leak when an expensive model
# orchestrates). Trivial/simple may omit (inheritance risk is acceptable).
_MODEL_REQUIRED_COMPLEXITY = frozenset({"medium", "complex"})
VALID_ACTIONS = ("keep", "demote", "tiebreak")

_AGENT_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_SKILL_RE = re.compile(r"^[a-z0-9-]+$")
_KEY_RE = re.compile(r"^[a-z0-9:_-]+$")  # alts= / stack= items (comma is the separator)

# Complexity -> thinking directive. Trivial never dispatches; medium is
# adaptive (no directive). Overrides: "slow" => THINKING_SLOW, "fast" =>
# THINKING_FAST, regardless of complexity.
_THINKING_BY_COMPLEXITY = {"simple": THINKING_FAST, "complex": THINKING_SLOW}

# task_spec input key -> Task Specification block label, in emit order.
_TASK_SPEC_FIELDS = (
    ("intent", "Intent"),
    ("constraints", "Constraints"),
    ("acceptance", "Acceptance criteria"),
    ("files", "Relevant file locations"),
    ("operator_context", "Operator context"),
)


class InputError(ValueError):
    """Invalid routing decision — message tells the caller what to fix."""


def _fmt_confidence(value: float) -> str:
    """Canonical health= float: 0.72 -> '0.72', 0.5 -> '0.5', 1.0 -> '1'.

    Must match the recorder's `\\d+(\\.\\d+)?` — never scientific notation,
    never a sign, never a trailing dot.
    """
    if not 0 <= value <= 1:
        raise InputError(f"health.confidence must be within [0, 1], got {value}")
    text = f"{value:.4f}".rstrip("0").rstrip(".")
    return text or "0"


def _require_str(decision: dict, key: str) -> str:
    value = decision.get(key)
    if not isinstance(value, str) or not value.strip():
        raise InputError(f"'{key}' is required and must be a non-empty string")
    return value.strip()


def _key_list(raw: object, field: str) -> list[str]:
    """Validate an alts=/stack= item list; items carry no commas or spaces."""
    if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
        raise InputError(f"'{field}' must be a list of strings")
    items = [item.strip().lower() for item in raw if item.strip()]
    for item in items:
        if not _KEY_RE.match(item):
            raise InputError(f"'{field}' item {item!r} — allowed chars: a-z 0-9 : _ -")
    return items


def build_marker(decision: dict) -> str:
    """Build the `[do-route]` marker line from one routing decision."""
    agent = _require_str(decision, "agent").lower()
    if not _AGENT_RE.match(agent):
        raise InputError(f"'agent' {agent!r} — must match [a-z0-9][a-z0-9-]*")

    skill = str(decision.get("skill") or "").strip().lower()
    if skill and skill != "-" and not _SKILL_RE.match(skill):
        raise InputError(f"'skill' {skill!r} — must match [a-z0-9-]+")
    skill = skill or "-"

    complexity = _require_str(decision, "complexity").lower()
    if complexity not in VALID_COMPLEXITY:
        raise InputError(f"'complexity' {complexity!r} — must be one of {'/'.join(VALID_COMPLEXITY)}")

    parts = [f"[do-route] agent={agent}", f"skill={skill}", f"complexity={complexity}"]

    # Model enforcement: required for medium/complex, optional for trivial/simple.
    model = decision.get("model")
    if model is not None:
        model = str(model).strip().lower()
        if model and model != "-":
            # gpt-5.5 contains a dot — allow it through the charset check.
            if model not in VALID_MODELS:
                raise InputError(f"'model' {model!r} — must be one of {'/'.join(VALID_MODELS)}")
            parts.append(f"model={model}")
        else:
            model = None
    if model is None:
        if complexity in _MODEL_REQUIRED_COMPLEXITY:
            raise InputError(
                f"'model' is required for complexity={complexity} "
                f"(allowed: {'/'.join(VALID_MODELS)}). "
                f"Omitting model inherits the session main-loop model — "
                f"set it explicitly per the Model Selection table."
            )
        parts.append("model=-")

    health = decision.get("health") or {}
    if not isinstance(health, dict):
        raise InputError("'health' must be an object")
    confidence = health.get("confidence")
    if confidence is None:
        # No weight row for the pick — the recorder writes null but marks the
        # gate inputs present (instrumented, state b).
        parts.append("health=-")
    else:
        if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
            raise InputError("'health.confidence' must be a number or null")
        parts.append(f"health={_fmt_confidence(float(confidence))}")
        for key, token in (("n", "n"), ("failure", "fail")):
            value = health.get(key)
            if value is None:
                continue
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise InputError(f"'health.{key}' must be a non-negative integer")
            parts.append(f"{token}={value}")
        action = health.get("action")
        if action is not None:
            if str(action).lower() not in VALID_ACTIONS:
                raise InputError(f"'health.action' {action!r} — must be one of {'/'.join(VALID_ACTIONS)}")
            parts.append(f"action={str(action).lower()}")
        alts = _key_list(health.get("alts") or [], "health.alts")
        if alts:
            parts.append(f"alts={','.join(alts)}")

    stack = _key_list(decision.get("stack") or [], "stack")
    if stack:
        parts.append(f"stack={{{','.join(stack)}}}")

    return " ".join(parts)


def build_thinking(decision: dict) -> str:
    """Thinking directive for the dispatch, or "" when adaptive/none."""
    override = (decision.get("flags") or {}).get("thinking_override")
    if override is not None:
        directive = {"slow": THINKING_SLOW, "fast": THINKING_FAST}.get(str(override).lower())
        if directive is None:
            raise InputError(f"'flags.thinking_override' {override!r} — must be 'slow', 'fast', or null")
        return directive
    complexity = str(decision.get("complexity") or "").lower()
    return _THINKING_BY_COMPLEXITY.get(complexity, "")


def read_token_budget(settings_path: Path = SETTINGS_PATH) -> int:
    """`orchestration.token_budget` from settings.json; 500000 on any miss."""
    try:
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        budget = settings.get("orchestration", {}).get("token_budget", DEFAULT_TOKEN_BUDGET)
        return int(budget)
    except Exception:
        return DEFAULT_TOKEN_BUDGET


def build_token_line(decision: dict, settings_path: Path = SETTINGS_PATH) -> str:
    remaining = decision.get("token_remaining")
    if remaining is None:
        remaining = read_token_budget(settings_path)
    if not isinstance(remaining, int) or isinstance(remaining, bool) or remaining < 0:
        raise InputError("'token_remaining' must be a non-negative integer")
    return f"~{remaining} tokens available for this task; prioritize accordingly."


def build_task_spec(decision: dict) -> str:
    """Task Specification block from provided fields, or "" when none given."""
    spec = decision.get("task_spec") or {}
    if not isinstance(spec, dict):
        raise InputError("'task_spec' must be an object")
    lines = []
    for key, label in _TASK_SPEC_FIELDS:
        value = spec.get(key)
        if value is None or not str(value).strip():
            continue
        lines.append(f"**{label}:** {str(value).strip()}")
    if not lines:
        return ""
    return "## Task Specification (auto-extracted)\n\n" + "\n".join(lines)


def build_preamble(decision: dict, settings_path: Path = SETTINGS_PATH) -> str:
    """Complete dispatch preamble, blocks in dispatch order, blank-line separated."""
    if not isinstance(decision, dict):
        raise InputError("routing decision must be a JSON object")
    flags = decision.get("flags") or {}
    if not isinstance(flags, dict):
        raise InputError("'flags' must be an object")

    blocks = [
        build_marker(decision),
        build_thinking(decision),
        build_token_line(decision, settings_path),
        build_task_spec(decision),
        INJ_REFERENCE_LOADING,
        INJ_COMPLETENESS,
        INJ_DENSE_COMPLETE,
        INJ_BASE_INSTRUCTIONS,
        WORKTREE_RULES if flags.get("worktree") else "",
        LOCAL_ONLY_BLOCK if flags.get("local_only") else "",
    ]
    return "\n\n".join(block for block in blocks if block) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the /do Phase 4 dispatch preamble from a routing decision.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--json", help="Routing decision as a JSON string")
    source.add_argument("--json-file", help="Path to a routing-decision JSON file ('-' = stdin)")
    args = parser.parse_args(argv)

    try:
        if args.json is not None:
            raw = args.json
        elif args.json_file == "-":
            raw = sys.stdin.read()
        else:
            raw = Path(args.json_file).read_text(encoding="utf-8")
        decision = json.loads(raw)
    except OSError as exc:
        print(f"build-dispatch: cannot read input: {exc}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as exc:
        print(f"build-dispatch: invalid JSON: {exc}", file=sys.stderr)
        return 2

    try:
        sys.stdout.write(build_preamble(decision))
    except InputError as exc:
        print(f"build-dispatch: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
