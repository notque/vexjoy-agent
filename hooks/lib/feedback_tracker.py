#!/usr/bin/env python3
"""
Automatic Feedback Tracking for Error Learning System.

Tracks pending feedback for error fixes and automatically records
success/failure based on subsequent tool results.

Design Principles:
- Stateful tracking across PostToolUse events via temp file
- Fast: <10ms overhead per event
- Self-cleaning: State expires after 60 seconds
- Non-blocking: Never interferes with tool execution
"""

import json
import os
import sys
import time
from pathlib import Path
from typing import Optional

# State file location - in user's .claude directory
_STATE_DIR = Path.home() / ".claude" / "learning"
_STATE_FILE = _STATE_DIR / "pending_feedback.json"

# State expires after 60 seconds (tool use should follow quickly)
STATE_EXPIRY_SECONDS = 60


def _ensure_dir():
    """Ensure state directory exists."""
    _STATE_DIR.mkdir(parents=True, exist_ok=True)


def _load_state() -> Optional[dict]:
    """Load pending feedback state, returning None if expired or missing."""
    try:
        if not _STATE_FILE.exists():
            return None

        state = json.loads(_STATE_FILE.read_text())

        # Check expiry
        if time.time() - state.get("timestamp", 0) > STATE_EXPIRY_SECONDS:
            clear_pending()
            return None

        return state
    except (json.JSONDecodeError, OSError):
        return None


def _save_state(state: dict) -> None:
    """Save pending feedback state."""
    try:
        _ensure_dir()
        state["timestamp"] = time.time()
        tmp = _STATE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, indent=2))
        tmp.rename(_STATE_FILE)
    except OSError as e:
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            print(f"[feedback-tracker] save error: {e}", file=sys.stderr)


def set_pending_feedback(signature: str, error_type: str, fix_action: str, original_error: str) -> None:
    """Set pending feedback for an applied fix.

    Called when error-learner emits a fix instruction.
    The next tool result will be compared to determine success/failure.

    Args:
        signature: Pattern signature from learning_db
        error_type: Classified error type
        fix_action: The fix action that was suggested
        original_error: First 200 chars of original error for comparison
    """
    state = {
        "signature": signature,
        "error_type": error_type,
        "fix_action": fix_action,
        "original_error": original_error[:200],
        "awaiting_result": True,
    }
    _save_state(state)


def check_pending_feedback(current_error: Optional[str]) -> Optional[dict]:
    """Check if there's pending feedback and determine outcome.

    Called on each PostToolUse to see if we're waiting for feedback.

    Args:
        current_error: Current error message (None if no error)

    Returns:
        Dict with feedback result, or None if no pending feedback:
        {
            "signature": str,
            "success": bool,
            "reason": str
        }
    """
    state = _load_state()
    if not state or not state.get("awaiting_result"):
        return None

    # Clear state - we're processing it now
    clear_pending()

    # Determine success/failure
    if current_error is None:
        # No error = fix worked
        return {
            "signature": state["signature"],
            "success": True,
            "reason": f"No error after applying {state['fix_action']}",
        }

    # Check if error is different (might indicate partial success or new issue)
    original = state.get("original_error", "")
    if current_error[:200] != original:
        # Different error - could be progress or new issue
        # Conservative: count as failure since original issue may not be fixed
        return {
            "signature": state["signature"],
            "success": False,
            "reason": f"Different error after {state['fix_action']}: {current_error[:100]}",
        }

    # Same error persists = fix didn't work
    return {
        "signature": state["signature"],
        "success": False,
        "reason": f"Same error persists after {state['fix_action']}",
    }


def clear_pending() -> None:
    """Clear any pending feedback state."""
    try:
        _STATE_FILE.unlink(missing_ok=True)
    except OSError:
        pass


def has_pending() -> bool:
    """Check if there's pending feedback awaiting result."""
    state = _load_state()
    return state is not None and state.get("awaiting_result", False)


if __name__ == "__main__":
    # Quick test
    print("Testing feedback tracker...")

    # Test set pending
    set_pending_feedback(
        signature="abc123",
        error_type="import_error",
        fix_action="install_module",
        original_error="ModuleNotFoundError: No module named 'requests'",
    )
    print(f"Has pending: {has_pending()}")

    # Test success case
    result = check_pending_feedback(None)
    print(f"Success result: {result}")

    # Test failure case
    set_pending_feedback(
        signature="def456",
        error_type="syntax_error",
        fix_action="systematic-debugging",
        original_error="SyntaxError: invalid syntax",
    )
    result = check_pending_feedback("SyntaxError: invalid syntax line 10")
    print(f"Failure result: {result}")

    print("Tests complete.")
