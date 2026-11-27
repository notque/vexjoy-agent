#!/usr/bin/env python3
"""Tests for scripts/record-misroute.py.

Covers: real SQLite persistence into CLAUDE_LEARNING_DIR, duplicate-key
observation count increment, error handling returning exit 1, and crash path.

Run with: python3 -m pytest scripts/tests/test_record_misroute.py -v
"""

from __future__ import annotations

import os
import runpy
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

_repo_root = Path(__file__).resolve().parents[2]
SCRIPT_PATH = str(_repo_root / "scripts" / "record-misroute.py")
HOOKS_LIB = str(_repo_root / "hooks" / "lib")

VALID_ARGS = [
    "--request",
    "original request",
    "--routed-to",
    "agent:skill",
    "--should-have-been",
    "other-agent:skill",
    "--reason",
    "wrong domain",
]


def _run_cli(db_dir: Path, extra_args: list[str] | None = None) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "CLAUDE_LEARNING_DIR": str(db_dir)}
    return subprocess.run(
        [sys.executable, SCRIPT_PATH, *(extra_args if extra_args is not None else VALID_ARGS)],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def test_records_misroute_into_sqlite_db(tmp_path: Path) -> None:
    """Running the CLI persists the misroute row directly into learning.db."""
    db_dir = tmp_path / "learning"
    result = _run_cli(db_dir)
    assert result.returncode == 0, result.stderr
    assert "Recorded misroute: agent:skill -> should have been other-agent:skill" in result.stdout

    db_path = db_dir / "learning.db"
    assert db_path.is_file()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("SELECT * FROM learnings WHERE topic = 'routing' AND category = 'misroute'").fetchall()
    finally:
        conn.close()

    assert len(rows) == 1
    row = dict(rows[0])
    assert row["key"] == "agent:skill->should-be-other-agent:skill"
    assert "request: original request" in row["value"]
    assert "routed_to: agent:skill" in row["value"]
    assert "should_have_been: other-agent:skill" in row["value"]
    assert "reason: wrong domain" in row["value"]
    assert row["tags"] == "misroute,routing-feedback"
    assert row["source"] == "manual:misroute-feedback"
    assert row["observation_count"] == 1


def test_repeat_misroute_increments_observation_count(tmp_path: Path) -> None:
    """Recording the same misroute pair twice updates observation_count to 2."""
    db_dir = tmp_path / "learning"
    assert _run_cli(db_dir).returncode == 0
    assert _run_cli(db_dir).returncode == 0

    conn = sqlite3.connect(db_dir / "learning.db")
    try:
        count = conn.execute(
            "SELECT observation_count FROM learnings WHERE topic = 'routing' AND key = ?",
            ("agent:skill->should-be-other-agent:skill",),
        ).fetchone()[0]
    finally:
        conn.close()
    assert count == 2


def test_recording_error_exits_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A failure inside learning_db_v2.record_learning exits 1 with stderr output."""
    if HOOKS_LIB not in sys.path:
        sys.path.insert(0, HOOKS_LIB)
    import learning_db_v2

    monkeypatch.setenv("CLAUDE_LEARNING_DIR", str(tmp_path / "learning"))
    monkeypatch.setattr(sys, "argv", [SCRIPT_PATH, *VALID_ARGS])

    def _boom(**_kwargs):
        raise RuntimeError("db locked")

    monkeypatch.setattr(learning_db_v2, "record_learning", _boom)
    with pytest.raises(SystemExit) as exc_info:
        runpy.run_path(SCRIPT_PATH, run_name="__main__")

    assert exc_info.value.code == 1
    assert "db locked" in capsys.readouterr().err


def test_missing_required_arg_exits_nonzero(tmp_path: Path) -> None:
    """Omitting a required CLI flag exits 2 (argparse error)."""
    result = _run_cli(tmp_path / "learning", ["--request", "only request"])
    assert result.returncode == 2
