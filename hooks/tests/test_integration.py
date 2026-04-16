#!/usr/bin/env python3
"""
Integration tests for the complete learning system (v2 unified database).

Tests the full workflow from error detection through learning to solution suggestion.
Uses an isolated temporary database — never touches the production DB at
~/.claude/learning/learning.db.
"""

import importlib
import sys
import uuid
from pathlib import Path

import pytest

# Add parent lib directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def isolated_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point learning DB to a temp directory so tests never touch production data."""
    db_dir = tmp_path / "learning"
    db_dir.mkdir()
    monkeypatch.setenv("CLAUDE_LEARNING_DIR", str(db_dir))

    # Reset the module-level _initialized flag so init_db() runs fresh each test.
    import learning_db_v2

    monkeypatch.setattr(learning_db_v2, "_initialized", False)
    return db_dir


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_end_to_end_learning(isolated_db: Path) -> None:
    """Test complete learning workflow."""
    from learning_db_v2 import (
        boost_confidence,
        classify_error,
        generate_signature,
        get_connection,
        init_db,
        record_learning,
    )

    init_db()

    unique_id = str(uuid.uuid4())[:8]
    error_message = f"Found 3 matches of the string to replace test-{unique_id}"

    error_type = classify_error(error_message)
    assert error_type == "multiple_matches", f"Expected 'multiple_matches', got '{error_type}'"

    signature = generate_signature(error_message, error_type)
    result = record_learning(
        topic=error_type,
        key=signature,
        value=f"{error_message} → Use replace_all or provide unique context",
        category="error",
        confidence=0.55,
        source="integration-test",
        project_path="/test/project",
        error_signature=signature,
        error_type=error_type,
    )
    assert result["is_new"] is True

    for _ in range(3):
        boost_confidence(error_type, signature, delta=0.12)

    with get_connection() as conn:
        row = conn.execute(
            "SELECT confidence FROM learnings WHERE error_signature = ?",
            (signature,),
        ).fetchone()
        assert row is not None, "Should find learning after recording"
        assert row["confidence"] >= 0.7, f"Expected confidence >= 0.7, got {row['confidence']}"


def test_multiple_error_types(isolated_db: Path) -> None:
    """Test learning multiple different error types."""
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
        error_type = classify_error(error_msg)
        assert error_type == expected_type, f"Expected {expected_type}, got {error_type}"


def test_confidence_bounds(isolated_db: Path) -> None:
    """Test confidence score bounds."""
    from learning_db_v2 import (
        boost_confidence,
        decay_confidence,
        init_db,
        record_learning,
    )

    init_db()

    unique_id = str(uuid.uuid4())[:8]
    topic = "test-bounds"
    key = f"bounds-test-{unique_id}"

    record_learning(
        topic=topic,
        key=key,
        value="Test solution for bounds checking",
        category="error",
        confidence=0.55,
        source="integration-test",
    )

    conf = 1.0
    for _ in range(15):
        conf = decay_confidence(topic, key, delta=0.18)

    assert conf >= 0.0, f"Confidence went below 0: {conf}"

    for _ in range(25):
        conf = boost_confidence(topic, key, delta=0.12)

    assert conf <= 1.0, f"Confidence went above 1: {conf}"
    assert conf > 0.5, f"Confidence should be high after many successes: {conf}"


def test_database_stats(isolated_db: Path) -> None:
    """Test database statistics."""
    from learning_db_v2 import get_stats, init_db

    init_db()

    stats = get_stats()
    assert "total_learnings" in stats
    assert "by_category" in stats
    assert "high_confidence" in stats
