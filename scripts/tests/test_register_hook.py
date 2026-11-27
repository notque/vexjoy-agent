"""Hook timeouts are seconds: the repo settings, register-hook.py add, and register-hook.py validate.

Claude Code reads a hook ``timeout`` in seconds. The repo settings used to carry
millisecond-looking values (3000 for the unified gate gave it 50 minutes), and
register-hook.py documented its ``--timeout`` in ms, which is where they came from.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "register-hook.py"
SETTINGS = REPO / ".claude" / "settings.json"
# A timed-out gate fails open, so these events never get less than 10 s.
GATE_EVENTS = {"PreToolUse", "PermissionRequest", "UserPromptSubmit"}

_spec = importlib.util.spec_from_file_location("hook_pyguard", REPO / "scripts" / "hook-pyguard.py")
assert _spec and _spec.loader
pyguard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pyguard)


def _entries(settings: dict) -> list[tuple[str, dict]]:
    return [(event, e) for event, groups in settings["hooks"].items() for g in groups for e in g["hooks"]]


def _timeout_of(settings: dict, needle: str) -> object:
    matches = [e["timeout"] for _, e in _entries(settings) if needle in e["command"]]
    assert len(matches) == 1, (needle, matches)
    return matches[0]


def test_repo_settings_timeouts_are_seconds_with_gate_floors() -> None:
    settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
    for event, entry in _entries(settings):
        timeout = entry["timeout"]
        label = f"{event}: {entry['command']}"
        assert isinstance(timeout, int) and 0 < timeout <= 600, label
        assert timeout >= (10 if event in GATE_EVENTS else 5), label


def test_repo_settings_keep_the_budgets_the_hooks_were_written_for() -> None:
    """The hooks' own comments name these budgets in seconds."""
    settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
    assert _timeout_of(settings, "sync-to-user-claude.py") == 20  # TIMEOUT_S = 18, under the 20 s hook timeout
    assert _timeout_of(settings, "jev-route-injector-userprompt.py") == 26  # 24 s budget under 26 s
    assert _timeout_of(settings, "pretool-review-before-push-gate.py") == 10  # 6 s budget, 10 s hook timeout
    assert _timeout_of(settings, "session-bootstrap.sh") == 240  # install.sh capped at 200 s inside 240 s


def _home(tmp_path: Path, timeouts: dict[str, object]) -> Path:
    """A HOME whose settings register one backed hook per (filename -> timeout)."""
    home = tmp_path / "home"
    hooks = home / ".claude" / "hooks"
    hooks.mkdir(parents=True)
    entries = []
    for name, timeout in timeouts.items():
        (hooks / name).write_text("import sys\n", encoding="utf-8")
        entries.append({"type": "command", "command": f'python3 "$HOME/.claude/hooks/{name}"', "timeout": timeout})
    settings = {"hooks": {"PostToolUse": [{"matcher": "Write", "hooks": entries}]}}
    (home / ".claude" / "settings.json").write_text(json.dumps(settings), encoding="utf-8")
    return home


def _env(home: Path) -> dict[str, str]:
    return {**os.environ, "HOME": str(home)}


def test_validate_rejects_a_timeout_over_600_seconds(tmp_path: Path) -> None:
    home = _home(tmp_path, {"ok.py": 5, "ms.py": 3000})
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "validate"], capture_output=True, text=True, env=_env(home), timeout=60
    )
    assert result.returncode == 2, result.stdout + result.stderr
    assert "[FAIL] PostToolUse/ms.py: timeout 3000" in result.stdout
    assert "[PASS] PostToolUse/ok.py" in result.stdout


@pytest.mark.parametrize("bad", [0, -5, "10", True])
def test_validate_rejects_a_timeout_that_is_not_a_positive_number(tmp_path: Path, bad: object) -> None:
    home = _home(tmp_path, {"bad.py": bad})
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "validate"], capture_output=True, text=True, env=_env(home), timeout=60
    )
    assert result.returncode == 2, result.stdout + result.stderr
    assert "[FAIL] PostToolUse/bad.py: timeout" in result.stdout


