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
