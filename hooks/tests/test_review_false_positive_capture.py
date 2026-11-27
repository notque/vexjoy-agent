"""Tests for hooks/review-false-positive-capture.py — redact before slicing."""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

HOOK_PATH = Path(__file__).resolve().parent.parent / "review-false-positive-capture.py"


def test_secret_straddling_200_char_boundary_is_redacted_before_slicing(tmp_path: Path) -> None:
    """A secret starting near char 190 must be redacted in full before truncating to 200 chars."""
    prefix = "That finding from reviewer-code in app.py is a false positive: "
    padding = "x" * (189 - len(prefix)) + " "
    # Build a GitHub token dynamically so secret scanners never flag this fixture.
    token = "ghp_" + ("A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6"[:32])
    prompt = f"{prefix}{padding}{token} trailing context"
    assert len(prefix) + len(padding) == 190

    learn_dir = tmp_path / "learn"
    env = dict(os.environ)
    env.pop("REVIEW_FALSE_POSITIVE_CAPTURE_BYPASS", None)
    env["CLAUDE_LEARNING_DIR"] = str(learn_dir)
    env["HOME"] = str(tmp_path)

    proc = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps({"prompt": prompt, "cwd": str(tmp_path), "session_id": "fp-redact-test"}),
        capture_output=True,
        text=True,
        env=env,
        timeout=10,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr

    db_path = learn_dir / "learning.db"
    assert db_path.is_file()
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute("SELECT value FROM learnings WHERE topic = 'review-false-positive'").fetchall()
    assert len(rows) == 1
    stored_value = rows[0][0]
    assert "ghp_" not in stored_value
    assert token[:10] not in stored_value
    assert "<redacted>" in stored_value
