#!/usr/bin/env python3
# hook-version: 1.0.0
"""
PostToolUse Hook: Routing Decision Recorder (action A, formerly /do Phase 5)

Records the routing-decision row for every Agent dispatch so the routing
feedback loop (`learning-db.py route-health`) keeps receiving the rows it
needs. Replaces the hand-run `learning-db.py record routing ...` step that
lived in /do Phase 2 Step 4 + Phase 5 action A.

SCOPING — record ONLY /do-routed dispatches.
Every Agent dispatch fires PostToolUse:Agent, including pr-review's reviewer
sub-agents (code-reviewer, security-reviewer, reviewer-*) and any other
nested fan-out. Recording all of them would inflate route-health's denominator
with dispatches /do never routed. So /do stamps a machine-readable marker on
the prompts IT routes (Phase 4 Step 2):

    [do-route] agent={agent} skill={skill} complexity={complexity}

This hook records ONLY when that marker is present, and reads the agent + skill
directly FROM the marker (structured intent emitted by the router — not fragile
prompt-sniffing). No marker → not a /do routing decision → skip. This is the
sole scoping mechanism (no reviewer-name denylist).

PostToolUse:Agent fires AFTER the subagent completes, so the event carries
both the dispatch metadata (tool_input.subagent_type / .prompt / .description)
and the subagent's tool_result. From these we:
  1. Read the routing key {agent}:{skill} from the [do-route] marker
     (agent-only "{agent}:" when the marker carries no skill).
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
from routing_outcome_state import append_pending_outcome, claim_dispatch
from stdin_timeout import read_stdin

EVENT_NAME = "PostToolUse"

# The /do routing marker. /do (SKILL.md Phase 4 Step 2) prepends this to every
# agent prompt IT routes. Its presence is the SOLE signal that a dispatch is a
# /do routing decision; agent + skill are read straight from it. Sub-agent
# fan-out (pr-review reviewers, nested dispatches) carries no marker → skipped.
#   [do-route] agent=python-general-engineer skill=test-driven-development complexity=Medium
# skill may be empty/"-"/absent (agent-only routing).
# Anchored to line start (^\s*, MULTILINE) so a quoted/forwarded marker
# mid-prose (e.g. a user pasting "...the [do-route] line...") doesn't get
# recorded — only a marker /do itself emitted at the head of a line counts.
_DO_ROUTE_RE = re.compile(
    r"^\s*\[do-route\]\s+agent=([a-z0-9][a-z0-9-]*)(?:\s+skill=([a-z0-9-]*|-)?)?",
    re.IGNORECASE | re.MULTILINE,
)

# Optional complexity field on the same marker line, recorded into the T3 event
# log for replay. Absent => "".
_COMPLEXITY_RE = re.compile(r"\bcomplexity=([a-z0-9-]+)", re.IGNORECASE)

# Right-sizing banner, e.g. "rightsizing: tier=2 files=8 packages=3 agents_dispatched=12"
_RIGHTSIZING_RE = re.compile(
    r"rightsizing:\s*tier=(\d+)\s+files=(\d+)\s+packages=(\d+)\s+agents_dispatched=(\d+)",
    re.IGNORECASE,
)


def parse_do_route_marker(prompt: str) -> tuple[str, str] | None:
    """Read (agent, skill) from the [do-route] marker, or None when absent.

    None means this dispatch was not routed by /do (no marker) → the caller
    skips recording. skill is "" when the marker carries no skill or "-".
    """
    if not prompt or "[do-route]" not in prompt.lower():
        return None
    m = _DO_ROUTE_RE.search(prompt)
    if not m:
        return None
    agent = m.group(1).strip().lower()
    skill = (m.group(2) or "").strip().lower()
    if skill == "-":
        skill = ""
    return agent, skill


def build_routing_key(agent: str, skill: str) -> str:
    """Build the {agent}:{skill} key; agent-only "{agent}:" when skill unknown."""
    return f"{agent}:{skill}" if skill else f"{agent}:"


def dispatch_signature(agent: str, skill: str, description: str, prompt: str) -> str:
    """Stable signature for one dispatch, used for idempotency."""
    raw = f"{agent}|{skill}|{description}|{prompt[:200]}"
    return hashlib.md5(raw.encode("utf-8", errors="replace")).hexdigest()[:16]


def detect_errors(event: dict) -> bool:
    """Return True if the subagent's tool_result shows an error. Best-effort.

    Uses hook_utils.is_tool_error as the intended detector. (The earlier
    `from error_learner import detect_error` branch was dead code: the module
    file is hooks/error-learner.py — hyphenated, so the import always raised
    ImportError and silently fell through to is_tool_error. Removed to make the
    real detector explicit.)
    """
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
        prompt = tool_input.get("prompt") or ""
        description = tool_input.get("description") or ""

        # SCOPING: record ONLY /do-routed dispatches. No [do-route] marker =>
        # this is a sub-agent fan-out (pr-review reviewers, nested dispatch),
        # not a /do routing decision — skip so route-health's denominator stays
        # clean. agent + skill are read straight from the marker.
        routed = parse_do_route_marker(prompt)
        if routed is None:
            return
        agent, skill = routed
        if not agent:
            return  # malformed marker => nothing to key on
        key = build_routing_key(agent, skill)

        # Idempotency (atomic, MEDIUM/TOCTOU): claim this dispatch signature.
        # claim_dispatch performs check-and-set under one flock, so N concurrent
        # duplicate deliveries record exactly once. False => already claimed.
        sig = dispatch_signature(agent, skill, description, prompt)
        session_id = event.get("session_id") or ""
        if not claim_dispatch(session_id, sig):
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

        # T3: per-dispatch DECISION event (JSONL), append-only + failure-safe.
        # Auxiliary to the aggregate row above — never blocks; route_events
        # swallows write errors so the hook stays non-blocking.
        cm = _COMPLEXITY_RE.search(prompt)
        complexity = cm.group(1) if cm else ""
        from route_events import record_decision_event

        record_decision_event(
            session=session_id,
            request_snippet=request_snippet,
            agent=agent,
            skill=skill,
            complexity=complexity,
            health_at_decision=None,  # populated by the gated Step-1.5 wiring (T6)
        )

        # (C) right-sizing feedback, parse-only.
        from hook_utils import get_tool_output, get_tool_result

        output = get_tool_output(get_tool_result(event))
        if isinstance(output, str):
            record_rightsizing(output)

        # Bridge to the SubagentStop outcome hook (action B). The dispatch was
        # already claimed (marked seen) atomically above, so no separate mark.
        # Decision row is written BEFORE this append (ordering: A-before-B).
        append_pending_outcome(session_id, key, has_errors)

    except Exception as e:
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            import traceback

            print(f"[routing-decision-recorder] HOOK-ERROR: {type(e).__name__}: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
    finally:
        sys.exit(0)  # Never block


if __name__ == "__main__":
    main()
