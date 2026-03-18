#!/usr/bin/env python3
"""
Integration tests for the complete learning system.

Tests the full workflow from error detection through learning to solution suggestion.
Uses the SQLite-based learning database.

Note: Tests use the real database at ~/.claude/learning/patterns.db
"""

import sys
import uuid
from pathlib import Path

# Add parent lib directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))


def test_end_to_end_learning():
    """Test complete learning workflow."""
    print("Testing end-to-end learning workflow...")

    from learning_db import (
        classify_error,
        init_db,
        lookup_solution,
        record_error,
    )

    # Initialize database
    init_db()

    # Use unique error message for this test run
    unique_id = str(uuid.uuid4())[:8]
    error_message = f"Found 3 matches of the string to replace test-{unique_id}"

    # Classify error
    error_type = classify_error(error_message)
    assert error_type == "multiple_matches", (
        f"Expected 'multiple_matches', got '{error_type}'"
    )

    # Record initial error (low confidence)
    result = record_error(
        error_message=error_message,
        solution="Use replace_all or provide unique context",
        success=False,
        project_path="/test/project",
    )
    assert result["is_new"] is True

    # Simulate learning (multiple successes)
    for _ in range(8):
        record_error(
            error_message=error_message,
            solution="Use replace_all or provide unique context",
            success=True,
            project_path="/test/project",
        )

    # Check confidence increased
    solution = lookup_solution(error_message)
    assert solution is not None, "Solution should not be None after recording"
    assert solution["confidence"] >= 0.7, (
        f"Expected confidence >= 0.7, got {solution['confidence']}"
    )

    print("  ✓ Pattern learned and reached high confidence")


def test_multiple_error_types():
    """Test learning multiple different error types."""
    print("Testing multiple error type learning...")

    from learning_db import classify_error, init_db

    init_db()

    error_scenarios = [
        ("No such file or directory: missing.txt", "missing_file"),
        ("Permission denied: /etc/shadow", "permissions"),
        ("Found 5 matches of the string to replace", "multiple_matches"),
        ("SyntaxError: unexpected token", "syntax_error"),
        ("ModuleNotFoundError: No module named 'foo'", "import_error"),
    ]

    for error_msg, expected_type in error_scenarios:
        # Classify
        error_type = classify_error(error_msg)
        assert error_type == expected_type, (
            f"Expected {expected_type}, got {error_type}"
        )

    print("  ✓ Multiple error types classified correctly")


def test_confidence_bounds():
    """Test confidence score bounds."""
    print("Testing confidence bounds...")

    from learning_db import (
        init_db,
        record_error,
        get_connection,
        generate_signature,
        classify_error,
    )

    init_db()

    # Use unique error message with a known error type pattern
    unique_id = str(uuid.uuid4())[:8]
    error_msg = f"Permission denied test-{unique_id}"  # matches "permissions" type

    # Helper to get pattern confidence
    def get_confidence(msg):
        error_type = classify_error(msg)
        sig = generate_signature(msg, error_type)
        with get_connection() as conn:
            row = conn.execute(
                "SELECT confidence FROM patterns WHERE signature = ?", (sig,)
            ).fetchone()
            return row["confidence"] if row else None

    # Start with failure
    record_error(
        error_msg, solution="Test solution", success=False, project_path="/test"
    )

    # Many failures should drive confidence down
    for _ in range(15):
        record_error(
            error_msg, solution="Test solution", success=False, project_path="/test"
        )

    confidence = get_confidence(error_msg)
    assert confidence is not None, "Should find pattern after recording"
    assert confidence >= 0.0, f"Confidence went below 0: {confidence}"

    # Many successes should drive confidence up but not above 1
    for _ in range(25):
        record_error(
            error_msg, solution="Test solution", success=True, project_path="/test"
        )

    confidence = get_confidence(error_msg)
    assert confidence <= 1.0, f"Confidence went above 1: {confidence}"
    assert confidence > 0.5, (
        f"Confidence should be high after many successes: {confidence}"
    )

    print("  ✓ Confidence bounds enforced correctly")


def test_database_stats():
    """Test database statistics."""
    print("Testing database statistics...")

    from learning_db import get_stats, init_db

    init_db()

    stats = get_stats()
    assert "patterns" in stats
    assert "sessions" in stats
    assert "total_patterns" in stats["patterns"]

    print(
        f"  Stats: {stats['patterns']['total_patterns']} patterns, "
        f"{stats['patterns'].get('high_confidence') or 0} high-confidence"
    )
    print("  ✓ Database statistics working correctly")


def main():
    """Run all integration tests."""
    print("╔═══════════════════════════════════════════════════════════╗")
    print("║       Learning System Integration Tests (SQLite)         ║")
    print("╚═══════════════════════════════════════════════════════════╝\n")

    test_end_to_end_learning()
    test_multiple_error_types()
    test_confidence_bounds()
    test_database_stats()

    print("\n" + "=" * 60)
    print("✅ All integration tests passed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