def test_validate_warns_over_120_seconds_but_passes(tmp_path: Path) -> None:
    home = _home(tmp_path, {"slow.py": 240, "ok.py": 120})
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "validate"], capture_output=True, text=True, env=_env(home), timeout=60
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "[WARN] PostToolUse/slow.py: timeout 240 s" in result.stdout
    assert "[WARN] PostToolUse/ok.py" not in result.stdout
    assert "[FAIL]" not in result.stdout


def _add(home: Path, hook: Path, event: str, *extra: str) -> subprocess.CompletedProcess[str]:
    argv = [sys.executable, str(SCRIPT), "add", "--file", str(hook), "--event", event, "--description", "x", *extra]
    return subprocess.run(argv, capture_output=True, text=True, env=_env(home), timeout=60)


def _guarded_hook(tmp_path: Path, name: str) -> Path:
    hook = tmp_path / name
    hook.write_text("import sys\n\nprint(sys.argv)\n", encoding="utf-8")
    assert pyguard.main(["--apply", "--file", str(hook)]) == 0
    return hook


def _empty_home(tmp_path: Path, *events: str) -> Path:
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    settings = {"hooks": {event: [{"hooks": []}] for event in events}}
    (home / ".claude" / "settings.json").write_text(json.dumps(settings), encoding="utf-8")
    return home


@pytest.mark.parametrize(("event", "expected"), [("PreToolUse", 10), ("UserPromptSubmit", 10), ("PostToolUse", 5)])
def test_add_defaults_to_seconds_with_a_gate_floor(tmp_path: Path, event: str, expected: int) -> None:
    home = _empty_home(tmp_path, event)
    added = _add(home, _guarded_hook(tmp_path, "new-hook.py"), event)
    assert added.returncode == 0, added.stderr
    settings = json.loads((home / ".claude" / "settings.json").read_text(encoding="utf-8"))
    assert _timeout_of(settings, "new-hook.py") == expected


def test_add_refuses_a_millisecond_timeout_before_deploying(tmp_path: Path) -> None:
    home = _empty_home(tmp_path, "PreToolUse")
    refused = _add(home, _guarded_hook(tmp_path, "new-hook.py"), "PreToolUse", "--timeout", "3000")
    assert refused.returncode == 1, refused.stdout + refused.stderr
    assert "3000" in refused.stderr and "600" in refused.stderr
    assert not (home / ".claude" / "hooks" / "new-hook.py").exists()
    settings = json.loads((home / ".claude" / "settings.json").read_text(encoding="utf-8"))
    assert _entries(settings) == []


def _remove(home: Path, name: str, event: str, *extra: str) -> subprocess.CompletedProcess[str]:
    argv = [sys.executable, str(SCRIPT), "remove", "--name", name, "--event", event, *extra]
    return subprocess.run(argv, capture_output=True, text=True, env=_env(home), timeout=60)


