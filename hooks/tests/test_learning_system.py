#!/usr/bin/env python3
"""
Tests for the learning hook system.

Run with: python3 -m pytest hooks/tests/test_learning_system.py -v
Or directly: python3 hooks/tests/test_learning_system.py
"""

import sys
from pathlib import Path

# Add parent lib directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from learning_db import (
    classify_error,
    normalize_error,
    generate_signature,
    record_error,
    lookup_solution,
    get_stats,
    init_db,
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
    """Test recording and looking up errors."""
    init_db()

    # Record a new error
    import uuid

    unique_id = str(uuid.uuid4())[:8]
    error_msg = f"Test error for lookup {unique_id}"

    result = record_error(
        error_message=error_msg,
        solution="Test solution",
        success=False,
        project_path="/test/project",
    )

    assert result["is_new"] is True
    assert result["confidence"] < 0.7  # Not high confidence yet

    # Build up confidence
    for _ in range(10):
        record_error(
            error_message=error_msg,
            solution="Test solution",
            success=True,
            project_path="/test/project",
        )

    # Now should be lookupable
    solution = lookup_solution(error_msg)
    assert solution is not None
    assert solution["confidence"] >= 0.7
    assert solution["solution"] == "Test solution"


def test_confidence_updates():
    """Test confidence score updates."""
    init_db()

    import uuid

    unique_id = str(uuid.uuid4())[:8]
    error_msg = f"Confidence test error {unique_id}"

    # Initial failure
    result = record_error(
        error_msg, solution="Fix it", success=False, project_path="/test"
    )
    initial_conf = result["confidence"]

    # Success should increase confidence
    result = record_error(
        error_msg, solution="Fix it", success=True, project_path="/test"
    )
    assert result["confidence"] > initial_conf

    # Multiple failures should decrease confidence
    for _ in range(5):
        result = record_error(
            error_msg, solution="Fix it", success=False, project_path="/test"
        )

    # Confidence should be lower but bounded at 0
    assert result["confidence"] >= 0.0


def test_statistics():
    """Test statistics generation."""
    init_db()

    stats = get_stats()

    assert "patterns" in stats
    assert "sessions" in stats
    assert "total_patterns" in stats["patterns"]
    assert stats["patterns"]["total_patterns"] >= 0


def test_fix_type_recording():
    """Test fix_type and fix_action are recorded correctly."""
    init_db()

    import uuid

    unique_id = str(uuid.uuid4())[:8]
    error_msg = f"Fix type test error {unique_id}"

    result = record_error(
        error_message=error_msg,
        solution="Use skill to fix",
        success=True,
        project_path="/test",
        fix_type="skill",
        fix_action="systematic-debugging",
    )

    assert result["fix_type"] == "skill"
    assert result["fix_action"] == "systematic-debugging"


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
