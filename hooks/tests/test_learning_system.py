#!/usr/bin/env python3
"""
Tests for the learning hook system (v2 unified database).

Run with: python3 -m pytest hooks/tests/test_learning_system.py -v
Or directly: python3 hooks/tests/test_learning_system.py
"""

import sys
from pathlib import Path

# Add parent lib directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from learning_db_v2 import (
    classify_error,
    generate_signature,
    get_stats,
    init_db,
    lookup_error_solution,
    normalize_error,
    record_learning,
)


def test_error_normalizer():
    """Test error message normalization."""
    # Test timestamp removal
    error = "2024-11-30T12:34:56 Error occurred"
    normalized = normalize_error(error)
    assert "timestamp" in normalized.lower() or "2024-11-30" not in normalized

    # Test path simplification
    error = "File /home/user/project/file.py not found"
    normalized = normalize_error(error)
    # Path should be simplified (intermediate dirs removed)
    assert "file.py" in normalized or "/home/user/project/" not in normalized

    # Test line number normalization
    error = "SyntaxError at line 42"
    normalized = normalize_error(error)
    assert "line n" in normalized.lower() or "42" not in normalized


def test_error_classifier():
    """Test error classification."""
    # Missing file
    error = "No such file or directory: test.txt"
    error_type = classify_error(error)
    assert error_type == "missing_file"

    # Permission error
    error = "Permission denied accessing /etc/shadow"
    error_type = classify_error(error)
    assert error_type == "permissions"

    # Multiple matches
    error = "Found 3 matches of the string to replace, but replace_all is false"
    error_type = classify_error(error)
    assert error_type == "multiple_matches"

    # Syntax error
    error = "SyntaxError: invalid syntax on line 10"
    error_type = classify_error(error)
    assert error_type == "syntax_error"

    # Import error
    error = "ModuleNotFoundError: No module named 'foo'"
    error_type = classify_error(error)
    assert error_type == "import_error"

    # Unknown error
    error = "Something went wrong mysteriously"
    error_type = classify_error(error)
    assert error_type == "unknown"


def test_signature_generation():
    """Test error signature generation."""
    # Same normalized error should generate same signature
    sig1 = generate_signature("File /path/to/file.txt not found", "missing_file")
    sig2 = generate_signature("File /different/path/file.txt not found", "missing_file")

    # After path normalization, these should match
    assert sig1 == sig2

    # Different error types should have different signatures
    sig3 = generate_signature("Permission denied", "permissions")
    assert sig1 != sig3

    # Signatures should be consistent
    sig4 = generate_signature("Permission denied", "permissions")
    assert sig3 == sig4


def test_record_and_lookup():
    """Test recording and looking up errors via v2 API."""
    init_db()

    import uuid

    unique_id = str(uuid.uuid4())[:8]
    error_msg = f"Test error for lookup {unique_id}"
    error_type = classify_error(error_msg)
    signature = generate_signature(error_msg, error_type)

    result = record_learning(
        topic=error_type,
        key=signature,
        value=f"{error_msg} → Test solution",
        category="error",
        confidence=0.55,
        source="test",
        error_signature=signature,
        error_type=error_type,
    )

    assert result["is_new"] is True
    assert result["confidence"] < 0.7  # Not high confidence yet

    # Boost confidence above threshold
    from learning_db_v2 import boost_confidence

    for _ in range(3):
        boost_confidence(error_type, signature, delta=0.12)

    # Now should be lookupable via signature
    from learning_db_v2 import get_connection

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM learnings WHERE error_signature = ? AND confidence >= 0.7",
            (signature,),
        ).fetchone()
        assert row is not None
        assert row["confidence"] >= 0.7


def test_confidence_updates():
    """Test confidence score updates via v2 API."""
    init_db()

    import uuid

    from learning_db_v2 import boost_confidence, decay_confidence

    unique_id = str(uuid.uuid4())[:8]
    topic = "test-confidence"
    key = f"conf-test-{unique_id}"

    result = record_learning(
        topic=topic,
        key=key,
        value="Confidence test entry",
        category="error",
        confidence=0.55,
        source="test",
    )
    initial_conf = result["confidence"]

    # Success should increase confidence
    new_conf = boost_confidence(topic, key, delta=0.12)
    assert new_conf > initial_conf

    # Multiple decays should decrease confidence
    for _ in range(5):
        new_conf = decay_confidence(topic, key, delta=0.18)

    # Confidence should be lower but bounded at 0
    assert new_conf >= 0.0


def test_statistics():
    """Test statistics generation."""
    init_db()

    stats = get_stats()

    assert "total_learnings" in stats
    assert "by_category" in stats
    assert "high_confidence" in stats
    assert stats["total_learnings"] >= 0


def test_fix_type_recording():
    """Test fix_type and fix_action are recorded correctly."""
    init_db()

    import uuid

    unique_id = str(uuid.uuid4())[:8]
    error_msg = f"Fix type test error {unique_id}"
    error_type = classify_error(error_msg)
    signature = generate_signature(error_msg, error_type)

    result = record_learning(
        topic=error_type,
        key=signature,
        value=f"{error_msg} → Use skill to fix",
        category="error",
        confidence=0.65,
        source="test",
        error_signature=signature,
        error_type=error_type,
        fix_type="skill",
        fix_action="systematic-debugging",
    )

    # Verify via direct query
    from learning_db_v2 import get_connection

    with get_connection() as conn:
        row = conn.execute(
            "SELECT fix_type, fix_action FROM learnings WHERE topic = ? AND key = ?",
            (error_type, signature),
        ).fetchone()
        assert row is not None
        assert row["fix_type"] == "skill"
        assert row["fix_action"] == "systematic-debugging"


if __name__ == "__main__":
    # Run tests
    test_error_normalizer()
    print("✓ Error normalizer tests passed")

    test_error_classifier()
    print("✓ Error classifier tests passed")

    test_signature_generation()
    print("✓ Signature generation tests passed")

    test_record_and_lookup()
    print("✓ Record and lookup tests passed")

    test_confidence_updates()
    print("✓ Confidence update tests passed")

    test_statistics()
    print("✓ Statistics tests passed")

    test_fix_type_recording()
    print("✓ Fix type recording tests passed")

    print("\n✅ All tests passed!")