def test_add_rolls_back_on_syntax_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import argparse

    spec = importlib.util.spec_from_file_location("register_hook_mod", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    home = _empty_home(tmp_path, "PostToolUse")
    monkeypatch.setattr(mod, "SETTINGS_PATH", home / ".claude" / "settings.json")
    monkeypatch.setattr(mod, "HOOKS_DIR", home / ".claude" / "hooks")
    monkeypatch.setattr(mod, "guard_problems", lambda _src: [])

    hook = tmp_path / "bad'syntax.py"
    hook.write_text("def broken(:\n    pass\n", encoding="utf-8")
    args = argparse.Namespace(file=str(hook), event="PostToolUse", description="x", timeout=5, matcher=None)
    with pytest.raises(SystemExit) as exc:
        mod.cmd_add(args)
    assert exc.value.code == 1
    captured = capsys.readouterr()
    assert "syntax errors" in captured.err
    assert not (home / ".claude" / "hooks" / "bad'syntax.py").exists()
    settings = json.loads((home / ".claude" / "settings.json").read_text(encoding="utf-8"))
    assert _entries(settings) == []


def test_add_creates_missing_event_and_matcher_group_in_place(tmp_path: Path) -> None:
    home = _empty_home(tmp_path)  # empty hooks dict
    hook = _guarded_hook(tmp_path, "my-gate.py")
    res = _add(home, hook, "PreToolUse", "--matcher", "Bash")
    assert res.returncode == 0, res.stdout + res.stderr
    settings = json.loads((home / ".claude" / "settings.json").read_text(encoding="utf-8"))
    groups = settings["hooks"]["PreToolUse"]
    assert len(groups) == 1
    assert groups[0]["matcher"] == "Bash"
    assert len(groups[0]["hooks"]) == 1
    assert "my-gate.py" in groups[0]["hooks"][0]["command"]


def test_add_duplicate_detection_searches_all_matcher_groups_with_exact_basename(tmp_path: Path) -> None:
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    settings = {
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "Bash",
                    "hooks": [{"type": "command", "command": 'python3 "$HOME/.claude/hooks/my-foo.py"', "timeout": 10}],
                },
                {
                    "matcher": "Write",
                    "hooks": [{"type": "command", "command": 'python3 "$HOME/.claude/hooks/bar.py"', "timeout": 10}],
                },
            ]
        }
    }
    (home / ".claude" / "settings.json").write_text(json.dumps(settings), encoding="utf-8")

    # bar.py is in the second matcher group -> must be detected as duplicate
    dup = _add(home, _guarded_hook(tmp_path, "bar.py"), "PreToolUse")
    assert dup.returncode == 0, dup.stderr
    assert "Already registered" in dup.stdout

    # foo.py is NOT a duplicate of my-foo.py (exact basename, not substring)
    ok = _add(home, _guarded_hook(tmp_path, "foo.py"), "PreToolUse", "--matcher", "Write")
    assert ok.returncode == 0, ok.stderr
    assert "Registered" in ok.stdout
    updated = json.loads((home / ".claude" / "settings.json").read_text(encoding="utf-8"))
    write_cmds = [h["command"] for h in updated["hooks"]["PreToolUse"][1]["hooks"]]
    assert len(write_cmds) == 2


def test_remove_searches_all_groups_and_respects_exact_basename_and_matcher(tmp_path: Path) -> None:
    home = tmp_path / "home"
    hooks_dir = home / ".claude" / "hooks"
    hooks_dir.mkdir(parents=True)
    for name in ("my-foo.py", "foo.py", "bar.py"):
        (hooks_dir / name).write_text("import sys\n", encoding="utf-8")
    settings = {
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "Bash",
                    "hooks": [{"type": "command", "command": 'python3 "$HOME/.claude/hooks/my-foo.py"', "timeout": 10}],
                },
                {
                    "matcher": "Write",
                    "hooks": [
                        {"type": "command", "command": 'python3 "$HOME/.claude/hooks/foo.py"', "timeout": 10},
                        {"type": "command", "command": 'python3 "$HOME/.claude/hooks/bar.py"', "timeout": 10},
                    ],
                },
            ]
        }
    }
    (home / ".claude" / "settings.json").write_text(json.dumps(settings), encoding="utf-8")

    # Removing foo.py without --matcher removes it from second group, leaves my-foo.py intact, keeps file
    res = _remove(home, "foo.py", "PreToolUse")
    assert res.returncode == 0, res.stderr
    updated = json.loads((home / ".claude" / "settings.json").read_text(encoding="utf-8"))
    assert len(updated["hooks"]["PreToolUse"][0]["hooks"]) == 1
    assert len(updated["hooks"]["PreToolUse"][1]["hooks"]) == 1
    assert (hooks_dir / "foo.py").exists()

    # Removing bar.py with wrong --matcher leaves it alone; with matching --matcher and --delete-file deletes it
    wrong = _remove(home, "bar.py", "PreToolUse", "--matcher", "Bash")
    assert wrong.returncode == 0
    assert "Not found" in wrong.stdout
    right = _remove(home, "bar.py", "PreToolUse", "--matcher", "Write", "--delete-file")
    assert right.returncode == 0, right.stderr
    assert not (hooks_dir / "bar.py").exists()


