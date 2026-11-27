"""Tests for pretool-commit-verification-gate.py.

Covers: trailer present/absent in every mode, observe log, enforce deny-then-allow,
none(reason) trailer, off mode, heredoc and multi-line -m forms, non-commit
commands, malformed stdin, passthrough commits.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parent.parent / "pretool-commit-verification-gate.py"


def _run(
    command: str,
    *,
    mode: str = "observe",
    session_id: str = "test-session",
    tmp_path: Path | None = None,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run the hook with a synthetic event."""
    env = dict(os.environ)
    env["COMMIT_VERIFY_GATE_MODE"] = mode
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if tmp_path:
        env["HOME"] = str(tmp_path)
    for key in ("CLAUDE_HOOKS_DEBUG",):
        env.pop(key, None)
    if extra_env:
        env.update(extra_env)
    payload = json.dumps(
        {
            "tool_input": {"command": command},
            "session_id": session_id,
            "cwd": str(tmp_path) if tmp_path else "/tmp",
        }
    )
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=payload,
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
    )


def _observe_log(tmp_path: Path) -> list[dict]:
    path = tmp_path / ".claude" / "state" / "commit-verify-gate" / "observe.jsonl"
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    return [json.loads(line) for line in lines]


def _enforce_count(tmp_path: Path, session_id: str = "test-session") -> int:
    import re

    safe_id = re.sub(r"[^A-Za-z0-9_-]", "_", session_id)[:64]
    path = tmp_path / ".claude" / "state" / "commit-verify-gate" / f"enforce-{safe_id}.count"
    if not path.exists():
        return 0
    return int(path.read_text(encoding="utf-8").strip())


# --- Trailer present: passes in every mode ---


@pytest.mark.parametrize("mode", ["off", "observe", "enforce"])
def test_trailer_present_passes(tmp_path: Path, mode: str) -> None:
    msg = 'git commit -m "added feature\n\nVerified-By: tests\nClaude-Session: https://example.com"'
    result = _run(msg, mode=mode, tmp_path=tmp_path)
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_none_reason_trailer_passes(tmp_path: Path) -> None:
    msg = 'git commit -m "wip\n\nVerified-By: none (quick iteration)"'
    result = _run(msg, mode="enforce", tmp_path=tmp_path)
    assert result.returncode == 0
    assert result.stdout.strip() == ""


# --- Missing trailer in observe mode ---


def test_observe_allows_and_logs(tmp_path: Path) -> None:
    msg = 'git commit -m "no trailer here"'
    result = _run(msg, mode="observe", tmp_path=tmp_path)
    assert result.returncode == 0
    assert result.stdout.strip() == ""  # no deny output
    logs = _observe_log(tmp_path)
    assert len(logs) == 1
    assert logs[0]["reason"] == "missing Verified-By trailer"
    assert set(logs[0].keys()) == {"ts", "repo", "reason"}
    assert "no trailer" not in json.dumps(logs[0])  # no message text in log


# --- Missing trailer in enforce mode ---


