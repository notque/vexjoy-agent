#!/usr/bin/env python3
# hook-version: 1.0.0
"""
PostToolUse Hook: Error Learning System with Automatic Feedback

Detects errors from tool executions and learns from patterns.
Uses SQLite database for persistent cross-session learning.
AUTOMATICALLY tracks fix outcomes for reinforcement learning.

Design Principles:
- SILENT when no errors detected (no noise)
- Non-blocking (always exits 0)
- Fast execution (<50ms target)
- SQLite for robust storage
- AUTOMATIC feedback loop (no manual intervention)
"""

import json
import os
import sys
from pathlib import Path

# Add lib directory to path for imports
sys.path.insert(0, str(Path(__file__).parent / "lib"))

from feedback_tracker import check_pending_feedback, set_pending_feedback
from learning_db_v2 import (
    DEFAULT_FIX_ACTIONS,
    boost_confidence,
    classify_error,
    decay_confidence,
    generate_signature,
    lookup_error_solution,
    record_learning,
)
from stdin_timeout import read_stdin


def process_automatic_feedback(current_error: str | None) -> None:
    """Process automatic feedback from previous fix suggestion.

    Uses learning_db_v2 boost/decay instead of direct SQL.
    """
    feedback = check_pending_feedback(current_error)
    if not feedback:
        return

    # The feedback tracker stores the error_type as topic and signature as key
    error_type = feedback.get("error_type", "unknown")
    signature = feedback["signature"]

    if feedback["success"]:
        new_confidence = boost_confidence(error_type, signature, 0.15)
        status = "✓"
    else:
        new_confidence = decay_confidence(error_type, signature, 0.1)
        status = "✗"

    if new_confidence > 0:
        print(f"[auto-feedback] {status} {feedback['reason']}")
        print(f"[auto-feedback] confidence → {new_confidence:.2f}")


def detect_error(event: dict) -> tuple[bool, str]:
    """Detect if tool execution had an error.

    Returns:
        Tuple of (has_error, error_message)
    """
    tool_result = event.get("tool_result", {})

    # Direct error field
    if "error" in tool_result:
        return True, str(tool_result["error"])

    # Check for error in output
    output = tool_result.get("output", "")
    if isinstance(output, str):
        output_lower = output.lower()

        # Error indicators that match our ERROR_TYPES patterns
        error_indicators = [
            "error",
            "failed",
            "permission denied",
            "access denied",
            "not found",
            "no such file",
            "cannot find",
            "does not exist",
            "syntax error",
            "unexpected token",
            "type error",
            "import error",
            "module not found",
            "no module named",
            "timeout",
            "timed out",
            "connection refused",
            "traceback",
            "exception",
        ]

        if any(indicator in output_lower for indicator in error_indicators):
            # Avoid false positives for success messages
            if "0 errors" not in output_lower and "no errors" not in output_lower:
                return True, output

    # Check for non-zero exit code mention in Bash tool
    tool_name = event.get("tool_name", "")
    if tool_name == "Bash" and isinstance(output, str):
        if "exit code" in output.lower() and "exit code 0" not in output.lower():
            return True, output

    return False, ""


def main():
    """Process PostToolUse events with automatic feedback loop.

    Flow:
    1. Check if previous fix suggestion worked (automatic feedback)
    2. Detect errors in current tool result
    3. Look up or record patterns
    4. Set pending feedback for next iteration
    """
    try:
        event_data = read_stdin(timeout=2)
        if not event_data:
            return

        event = json.loads(event_data)

        # Only process PostToolUse events
        event_type = event.get("hook_event_name") or event.get("type", "")
        if event_type != "PostToolUse":
            return

        # Check for errors in current result
        has_error, error_message = detect_error(event)

        # AUTOMATIC FEEDBACK: Check if previous fix worked
        # This happens on EVERY PostToolUse - if no pending feedback, it's a no-op
        process_automatic_feedback(error_message if has_error else None)

        # If no error now, we're done (feedback already processed above)
        if not has_error:
            return

        # Get context
        tool_name = event.get("tool_name", "unknown")
        agent_type = event.get("agent_type", "")
        cwd = event.get("cwd", str(Path.cwd()))

        # Build source_detail with agent attribution
        source_detail = f"{tool_name}:{agent_type}" if agent_type else tool_name

        # Classify and generate signature
        error_type = classify_error(error_message)
        signature = generate_signature(error_message, error_type)

        # Check for existing solution in unified DB
        existing = lookup_error_solution(error_message)
        if existing and existing.get("value"):
            fix_type = existing.get("fix_type", "manual")
            fix_action = existing.get("fix_action", "")
            solution = existing["value"]

            # Emit structured fix instruction based on type
            if fix_type == "auto" and fix_action:
                print(f"[auto-fix] type={fix_type} action={fix_action}")
                print(f"[auto-fix] solution: {solution}")
            elif fix_type == "skill" and fix_action:
                print(f"[fix-with-skill] {fix_action}")
                print(f"[fix-with-skill] reason: {solution}")
            elif fix_type == "agent" and fix_action:
                print(f"[fix-with-agent] {fix_action}")
                print(f"[fix-with-agent] reason: {solution}")
            else:
                print(f"[learned-solution] {solution}")

            set_pending_feedback(
                signature=signature,
                error_type=error_type,
                fix_action=fix_action or fix_type,
                original_error=error_message,
            )

            # Re-record to boost confidence
            record_learning(
                topic=error_type,
                key=signature,
                value=f"{error_message[:200]} → {solution}",
                category="error",
                source="hook:error-learner",
                source_detail=source_detail,
                project_path=cwd,
                error_signature=signature,
                error_type=error_type,
                fix_type=fix_type,
                fix_action=fix_action,
            )
        else:
            # New error — record with default fix action
            fix_info = DEFAULT_FIX_ACTIONS.get(error_type, {"fix_type": "manual", "fix_action": "investigate"})
            fix_type = fix_info["fix_type"]
            fix_action = fix_info["fix_action"]
            solution = f"Fix {error_type} error in {tool_name}"

            print(f"[new-error] {error_type}: {error_message[:100]}")
            if fix_type == "auto":
                print(f"[new-error] suggested action: {fix_action}")
            elif fix_type == "skill":
                print(f"[new-error] suggested skill: {fix_action}")
            else:
                print(f"[new-error] suggestion: {solution}")

            set_pending_feedback(
                signature=signature,
                error_type=error_type,
                fix_action=fix_action,
                original_error=error_message,
            )

            record_learning(
                topic=error_type,
                key=signature,
                value=f"{error_message[:200]} → {solution}",
                category="error",
                source="hook:error-learner",
                source_detail=source_detail,
                project_path=cwd,
                error_signature=signature,
                error_type=error_type,
                fix_type=fix_type,
                fix_action=fix_action,
            )

    except Exception as e:
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            import traceback

            print(f"[error-learner] HOOK-ERROR: {type(e).__name__}: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
    finally:
        sys.exit(0)  # Never block


if __name__ == "__main__":
    main()
