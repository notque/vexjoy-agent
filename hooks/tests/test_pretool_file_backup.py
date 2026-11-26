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


def _run_hook(event, env_extra=None):
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_SESSION_ID"}
    env.update(env_extra or {})
    return subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        env=env,
    )


def test_one_session_shares_one_dir_keyed_on_event_session_id(tmp_path):
    """Claude Code sends session_id in the event and never sets CLAUDE_SESSION_ID.
    Two Edits in one session must land in one directory named for that id."""
    src = tmp_path / "target.txt"
    src.write_text("one")
    session_id = f"pytest-{uuid.uuid4().hex}"
    session_dir = BACKUP_ROOT / session_id
    event = {"session_id": session_id, "tool_input": {"file_path": str(src)}}
    try:
        assert _run_hook(event).returncode == 0
        src.write_text("two")
        assert _run_hook(event).returncode == 0
        contents = sorted(p.read_text() for p in session_dir.iterdir())
        assert contents == ["one", "two"]
    finally:
        shutil.rmtree(session_dir, ignore_errors=True)


def test_event_session_id_wins_over_env(tmp_path):
    src = tmp_path / "target.txt"
    src.write_text("x")
    event_id = f"pytest-{uuid.uuid4().hex}"
    env_id = f"pytest-{uuid.uuid4().hex}"
    event = {"session_id": event_id, "tool_input": {"file_path": str(src)}}
    try:
        assert _run_hook(event, {"CLAUDE_SESSION_ID": env_id}).returncode == 0
        assert (BACKUP_ROOT / event_id).is_dir()
        assert not (BACKUP_ROOT / env_id).exists()
    finally:
        shutil.rmtree(BACKUP_ROOT / event_id, ignore_errors=True)
        shutil.rmtree(BACKUP_ROOT / env_id, ignore_errors=True)


def test_new_session_prunes_stale_dirs_and_keeps_recent(tmp_path):
    src = tmp_path / "target.txt"
    src.write_text("x")
    tag = uuid.uuid4().hex
    stale = BACKUP_ROOT / f"pytest-stale-{tag}"
    recent = BACKUP_ROOT / f"pytest-recent-{tag}"
    new_id = f"pytest-new-{tag}"
    BACKUP_ROOT.mkdir(parents=True, mode=0o700, exist_ok=True)
    for d in (stale, recent):
        d.mkdir(mode=0o700)
        (d / "1-f.txt").write_text("old")
    eight_days_ago = __import__("time").time() - 8 * 24 * 3600
    os.utime(stale, (eight_days_ago, eight_days_ago))
    event = {"session_id": new_id, "tool_input": {"file_path": str(src)}}
    try:
        assert _run_hook(event).returncode == 0
        assert not stale.exists(), "a session dir untouched for 8 days should be pruned"
        assert recent.is_dir(), "a recently touched session dir must be kept"
        assert (BACKUP_ROOT / new_id).is_dir()
    finally:
        for d in (stale, recent, BACKUP_ROOT / new_id):
            shutil.rmtree(d, ignore_errors=True)
