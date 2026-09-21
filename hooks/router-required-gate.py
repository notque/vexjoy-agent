#!/usr/bin/env python3
# hook-version: 1.0.0
"""Block native dispatch and completion until this turn's router checks ran.

Claude supports Agent/Task PreToolUse. Codex currently supports Stop but does
not expose native agent dispatch to PreToolUse; the builder enforces its own
handoffs on either host. Claude Stop also requires queued dispatches to be
consumed. Codex Stop can verify intent validation but cannot verify agent
invocation; its adapter explicitly tags this narrower host guarantee.
This is not a general shell-command sandbox.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))


def evaluate(event: dict) -> dict:
    event_name = event.get("hook_event_name", "PreToolUse")
    if event_name not in {"Stop", "PreToolUse"}:
        return {}
    if event_name == "PreToolUse" and event.get("tool_name") not in {"Agent", "Task"}:
        return {}
    try:
        from router_gate import complete_required_router, consume_dispatch, get_required_router, session_id

        session = event.get("session_id") or session_id()
        if not session:
            return {}
        marker = get_required_router(session)
        if marker is None:
            return {}
        if event_name == "Stop":
            status = marker.get("status")
            if status == "checked_blocked":
                return {}
            if marker.get("pending") is False and status in {"validated", "dispatched", "completed"}:
                if complete_required_router(session, marker["generation"]):
                    return {}
            if (
                event.get("_vexjoy_hook_host") == "codex"
                and marker.get("pending") is False
                and status == "dispatch_ready"
            ):
                # Codex does not expose native agent dispatch consumption.
                if complete_required_router(session, marker["generation"]):
                    return {}
        if event_name == "PreToolUse" and marker.get("status") == "dispatch_ready":
            tool_input = event.get("tool_input")
            prompt = tool_input.get("prompt", "") if isinstance(tool_input, dict) else ""
            if consume_dispatch(session, prompt):
                return {}
        reason = (
            "[router-required] Mandatory router checks are pending for this request. "
            "Run scripts/build-dispatch.py with router, unchanged request_verbatim, "
            "and the actual task_spec.intent; use --router-finalize for a direct answer. "
            "Complete all required skill phases. Classification or a baseline receipt "
            "does not satisfy the proposed-intent check."
        )
        if event_name == "Stop" and marker.get("status") == "dispatch_ready":
            reason = (
                "[router-required] Validated worker dispatches remain outstanding. "
                "Invoke every queued Agent/Task with its exact builder prompt before completing."
            )
    except Exception:
        reason = (
            "[router-required] Cannot verify mandatory router state. Repair the state before dispatch or completion."
        )
    if event_name == "Stop":
        return {"decision": "block", "reason": reason}
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }


def main() -> None:
    try:
        event = json.load(sys.stdin)
    except (ValueError, OSError):
        return
    if isinstance(event, dict):
        print(json.dumps(evaluate(event)))


if __name__ == "__main__":
    main()
