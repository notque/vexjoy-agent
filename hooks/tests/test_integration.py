#!/usr/bin/env python3
"""
Integration tests for the complete learning system (v2 unified database).

Tests the full workflow from error detection through learning to solution suggestion.
Uses the unified learning database at ~/.claude/learning/learning.db.
"""

import sys
import uuid
from pathlib import Path

# Add parent lib directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))


def test_end_to_end_learning():
    """Test complete learning workflow."""
    print("Testing end-to-end learning workflow...")

    from learning_db_v2 import (
        boost_confidence,
        classify_error,
        generate_signature,
        get_connection,
        init_db,
        record_learning,
    )

    # Initialize database
    init_db()

    # Use unique error message for this test run
    unique_id = str(uuid.uuid4())[:8]
    error_message = f"Found 3 matches of the string to replace test-{unique_id}"

    # Classify error
    error_type = classify_error(error_message)
    assert error_type == "multiple_matches", f"Expected 'multiple_matches', got '{error_type}'"

    # Record initial error (low confidence)
    signature = generate_signature(error_message, error_type)
    result = record_learning(
        topic=error_type,
        key=signature,
        value=f"{error_message} → Use replace_all or provide unique context",
        category="error",
        confidence=0.55,
        source="test",
        project_path="/test/project",
        error_signature=signature,
        error_type=error_type,
    )
    assert result["is_new"] is True

    # Simulate learning (multiple successes boost confidence)
    for _ in range(3):
        boost_confidence(error_type, signature, delta=0.12)

    # Check confidence increased above threshold
    with get_connection() as conn:
        row = conn.execute(
            "SELECT confidence FROM learnings WHERE error_signature = ?",
            (signature,),
        ).fetchone()
        assert row is not None, "Should find learning after recording"
        assert row["confidence"] >= 0.7, f"Expected confidence >= 0.7, got {row['confidence']}"

    print("  ✓ Pattern learned and reached high confidence")


def test_multiple_error_types():
    """Test learning multiple different error types."""
    print("Testing multiple error type learning...")

    from learning_db_v2 import classify_error, init_db

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
        assert error_type == expected_type, f"Expected {expected_type}, got {error_type}"

    print("  ✓ Multiple error types classified correctly")


def test_confidence_bounds():
    """Test confidence score bounds."""
    print("Testing confidence bounds...")

    from learning_db_v2 import (
        boost_confidence,
        decay_confidence,
        init_db,
        record_learning,
    )

    init_db()

    # Use unique error message
    unique_id = str(uuid.uuid4())[:8]
    topic = "test-bounds"
    key = f"bounds-test-{unique_id}"

    # Start with low confidence
    record_learning(
        topic=topic,
        key=key,
        value="Test solution for bounds checking",
        category="error",
        confidence=0.55,
        source="test",
    )

    # Many decays should drive confidence down but not below 0
    for _ in range(15):
        conf = decay_confidence(topic, key, delta=0.18)

    assert conf >= 0.0, f"Confidence went below 0: {conf}"

    # Many boosts should drive confidence up but not above 1
    for _ in range(25):
        conf = boost_confidence(topic, key, delta=0.12)

    assert conf <= 1.0, f"Confidence went above 1: {conf}"
    assert conf > 0.5, f"Confidence should be high after many successes: {conf}"

    print("  ✓ Confidence bounds enforced correctly")


def test_database_stats():
    """Test database statistics."""
    print("Testing database statistics...")

    from learning_db_v2 import get_stats, init_db

    init_db()

    stats = get_stats()
    assert "total_learnings" in stats
    assert "by_category" in stats
    assert "high_confidence" in stats

    print(
        f"  Stats: {stats['total_learnings']} learnings, "
        f"{stats.get('high_confidence', 0)} high-confidence"
    )
    print("  ✓ Database statistics working correctly")


def main():
    """Run all integration tests."""
    print("╔═══════════════════════════════════════════════════════════╗")
    print("║    Learning System Integration Tests (v2 unified DB)     ║")
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
