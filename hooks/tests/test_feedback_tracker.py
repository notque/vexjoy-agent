#!/usr/bin/env python3
"""
Tests for the feedback_tracker module.

Tests the automatic feedback tracking for error learning.
"""

import json
import sys
import time
from pathlib import Path

# Add lib directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from feedback_tracker import (
    _STATE_FILE,
    STATE_EXPIRY_SECONDS,
    check_pending_feedback,
    clear_pending,
    has_pending,
    set_pending_feedback,
)


def test_set_pending_feedback():
    """Test setting pending feedback state."""
    clear_pending()  # Start clean

    set_pending_feedback(
        signature="test123",
        error_type="import_error",
        fix_action="install_module",
        original_error="ModuleNotFoundError: No module named 'requests'",
    )

    assert has_pending(), "Should have pending feedback after setting"
    print("✓ set_pending_feedback works")


def test_check_pending_feedback_success():
    """Test checking pending feedback when fix succeeded."""
    clear_pending()

    set_pending_feedback(
        signature="success_test",
        error_type="import_error",
        fix_action="install_module",
        original_error="ModuleNotFoundError: No module named 'requests'",
    )

    # No error = success
    result = check_pending_feedback(None)

    assert result is not None, "Should return result"
    assert result["signature"] == "success_test"
    assert result["success"] is True
    assert "install_module" in result["reason"]
    assert not has_pending(), "Should clear pending after check"
    print("✓ check_pending_feedback (success case) works")


def test_check_pending_feedback_failure_same_error():
    """Test checking pending feedback when same error persists."""
    clear_pending()

    original = "SyntaxError: invalid syntax on line 10"
    set_pending_feedback(
        signature="fail_test",
        error_type="syntax_error",
        fix_action="systematic-debugging",
        original_error=original,
    )

    # Same error = failure
    result = check_pending_feedback(original)

    assert result is not None, "Should return result"
    assert result["signature"] == "fail_test"
    assert result["success"] is False
    assert "persists" in result["reason"]
    print("✓ check_pending_feedback (same error failure) works")


def test_check_pending_feedback_failure_different_error():
    """Test checking pending feedback when different error occurs."""
    clear_pending()

    set_pending_feedback(
        signature="diff_test",
        error_type="import_error",
        fix_action="install_module",
        original_error="ModuleNotFoundError: No module named 'requests'",
    )

    # Different error = also counts as failure (conservative)
    result = check_pending_feedback("TypeError: cannot concatenate str and int")

    assert result is not None, "Should return result"
    assert result["success"] is False
    assert "Different error" in result["reason"]
    print("✓ check_pending_feedback (different error failure) works")


def test_check_pending_feedback_no_pending():
    """Test checking when no pending feedback exists."""
    clear_pending()

    result = check_pending_feedback(None)
    assert result is None, "Should return None when no pending"
    print("✓ check_pending_feedback (no pending) works")


def test_clear_pending():
    """Test clearing pending feedback state."""
    set_pending_feedback(
        signature="clear_test",
        error_type="test",
        fix_action="test",
        original_error="test error",
    )
    assert has_pending()

    clear_pending()
    assert not has_pending(), "Should not have pending after clear"
    print("✓ clear_pending works")


def test_has_pending():
    """Test has_pending check."""
    clear_pending()
    assert not has_pending(), "Should not have pending when cleared"

    set_pending_feedback(
        signature="has_test",
        error_type="test",
        fix_action="test",
        original_error="test",
    )
    assert has_pending(), "Should have pending after set"
    print("✓ has_pending works")


def test_state_expiry():
    """Test that state expires after timeout."""
    clear_pending()

    set_pending_feedback(
        signature="expiry_test",
        error_type="test",
        fix_action="test",
        original_error="test",
    )

    # Manually modify timestamp to simulate expiry
    if _STATE_FILE.exists():
        state = json.loads(_STATE_FILE.read_text())
        state["timestamp"] = time.time() - STATE_EXPIRY_SECONDS - 10
        _STATE_FILE.write_text(json.dumps(state))

    assert not has_pending(), "Should not have pending after expiry"
    print("✓ state expiry works")


def test_truncation():
    """Test that long error messages are truncated."""
    clear_pending()

    long_error = "X" * 500  # Longer than 200 char limit
    set_pending_feedback(
        signature="trunc_test",
        error_type="test",
        fix_action="test",
        original_error=long_error,
    )

    # Read state directly
    state = json.loads(_STATE_FILE.read_text())
    assert len(state["original_error"]) == 200, "Should truncate to 200 chars"
    print("✓ error truncation works")


def main():
    """Run all tests."""
    print("Testing feedback_tracker module...\n")

    test_set_pending_feedback()
    test_check_pending_feedback_success()
    test_check_pending_feedback_failure_same_error()
    test_check_pending_feedback_failure_different_error()
    test_check_pending_feedback_no_pending()
    test_clear_pending()
    test_has_pending()
    test_state_expiry()
    test_truncation()

    # Cleanup
    clear_pending()

    print("\n✅ All feedback_tracker tests passed!")


if __name__ == "__main__":
    main()
