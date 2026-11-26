"""Tests for scripts/benchmark-hooks.py: hook selection and sandbox isolation."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SPEC = importlib.util.spec_from_file_location("benchmark_hooks", REPO_ROOT / "scripts" / "benchmark-hooks.py")
bh = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(bh)


def test_matcher_semantics():
    assert bh.matches("", "Grep")
    assert bh.matches("*", "Grep")
    assert bh.matches("Write|Edit", "Edit")
    assert bh.matches("Bash", None)
    assert not bh.matches("Write|Edit", "MultiEdit")
    assert not bh.matches("Bash", "BashOutput")


def test_registered_selects_by_event_and_tool():
    s = {
        "hooks": {
            "PreToolUse": [
                {"matcher": "Bash", "hooks": [{"command": "a"}]},
                {"hooks": [{"command": "b"}]},
            ],
            "PostToolUse": [{"hooks": [{"command": "c"}]}],
        }
    }
    assert bh.registered(s, "PreToolUse", "Bash") == ["a", "b"]
    assert bh.registered(s, "PreToolUse", "Read") == ["b"]


def test_env_drops_keys_and_live_ids(monkeypatch, tmp_path):
    keys = ("TYPESAFE_API_KEY", "AI_GATEWAY_API_KEY", "GH_TOKEN", "ANTHROPIC_API_KEY")
    for key in keys:
        monkeypatch.setenv(key, "secret-value")
    monkeypatch.setenv("CLAUDE_SESSION_ID", "live-1")
    env = bh.build_env(tmp_path, home=tmp_path / "home", work=tmp_path / "work", session_id="bench-x")
    for key in keys:
        assert key not in env
    assert env["CLAUDE_SESSION_ID"] == "bench-x"
    assert env["HOME"] == str(tmp_path / "home")
    assert env["VEXJOY_SYNC_DISABLED"] == "1"


def test_runs_the_registered_command_under_the_sandbox_home(tmp_path):
    fixture = tmp_path / "settings.json"
    command = 'printf %s "$HOME" > "$TMPDIR/seen-home"'
    fixture.write_text(json.dumps({"hooks": {"UserPromptSubmit": [{"hooks": [{"command": command}]}]}}))
    rc = bh.main(
        [
            "--settings",
            str(fixture),
            "--sandbox-root",
            str(tmp_path / "sb"),
            "--iterations",
            "1",
            "--event",
            "UserPromptSubmit",
            "--json",
        ]
    )
    assert rc == 0
    seen = (tmp_path / "sb" / "tmp" / "seen-home").read_text()
    assert seen.startswith(str(tmp_path))
    assert seen != str(Path.home())


def test_cleanup_removes_only_the_bench_session_files(tmp_path):
    backup = tmp_path / ".claude-backups" / "bench-x" / "f"
    backup.parent.mkdir(parents=True)
    backup.write_text("x")
    lock = tmp_path / "claude-routing-outcomes-bench-x.json.lock"
    lock.write_text("")
    other = tmp_path / "claude-other-live-1.state"
    other.write_text("")
    bh.cleanup_tmp("bench-x", base=tmp_path)
    assert not backup.exists()
    assert not backup.parent.exists()
    assert not lock.exists()
    assert other.exists()
