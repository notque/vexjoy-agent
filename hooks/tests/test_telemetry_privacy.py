#!/usr/bin/env python3
"""Privacy of hook telemetry: redacted prompt capture and owner-only files.

Audit findings C-01/I-05 (prompts stored unredacted; telemetry files created
group- or world-readable) and F-16/B-09 (an unconditional, world-readable
/tmp/claude_hook_debug.log; backups in /tmp readable by every account).

Secret-shaped fixtures are assembled at runtime so no literal secret is
committed.

Run with: python3 -m pytest hooks/tests/test_telemetry_privacy.py -v
"""

import importlib.util
import json
import os
import sqlite3
import stat
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

HOOKS_DIR = Path(__file__).parent.parent
LIB_DIR = HOOKS_DIR / "lib"
sys.path.insert(0, str(LIB_DIR))

import hook_utils
import learning_db_v2 as ldb
import route_events
import usage_db


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def _load_hook(filename: str, name: str):
    spec = importlib.util.spec_from_file_location(name, HOOKS_DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    with patch("sys.exit"):
        spec.loader.exec_module(mod)
    return mod


# Assembled at runtime: never a literal secret in the repo.
AWS_KEY = "AKIA" + "Q" * 16
GITHUB_TOKEN = "ghp" + "_" + "a1B2c3D4" * 5
PASSWORD_VALUE = "hunter" + "2" * 8


# ---------------------------------------------------------------------------
# C-01: prompt-capture redacts secrets before storing, keeps the 500-char cap
# ---------------------------------------------------------------------------


def _human_prompt_with_secrets() -> str:
    return (
        "so i was trying to get the deploy working again and it keeps failing, "
        f"i pasted the key {AWS_KEY} and the token {GITHUB_TOKEN} into the config "
        "and put " + "pass" + "word=" + PASSWORD_VALUE + " in place but the staging box still rejects it, "
        "can you figure out why the auth step keeps timing out for us today"
    )


def _run_prompt_capture(prompt: str, tmp_path: Path) -> list[str]:
    learning_dir = tmp_path / "learning"
    learning_dir.mkdir()
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    result = subprocess.run(
        [sys.executable, str(HOOKS_DIR / "prompt-capture.py")],
        input=json.dumps({"prompt": prompt, "cwd": str(repo), "session_id": "s1"}),
        capture_output=True,
        text=True,
        env={
            "CLAUDE_LEARNING_DIR": str(learning_dir),
            "CLAUDE_HOOK_ERRORS_PATH": str(tmp_path / "hook-errors.jsonl"),
            "PATH": "/usr/bin:/bin",
            "HOME": str(tmp_path),
        },
        cwd=str(repo),
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    db = learning_dir / "learning.db"
    if not db.exists():
        return []
    with sqlite3.connect(db) as conn:
        return [r[0] for r in conn.execute("SELECT value FROM learnings WHERE topic='voice-sample'")]


def test_prompt_capture_redacts_secrets_before_storing(tmp_path):
    rows = _run_prompt_capture(_human_prompt_with_secrets(), tmp_path)
    assert len(rows) == 1, "capture must stay on for a genuine human prompt"
    stored = rows[0]
    assert AWS_KEY not in stored
    assert GITHUB_TOKEN not in stored
    assert PASSWORD_VALUE not in stored
    assert "<redacted:" in stored
    assert stored.startswith("so i was trying to get the deploy working")


def test_prompt_capture_keeps_500_char_cap(tmp_path):
    prompt = ("we keep tuning the routing weights by hand and it is slow going " * 20).strip()
    rows = _run_prompt_capture(prompt, tmp_path)
    assert len(rows) == 1
    assert rows[0] == prompt[:500]


def test_prompt_capture_redacts_secret_straddling_the_cap(tmp_path):
    """Redaction runs on the whole prompt before the cap, so a key cut by the cap is not half-stored."""
    filler = "we keep tuning the routing weights by hand and it is slow going "
    head = (filler * 8)[:490]
    prompt = head + f" {AWS_KEY} " + filler * 2
    rows = _run_prompt_capture(prompt, tmp_path)
    assert len(rows) == 1
    assert len(rows[0]) <= 500
    # The cap leaves 9 key characters in the row; redacting after the cap would keep them.
    assert "AKIA" not in rows[0]


def test_secret_redact_covers_vendor_tokens_and_pem():
    import secret_redact

    pem_label = "RSA " + "PRIVATE " + "KEY"
    pem = "-----BEGIN " + pem_label + "-----\nMIIabc\n-----END " + pem_label + "-----"
    text = f"a {AWS_KEY} b {GITHUB_TOKEN} c Bearer {'x' * 24} d {pem} e"
    out = secret_redact.redact_text(text)
    for secret in (AWS_KEY, GITHUB_TOKEN, "x" * 24, "MIIabc"):
        assert secret not in out
    assert out.startswith("a <redacted:aws-key:")
    assert secret_redact.redact_text("plain words stay as they are") == "plain words stay as they are"


# ---------------------------------------------------------------------------
# I-05: telemetry files are created owner-only (0600) in 0700 directories
# ---------------------------------------------------------------------------


def test_hook_errors_jsonl_created_owner_only(tmp_path, monkeypatch):
    path = tmp_path / "newdir" / "hook-errors.jsonl"
    monkeypatch.setenv("CLAUDE_HOOK_ERRORS_PATH", str(path))
    hook_utils.hook_error("privacy-test", RuntimeError("boom"))
    assert json.loads(path.read_text(encoding="utf-8"))["hook"] == "privacy-test"
    assert _mode(path) == 0o600
    assert _mode(path.parent) == 0o700


def test_hook_errors_jsonl_existing_loose_file_tightened(tmp_path, monkeypatch):
    path = tmp_path / "hook-errors.jsonl"
    path.write_text("")
    os.chmod(path, 0o664)
    monkeypatch.setenv("CLAUDE_HOOK_ERRORS_PATH", str(path))
    hook_utils.hook_error("privacy-test", RuntimeError("boom"))
    assert _mode(path) == 0o600


def test_existing_file_owned_by_someone_else_is_not_chmodded(tmp_path, monkeypatch):
    path = tmp_path / "shared.jsonl"
    path.write_text("")
    os.chmod(path, 0o664)
    monkeypatch.setattr(hook_utils.os, "getuid", lambda: path.stat().st_uid + 1)
    with hook_utils.open_owner_only_append(path) as fh:
        fh.write("x\n")
    assert _mode(path) == 0o664


def test_route_events_jsonl_created_owner_only(tmp_path, monkeypatch):
    learning_dir = tmp_path / "learning"
    monkeypatch.setenv("CLAUDE_LEARNING_DIR", str(learning_dir))
    route_events.record_outcome_event(session="s1", key="a:b", outcome="success")
    path = learning_dir / "route-events.jsonl"
    assert path.exists()
    assert _mode(path) == 0o600
    assert _mode(learning_dir) == 0o700


def test_route_events_existing_loose_file_tightened(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_LEARNING_DIR", str(tmp_path))
    path = tmp_path / "route-events.jsonl"
    path.write_text("")
    os.chmod(path, 0o664)
    route_events.record_outcome_event(session="s1", key="a:b", outcome="success")
    assert _mode(path) == 0o600
    assert path.read_text(encoding="utf-8").count("\n") == 1


def test_usage_db_created_owner_only(tmp_path, monkeypatch):
    learning_dir = tmp_path / "learning"
    monkeypatch.setenv("CLAUDE_LEARNING_DIR", str(learning_dir))
    usage_db.init_db()
    with usage_db.get_connection() as conn:
        conn.execute("SELECT 1").fetchone()
        db = learning_dir / "usage.db"
        assert _mode(db) == 0o600
        for side in ("usage.db-wal", "usage.db-shm"):
            side_path = learning_dir / side
            if side_path.exists():
                assert _mode(side_path) == 0o600, side
    assert _mode(learning_dir) == 0o700


def test_usage_db_existing_loose_file_tightened(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_LEARNING_DIR", str(tmp_path))
    db = tmp_path / "usage.db"
    sqlite3.connect(db).close()
    os.chmod(db, 0o644)
    usage_db.init_db()
    assert _mode(db) == 0o600


def test_learning_db_created_owner_only_before_first_write(tmp_path, monkeypatch):
    learning_dir = tmp_path / "learning"
    monkeypatch.setenv("CLAUDE_LEARNING_DIR", str(learning_dir))
    with ldb.get_connection() as conn:
        conn.execute("CREATE TABLE t (x INTEGER)")
        conn.execute("INSERT INTO t VALUES (1)")
        conn.commit()
        assert _mode(learning_dir / "learning.db") == 0o600
        for side in ("learning.db-wal", "learning.db-shm"):
            side_path = learning_dir / side
            if side_path.exists():
                assert _mode(side_path) == 0o600, side


# ---------------------------------------------------------------------------
# F-16 / B-09: the shared hook debug log is opt-in and owner-only
# ---------------------------------------------------------------------------

DEBUG_WRITERS = [
    ("adr-lifecycle-on-merge.py", "DEBUG_LOG", "debug_log"),
    ("subagent-state-tracker.py", "_DEBUG_LOG", "_debug"),
]


@pytest.mark.parametrize("filename,path_attr,func_name", DEBUG_WRITERS)
def test_hook_debug_log_not_written_without_debug_flag(filename, path_attr, func_name, tmp_path, monkeypatch):
    mod = _load_hook(filename, filename.replace("-", "_")[:-3])
    log = tmp_path / "claude_hook_debug.log"
    monkeypatch.setattr(mod, path_attr, log)
    monkeypatch.delenv("CLAUDE_HOOKS_DEBUG", raising=False)
    getattr(mod, func_name)("a debug line")
    assert not log.exists()


@pytest.mark.parametrize("filename,path_attr,func_name", DEBUG_WRITERS)
def test_hook_debug_log_owner_only_with_debug_flag(filename, path_attr, func_name, tmp_path, monkeypatch):
    mod = _load_hook(filename, filename.replace("-", "_")[:-3])
    log = tmp_path / "claude_hook_debug.log"
    monkeypatch.setattr(mod, path_attr, log)
    monkeypatch.setenv("CLAUDE_HOOKS_DEBUG", "1")
    getattr(mod, func_name)("a debug line")
    assert "a debug line" in log.read_text(encoding="utf-8")
    assert _mode(log) == 0o600


def test_learning_db_debug_line_opt_in_and_owner_only(tmp_path, monkeypatch):
    log = tmp_path / "claude_hook_debug.log"
    monkeypatch.setattr(ldb, "_DEBUG_LOG_PATH", str(log))
    monkeypatch.delenv("CLAUDE_HOOKS_DEBUG", raising=False)
    ldb._debug_line("first")
    assert not log.exists()
    monkeypatch.setenv("CLAUDE_HOOKS_DEBUG", "1")
    ldb._debug_line("second")
    assert log.read_text(encoding="utf-8") == "[learning_db_v2] second\n"
    assert _mode(log) == 0o600


# ---------------------------------------------------------------------------
# B-09: file backups are owner-only (dirs 0700, files 0600)
# ---------------------------------------------------------------------------


def test_file_backup_dirs_and_files_owner_only(tmp_path, monkeypatch):
    mod = _load_hook("pretool-file-backup.py", "pretool_file_backup_privacy")
    base = tmp_path / ".claude-backups"
    monkeypatch.setattr(mod, "_BACKUP_BASE", base)
    monkeypatch.setattr(mod, "_BACKUP_ROOT", base / "sess-1")
    src = tmp_path / "target.txt"
    src.write_text("hello")
    os.chmod(src, 0o644)
    monkeypatch.setattr(mod, "read_stdin", lambda **_kw: json.dumps({"tool_input": {"file_path": str(src)}}))
    with pytest.raises(SystemExit):
        mod.main()
    backups = [p for p in (base / "sess-1").iterdir() if p.is_file()]
    assert len(backups) == 1
    assert backups[0].read_text() == "hello"
    assert _mode(backups[0]) == 0o600
    assert _mode(base) == 0o700
    assert _mode(base / "sess-1") == 0o700
    assert backups[0].stat().st_mtime == pytest.approx(src.stat().st_mtime, abs=1e-3)
    assert _mode(src) == 0o644


def test_file_backup_docstring_no_longer_claims_tmp_clears_on_reboot():
    text = (HOOKS_DIR / "pretool-file-backup.py").read_text(encoding="utf-8")
    assert "clears on reboot" not in text


# ---------------------------------------------------------------------------
# Review follow-ups: bounded redaction time, no symlink following in /tmp,
# no empty backup left when the source cannot be read
# ---------------------------------------------------------------------------


def test_secret_redact_runs_in_linear_time_on_long_dotted_runs():
    """Unbounded key-name quantifiers made kv/entropy quadratic (12 KB took ~10 s, past the hook timeout)."""
    import time

    import secret_redact

    text = "please look at this long thing " + "a." * 6000
    start = time.monotonic()
    assert secret_redact.redact_text(text) == text
    assert time.monotonic() - start < 3.0
    key = "my_" + "api" + "_key" + "=" + "Z" * 20
    assert "Z" * 20 not in secret_redact.redact_text(key)


def test_hook_debug_log_does_not_follow_a_symlink(tmp_path, monkeypatch):
    target = tmp_path / "victim.txt"
    target.write_text("original\n")
    os.chmod(target, 0o644)
    log = tmp_path / "claude_hook_debug.log"
    log.symlink_to(target)
    monkeypatch.setenv("CLAUDE_HOOKS_DEBUG", "1")
    hook_utils.append_hook_debug_log(log, "planted line")
    assert target.read_text() == "original\n"
    assert _mode(target) == 0o644


@pytest.mark.skipif(not hasattr(os, "getuid") or os.getuid() == 0, reason="root reads any file")
def test_file_backup_leaves_no_empty_copy_when_source_unreadable(tmp_path):
    mod = _load_hook("pretool-file-backup.py", "pretool_file_backup_unreadable")
    src = tmp_path / "secret.txt"
    src.write_text("hello")
    os.chmod(src, 0)
    dest = tmp_path / "copy.txt"
    try:
        with pytest.raises(OSError):
            mod._copy_owner_only(src, dest)
    finally:
        os.chmod(src, 0o600)
    assert not dest.exists()
