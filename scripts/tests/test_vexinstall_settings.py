"""vexinstall settings.json merge (spec 10): owned rule, merge, dedupe, backups, restore."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from scripts.tests.vexinstall_support import TARGETS, Env, world
from scripts.tests.vexinstall_support import settings_mod as sm


def _rule(tmp_path: Path) -> sm.OwnerRule:
    repo = tmp_path / "repo"
    (repo / "hooks").mkdir(parents=True)
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    os.symlink(repo / "hooks", home / ".claude" / "hooks")
    return sm.OwnerRule(home=home, hooks_dir=home / ".claude" / "hooks", source_root=repo)


def _cmd(c: str) -> dict:
    return {"type": "command", "command": c}


@pytest.mark.parametrize(
    ("command", "owned"),
    [
        ('python3 "$HOME/.claude/hooks/a.py"', True),
        ("python3 ${HOME}/.claude/hooks/a.py --flag", True),
        ("python3 ~/.claude/hooks/lib/x.py", True),
        ("python3 /home/someone/vexjoy-agent/hooks/old.py", True),
        ("python3 /opt/user/hooks/mine.py", False),
        ("echo hi", False),
        ("python3 ${CLAUDE_PLUGIN_ROOT}/hooks/p.py", False),
    ],
)
def test_owner_rule(tmp_path: Path, command: str, owned: bool) -> None:
    assert _rule(tmp_path).owns(_cmd(command)) is owned


def test_owner_rule_realpath_through_hooks_symlink(tmp_path: Path) -> None:
    rule = _rule(tmp_path)
    direct = str(rule.source_root / "hooks" / "a.py")
    assert rule.owns(_cmd(f"python3 {direct}"))


def test_merge_preserves_user_entries_and_collapses_owned(tmp_path: Path) -> None:
    rule = _rule(tmp_path)
    sync = _cmd('python3 "$HOME/.claude/hooks/sync.py"')
    user = _cmd("python3 /opt/user/hook.py")
    current = {
        "theme": "dark",
        "hooks": {
            "SessionStart": [
                {"hooks": [sync, user]},
                {"matcher": "resume", "hooks": [sync]},
                {"hooks": [sync]},
                {"matcher": "startup", "hooks": [_cmd("python3 /old/vexjoy-agent/hooks/gone.py")]},
            ],
            "Notification": [{"hooks": [_cmd("notify-send hi")]}],
        },
    }
    desired = {"SessionStart": [{"hooks": [sync, _cmd('python3 "$HOME/.claude/hooks/new.py"')]}]}
    res = sm.merge(current, desired, rule)
    hooks = res.settings["hooks"]
    flat = [(g.get("matcher"), e["command"]) for g in hooks["SessionStart"] for e in g["hooks"]]
    assert flat.count((None, sync["command"])) == 1
    assert (None, user["command"]) in flat
    assert all("gone.py" not in c for _, c in flat)
    assert ("resume", sync["command"]) not in flat
    assert (None, 'python3 "$HOME/.claude/hooks/new.py"') in flat
    assert hooks["Notification"] == current["hooks"]["Notification"]
    assert res.settings["theme"] == "dark"
    assert res.deduped and res.removed and res.added
    assert sm.duplicate_owned(res.settings, rule) == []
    again = sm.merge(res.settings, desired, rule)
    assert not again.changed


@pytest.mark.parametrize("target", TARGETS)
def test_apply_settings_merge_per_target(world: Env, target: str) -> None:
    spath = world.home / ".claude" / "settings.json"
    user = {"type": "command", "command": "python3 /opt/user/hook.py"}
    owned = {"type": "command", "command": 'python3 "$HOME/.claude/hooks/h1.py"', "timeout": 20000}
    original = {
        "theme": "dark",
        "hooks": {
            "SessionStart": [
                {"hooks": [owned, user]},
                {"matcher": "resume", "hooks": [owned]},
                {"hooks": [owned]},
            ],
            "PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "mine.sh"}]}],
        },
    }
    spath.write_text(json.dumps(original, indent=2))
    before = spath.read_bytes()
    res = world.run("apply", "--target", target)
    assert res.code == 0, res.err
    if target != "claude":
        assert spath.read_bytes() == before, "non-claude targets must not touch ~/.claude/settings.json"
        return
    merged = json.loads(spath.read_text())
    assert merged["theme"] == "dark"
    assert merged["hooks"]["PreToolUse"] == original["hooks"]["PreToolUse"]
    ss = [e["command"] for g in merged["hooks"]["SessionStart"] for e in g["hooks"]]
    assert ss.count(owned["command"]) == 1
    assert user["command"] in ss
    assert any("h3.py" in e["command"] for g in merged["hooks"]["Stop"] for e in g["hooks"])
    assert oct(spath.stat().st_mode & 0o777) == "0o600"
    backups = sorted((world.home / ".claude" / "vexjoy" / "backups").glob("settings.*.json"))
    assert len(backups) == 1 and backups[0].read_bytes() == before
    assert world.ledger()["settings"]["claude"]
    doctor = world.run("doctor", "--target", "claude")
    assert not any("settings-" in line for line in doctor.out), doctor.out
    ts = backups[0].name[len("settings.") : -len(".json")]
    assert world.run("restore-settings", ts).code == 0
    assert spath.read_bytes() == before


def test_settings_backups_keep_ten(world: Env) -> None:
    spath = world.home / ".claude" / "settings.json"
    for i in range(13):
        spath.write_text(json.dumps({"n": i, "hooks": {}}))
        assert world.run("apply", "--target", "claude").code == 0
    backups = list((world.home / ".claude" / "vexjoy" / "backups").glob("settings.*.json"))
    assert len(backups) == 10


def test_doctor_reports_settings_drift_and_duplicates(world: Env) -> None:
    assert world.run("apply", "--target", "claude").code == 0
    spath = world.home / ".claude" / "settings.json"
    data = json.loads(spath.read_text())
    extra = {"type": "command", "command": 'python3 "$HOME/.claude/hooks/h3.py"'}
    data["hooks"]["SessionStart"].append({"hooks": [extra]})
    data["hooks"]["SessionStart"].append({"hooks": [extra]})
    spath.write_text(json.dumps(data))
    out = "\n".join(world.run("doctor", "--target", "claude").out)
    assert "settings-drift" in out and "settings-duplicate-owned" in out
