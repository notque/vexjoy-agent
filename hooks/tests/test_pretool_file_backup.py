#!/usr/bin/env python3
"""
Tests for the pretool-file-backup hook (adr/020-pre-edit-file-backup.md).

Run with: python3 -m pytest hooks/tests/test_pretool_file_backup.py -v
"""

import json
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

HOOK_PATH = Path(__file__).parent.parent / "pretool-file-backup.py"
# The hook hardcodes this root; the session id is the only per-run lever.
BACKUP_ROOT = Path("/tmp/.claude-backups")


def test_backs_up_existing_file(tmp_path):
    """Baseline: an Edit on an existing file exits 0 and writes a backup."""
    src = tmp_path / "target.txt"
    src.write_text("hello")
    event = {"tool_input": {"file_path": str(src)}}
    # Unique id: never a live session's backup dir, never shared with a parallel run.
    session_id = f"pytest-{uuid.uuid4().hex}"
    session_dir = BACKUP_ROOT / session_id

    try:
        result = subprocess.run(
            [sys.executable, str(HOOK_PATH)],
            input=json.dumps(event),
            capture_output=True,
            text=True,
            env={**os.environ, "CLAUDE_SESSION_ID": session_id},
        )
        assert result.returncode == 0
        backups = [p for p in session_dir.rglob("*") if p.is_file()]
        assert backups, f"no backup written under {session_dir}"
        assert any(p.read_text() == "hello" for p in backups)
    finally:
        shutil.rmtree(session_dir, ignore_errors=True)


def test_exits_0_on_injected_exception():
    """A JSON boolean is valid JSON but has no .get() — main() calls
    event.get(...) downstream, raising AttributeError uncaught by main()'s
    own json.loads try/except. The __main__ guard must still exit 0 and
    print a visibility signal, not just silently swallow it."""
    result = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input="true",
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "[pretool-file-backup] HOOK-ERROR: AttributeError" in result.stderr