def test_enforce_denies_twice_then_allows(tmp_path: Path) -> None:
    msg = 'git commit -m "no trailer"'
    sid = "enforce-test-session"

    # First attempt: deny.
    r1 = _run(msg, mode="enforce", session_id=sid, tmp_path=tmp_path)
    assert r1.returncode == 0
    out1 = json.loads(r1.stdout)
    assert out1["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert _enforce_count(tmp_path, sid) == 1

    # Second attempt: deny.
    r2 = _run(msg, mode="enforce", session_id=sid, tmp_path=tmp_path)
    assert r2.returncode == 0
    out2 = json.loads(r2.stdout)
    assert out2["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert _enforce_count(tmp_path, sid) == 2

    # Third attempt: allowed (deadlock prevention).
    r3 = _run(msg, mode="enforce", session_id=sid, tmp_path=tmp_path)
    assert r3.returncode == 0
    assert r3.stdout.strip() == ""  # no deny — stdout must be empty
    assert "Allowed after 2 prior blocks" in r3.stderr


# --- Off mode writes nothing ---


def test_off_mode_writes_nothing(tmp_path: Path) -> None:
    msg = 'git commit -m "no trailer"'
    result = _run(msg, mode="off", tmp_path=tmp_path)
    assert result.returncode == 0
    assert result.stdout.strip() == ""
    assert not _observe_log(tmp_path)


# --- Heredoc form ---


def test_heredoc_message_parsed(tmp_path: Path) -> None:
    msg = "git commit -m \"$(cat <<'EOF'\nadded feature\n\nVerified-By: manual\nEOF\n)\""
    result = _run(msg, mode="enforce", tmp_path=tmp_path)
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_heredoc_missing_trailer(tmp_path: Path) -> None:
    msg = "git commit -m \"$(cat <<'EOF'\nadded feature without verification\nEOF\n)\""
    result = _run(msg, mode="observe", tmp_path=tmp_path)
    assert result.returncode == 0
    logs = _observe_log(tmp_path)
    assert len(logs) == 1


def test_heredoc_with_inner_quotes_and_shell_ops_passes(tmp_path: Path) -> None:
    """Heredoc bodies containing inner double quotes and `;&|\\n` must not split mid-message."""
    cmd = 'git commit -m "$(cat <<\'EOF\'\nfix "a | b"; don\'t & split\n\nVerified-By: tests\nEOF\n)"'
    result = _run(cmd, mode="enforce", tmp_path=tmp_path)
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_heredoc_with_inner_quotes_and_shell_ops_missing_trailer_denied(tmp_path: Path) -> None:
    """Heredoc bodies with inner quotes/operators still deny when Verified-By is absent."""
    cmd = 'git commit -m "$(cat <<\'EOF\'\nfix "a | b"; don\'t & split\nEOF\n)"'
    result = _run(cmd, mode="enforce", session_id="s-heredoc-ops", tmp_path=tmp_path)
    assert result.returncode == 0
    out = json.loads(result.stdout)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"


# --- Multi-line -m ---


def test_multi_m_flags(tmp_path: Path) -> None:
    """Repeated -m: trailer in the second one is enough."""
    msg = 'git commit -m "subject line" -m "Verified-By: tests"'
    result = _run(msg, mode="enforce", tmp_path=tmp_path)
    assert result.returncode == 0
    assert result.stdout.strip() == ""


# --- -F file form ---


def test_file_flag(tmp_path: Path) -> None:
    msg_file = tmp_path / "commit-msg.txt"
    msg_file.write_text("added feature\n\nVerified-By: ci-local\n", encoding="utf-8")
    cmd = f"git commit -F {msg_file}"
    result = _run(cmd, mode="enforce", tmp_path=tmp_path)
    assert result.returncode == 0
    assert result.stdout.strip() == ""


# --- Non-commit commands ---


def test_non_commit_command_passes(tmp_path: Path) -> None:
    result = _run("git push origin main", mode="enforce", tmp_path=tmp_path)
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_non_git_command_passes(tmp_path: Path) -> None:
    result = _run("echo hello", mode="enforce", tmp_path=tmp_path)
    assert result.returncode == 0
    assert result.stdout.strip() == ""


# --- Malformed stdin ---


def test_malformed_stdin_exits_zero(tmp_path: Path) -> None:
    env = dict(os.environ)
    env["COMMIT_VERIFY_GATE_MODE"] = "enforce"
    env["HOME"] = str(tmp_path)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    result = subprocess.run(
        [sys.executable, str(HOOK)],
        input="not json at all",
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_empty_stdin_exits_zero(tmp_path: Path) -> None:
    env = dict(os.environ)
    env["COMMIT_VERIFY_GATE_MODE"] = "enforce"
    env["HOME"] = str(tmp_path)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    result = subprocess.run(
        [sys.executable, str(HOOK)],
        input="",
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
    )
    assert result.returncode == 0


# --- Passthrough commits ---


@pytest.mark.parametrize(
    "command",
    [
        'git commit --amend -m "no trailer"',
        "git commit --fixup abc123",
        "git commit --squash abc123",
        "git commit -C HEAD",
        "git commit -c HEAD",
    ],
)
def test_passthrough_flag_passes(tmp_path: Path, command: str) -> None:
    result = _run(command, mode="enforce", tmp_path=tmp_path)
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_passthrough_subject_passes(tmp_path: Path) -> None:
    result = _run('git commit -m "Merge branch main into feature"', mode="enforce", tmp_path=tmp_path)
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_revert_subject_passes(tmp_path: Path) -> None:
    result = _run("git commit -m 'Revert added feature'", mode="enforce", tmp_path=tmp_path)
    assert result.returncode == 0
    assert result.stdout.strip() == ""


# --- Bypass ---


def test_bypass_env_skips_all(tmp_path: Path) -> None:
    msg = 'git commit -m "no trailer"'
    result = _run(msg, mode="enforce", tmp_path=tmp_path, extra_env={"COMMIT_VERIFY_GATE_BYPASS": "1"})
    assert result.returncode == 0
    assert result.stdout.strip() == ""


# --- -am form ---


def test_am_flag(tmp_path: Path) -> None:
    """git commit -am 'msg' has -a and -m collapsed."""
    result = _run('git commit -am "no trailer"', mode="observe", tmp_path=tmp_path)
    assert result.returncode == 0
    logs = _observe_log(tmp_path)
    assert len(logs) == 1


# --- Global git options and commit-message text must not trigger passthrough ---


@pytest.mark.parametrize(
    "command",
    [
        'git -C /tmp/some-repo commit -m "no trailer"',
        'git -c user.name=Bot commit -m "no trailer"',
        'git commit -m "document --amend behavior without trailer"',
        'git commit -m "explain -c flag handling without trailer"',
    ],
)
def test_global_git_opts_and_message_flags_do_not_bypass_gate(tmp_path: Path, command: str) -> None:
    result = _run(command, mode="enforce", session_id="s-global", tmp_path=tmp_path)
    assert result.returncode == 0
    out = json.loads(result.stdout)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"


# --- Heredoc + additional -m / -F flags and attached short flags ---


def test_heredoc_plus_second_m_trailer_passes(tmp_path: Path) -> None:
    cmd = 'git commit -m "$(cat <<\'EOF\'\nadded feature\nEOF\n)" -m "Verified-By: tests"'
    result = _run(cmd, mode="enforce", tmp_path=tmp_path)
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_heredoc_plus_relative_file_flag_passes(tmp_path: Path) -> None:
    (tmp_path / "trailer.txt").write_text("Verified-By: ci-local\n", encoding="utf-8")
    cmd = "git commit -m \"$(cat <<'EOF'\nadded feature\nEOF\n)\" -F trailer.txt"
    result = _run(cmd, mode="enforce", tmp_path=tmp_path)
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_relative_file_flag_resolved_against_git_dash_c(tmp_path: Path) -> None:
    sub = tmp_path / "subrepo"
    sub.mkdir()
    (sub / "msg.txt").write_text("fixed bug\n\nVerified-By: tests\n", encoding="utf-8")
    cmd = f"git -C {sub} commit -F msg.txt"
    result = _run(cmd, mode="enforce", tmp_path=tmp_path)
    assert result.returncode == 0
    assert result.stdout.strip() == ""


@pytest.mark.parametrize("cmd", ['git commit -m"no trailer"', 'git commit -am"no trailer"'])
def test_attached_short_m_flags_missing_trailer_denied(tmp_path: Path, cmd: str) -> None:
    result = _run(cmd, mode="enforce", session_id="s-attached", tmp_path=tmp_path)
    assert result.returncode == 0
    out = json.loads(result.stdout)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_attached_short_am_flag_with_trailer_passes(tmp_path: Path) -> None:
    cmd = 'git commit -am"added feature\n\nVerified-By: tests"'
    result = _run(cmd, mode="enforce", tmp_path=tmp_path)
    assert result.returncode == 0
    assert result.stdout.strip() == ""


# --- Empty session_id guard in enforce mode ---


def test_empty_session_id_does_not_share_counter(tmp_path: Path) -> None:
    msg = 'git commit -m "no trailer"'
    for _ in range(3):
        res = _run(msg, mode="enforce", session_id="", tmp_path=tmp_path)
        assert res.returncode == 0
        out = json.loads(res.stdout)
        assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
    shared_counter = tmp_path / ".claude" / "state" / "commit-verify-gate" / "enforce-.count"
    assert not shared_counter.exists()