def test_remove_refuses_delete_file_when_still_referenced_elsewhere(tmp_path: Path) -> None:
    home = tmp_path / "home"
    hooks_dir = home / ".claude" / "hooks"
    hooks_dir.mkdir(parents=True)
    (hooks_dir / "shared.py").write_text("import sys\n", encoding="utf-8")
    settings = {
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "Bash",
                    "hooks": [{"type": "command", "command": 'python3 "$HOME/.claude/hooks/shared.py"', "timeout": 10}],
                }
            ],
            "PostToolUse": [
                {
                    "matcher": "Write",
                    "hooks": [{"type": "command", "command": 'python3 "$HOME/.claude/hooks/shared.py"', "timeout": 5}],
                }
            ],
        }
    }
    (home / ".claude" / "settings.json").write_text(json.dumps(settings), encoding="utf-8")

    res = _remove(home, "shared.py", "PreToolUse", "--delete-file")
    assert res.returncode == 1
    assert "still referenced" in res.stderr
    assert (hooks_dir / "shared.py").exists()
    # PreToolUse entry was unregistered while PostToolUse remains
    updated = json.loads((home / ".claude" / "settings.json").read_text(encoding="utf-8"))
    assert updated["hooks"]["PreToolUse"][0]["hooks"] == []
    assert len(updated["hooks"]["PostToolUse"][0]["hooks"]) == 1


@pytest.mark.parametrize("bad_name", ["", ".", "..", "../settings.json", "sub/hook.py", "sub\\hook.py", "a..b.py"])
def test_remove_rejects_path_traversal_names(tmp_path: Path, bad_name: str) -> None:
    home = _empty_home(tmp_path, "PreToolUse")
    res = _remove(home, bad_name, "PreToolUse", "--delete-file")
    assert res.returncode == 1
    assert "invalid hook name" in res.stderr
    assert (home / ".claude" / "settings.json").exists()


def test_remove_refuses_symlink_escaping_hooks_dir(tmp_path: Path) -> None:
    home = _empty_home(tmp_path, "PreToolUse")
    hooks_dir = home / ".claude" / "hooks"
    hooks_dir.mkdir(parents=True)
    outside = tmp_path / "outside.py"
    outside.write_text("keep me\n", encoding="utf-8")
    escape_link = hooks_dir / "escape.py"
    try:
        escape_link.symlink_to(outside)
    except OSError:
        pytest.skip("symlinks unavailable")
    res = _remove(home, "escape.py", "PreToolUse", "--delete-file")
    assert res.returncode == 1
    assert "resolves outside" in res.stderr
    assert outside.exists()


def test_validate_reports_missing_file_and_relative_path(tmp_path: Path) -> None:
    home = tmp_path / "home"
    (home / ".claude" / "hooks").mkdir(parents=True)
    settings = {
        "hooks": {
            "PostToolUse": [
                {
                    "matcher": "Write",
                    "hooks": [
                        {"type": "command", "command": 'python3 "$HOME/.claude/hooks/ghost.py"', "timeout": 5},
                        {"type": "command", "command": "python3 hooks/relative.py", "timeout": 5},
                    ],
                }
            ]
        }
    }
    (home / ".claude" / "settings.json").write_text(json.dumps(settings), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "validate"], capture_output=True, text=True, env=_env(home), timeout=60
    )
    assert result.returncode == 2
    assert "[FAIL] PostToolUse/ghost.py: file does not exist" in result.stdout
    assert "[FAIL] PostToolUse/relative.py: uses relative path" in result.stdout
