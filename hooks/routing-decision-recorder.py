#!/usr/bin/env python3
# hook-version: 1.0.0
"""
PostToolUse Hook: Routing Decision Recorder (action A, formerly /do Phase 5)

Records the routing-decision row for every Agent dispatch so the routing
feedback loop (`learning-db.py route-health`) keeps receiving the rows it
needs. Replaces the hand-run `learning-db.py record routing ...` step that
lived in /do Phase 2 Step 4 + Phase 5 action A.

PostToolUse:Agent fires AFTER the subagent completes, so the event carries
both the dispatch metadata (tool_input.subagent_type / .prompt / .description)
and the subagent's tool_result. From these we:
  1. Reconstruct the routing key {agent}:{skill} (skill parsed from the
     dispatch prompt; agent-only "{agent}:" when the skill is undiscoverable —
     matching the key format Phase 5 used).
  2. Record topic="routing", category="effectiveness" with observable fields
     (tool_errors, request/description snippet).
  3. (C) Parse a `rightsizing:tier{N}` banner from the subagent output and
     record a separate rightsizing row, parse-only and silent when absent.
  4. Write a pending-outcome entry to a per-session file so the SubagentStop
     hook (routing-outcome-recorder.py) can recover the full key + the error
     verdict and apply boost/decay. PostToolUse:Agent fires before
     SubagentStop, so the decision row is committed before the outcome runs —
     the ordering dependency is honored structurally.

Idempotency: a per-session state file keyed by a dispatch signature stops the
same dispatch being recorded twice (e.g. on retries). The DB upsert on
(topic, key) is also idempotent.

Design Principles:
- SILENT (records to DB, no context injection)
- Non-blocking (always exits 0)
- Fast execution (<50ms target); lazy imports
"""

import hashlib
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from routing_outcome_state import append_pending_outcome, dispatch_seen, mark_dispatch_seen
from stdin_timeout import read_stdin

EVENT_NAME = "PostToolUse"

# Skill discovery from the dispatch prompt, in priority order.
_SKILL_PATTERNS = [
    re.compile(r"""Skill\(\s*["']([a-z0-9][a-z0-9-]*)["']""", re.IGNORECASE),
    re.compile(r"\bskill\s*[:=]\s*([a-z0-9][a-z0-9-]*)", re.IGNORECASE),
    re.compile(r"\b(?:load|use|run|invoke)\s+the\s+([a-z0-9][a-z0-9-]*)\s+skill\b", re.IGNORECASE),
]

# Right-sizing banner, e.g. "rightsizing: tier=2 files=8 packages=3 agents_dispatched=12"
_RIGHTSIZING_RE = re.compile(
    r"rightsizing:\s*tier=(\d+)\s+files=(\d+)\s+packages=(\d+)\s+agents_dispatched=(\d+)",
    re.IGNORECASE,
)


def extract_skill(prompt: str) -> str:
    """Return the first skill name discoverable in the dispatch prompt, else ''."""
    if not prompt:
        return ""
    for pat in _SKILL_PATTERNS:
        m = pat.search(prompt)
        if m:
            return m.group(1).lower()
    return ""


def build_routing_key(agent: str, skill: str) -> str:
    """Build the {agent}:{skill} key; agent-only "{agent}:" when skill unknown."""
    return f"{agent}:{skill}" if skill else f"{agent}:"


def dispatch_signature(agent: str, skill: str, description: str, prompt: str) -> str:
    """Stable signature for one dispatch, used for idempotency."""
    raw = f"{agent}|{skill}|{description}|{prompt[:200]}"
    return hashlib.md5(raw.encode("utf-8", errors="replace")).hexdigest()[:16]


def detect_errors(event: dict) -> bool:
    """Return True if the subagent's tool_result shows an error. Best-effort."""
    try:
        from error_learner import detect_error

        has_error, _ = detect_error(event)
        return bool(has_error)
    except Exception:
        # Fallback: direct error field on the result.
        try:
            from hook_utils import get_tool_result, is_tool_error

            return is_tool_error(get_tool_result(event))
        except Exception:
            return False


def record_rightsizing(output: str) -> None:
    """(C) Record a rightsizing row when the output carries the banner. Silent otherwise."""
    if not output or "rightsizing:" not in output.lower():
        return
    m = _RIGHTSIZING_RE.search(output)
    if not m:
        return
    tier, files, packages, agents = m.group(1), m.group(2), m.group(3), m.group(4)
    from learning_db_v2 import record_learning

    record_learning(
        topic="routing",
        key=f"rightsizing:tier{tier}",
        value=f"rightsizing: tier={tier} files={files} packages={packages} agents_dispatched={agents}",
        category="effectiveness",
        tags=["routing", "rightsizing"],
        source="hook:routing-decision-recorder",
    )


def main() -> None:
    try:
        raw = read_stdin(timeout=2)
        if not raw:
            return
        event = json.loads(raw)

        # matcher "Agent" in settings.json scopes this hook; guard defensively.
        tool_name = event.get("tool_name") or event.get("tool", "")
        if tool_name != "Agent":
            return

        tool_input = event.get("tool_input") or event.get("input") or {}
        agent = (tool_input.get("subagent_type") or "").strip()
        if not agent:
            return  # no agent => nothing to key on

        prompt = tool_input.get("prompt") or ""
        description = tool_input.get("description") or ""
        skill = extract_skill(prompt)
        key = build_routing_key(agent, skill)

        # Idempotency: skip if we've already recorded this exact dispatch.
        sig = dispatch_signature(agent, skill, description, prompt)
        session_id = event.get("session_id") or ""
        if dispatch_seen(session_id, sig):
            return

        has_errors = detect_errors(event)
        request_snippet = (description or prompt)[:200].replace("\n", " ").strip()

        from learning_db_v2 import record_learning

        record_learning(
            topic="routing",
            key=key,
            value=(
                f"routing-decision: agent={agent} skill={skill or '-'} "
                f"tool_errors={1 if has_errors else 0} user_rerouted=0 "
                f"request: {request_snippet}"
            ),
            category="effectiveness",
            tags=["routing", agent] + ([skill] if skill else []),
            source="hook:routing-decision-recorder",
            session_id=session_id or None,
        )

        # (C) right-sizing feedback, parse-only.
        from hook_utils import get_tool_output, get_tool_result

        output = get_tool_output(get_tool_result(event))
        if isinstance(output, str):
            record_rightsizing(output)

        # Bridge to the SubagentStop outcome hook (action B).
        append_pending_outcome(session_id, key, has_errors)
        mark_dispatch_seen(session_id, sig)

    except Exception as e:
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            import traceback

            print(f"[routing-decision-recorder] HOOK-ERROR: {type(e).__name__}: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
    finally:
        sys.exit(0)  # Never block


if __name__ == "__main__":
    main()
