"""vexinstall honors the install.sh profile (.local/profile.yaml / $VEXJOY_INSTALL_PROFILE).

Disabled skills, agents, and hooks are not desired: never installed, removed
when previously owned, absent from the installed index. Every test runs for
all five targets. Hermetic: temp HOME, fixture repo, temp profile file.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from scripts.tests.vexinstall_support import (
    ADAPTERS,
    BULK_SKILLS,
    TARGETS,
    Env,
    adapters,
    bulk_world,
    expected_skill_names,
    profile,
    world,
)

effective_adapter = adapters.effective_adapter
EMPTY = profile.EMPTY
filter_settings_hooks = profile.filter_settings_hooks
load_profile = profile.load_profile
profile_path = profile.profile_path

__all__ = ["bulk_world", "world"]

MODES = ("symlink", "copy")
DISABLED_SKILLS = ("beta", "private-one", "voice-v1")
DISABLED_AGENT = "b-eng"
DISABLED_HOOK = "h1.py"  # in both fixture allowlists (codex, reasonix)


def _ok(res) -> None:
    assert res.code == 0, f"exit {res.code}\nout={res.out}\nerr={res.err}"


def _entries(path: Path) -> set[str]:
    return {p for p in os.listdir(path) if not p.startswith(".")} if path.is_dir() else set()


def _write_profile(path: Path, *, skills=DISABLED_SKILLS, agents=(DISABLED_AGENT,), hooks=(DISABLED_HOOK,)) -> Path:
    lines = ["disabled:"]
    for key, items in (("skills", skills), ("agents", agents), ("hooks", hooks)):
        lines.append(f"  {key}:")
        lines.extend(f"    - {i}" for i in items)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


@pytest.fixture
def profile_file(world: Env, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = world.work / "profile.yaml"
    monkeypatch.setenv("VEXJOY_INSTALL_PROFILE", str(path))
    return path


def _assert_filtered(env: Env, target: str) -> None:
    adapter = ADAPTERS[target]
    root = env.root(target)
    assert _entries(env.skills(target)) == expected_skill_names(target) - set(DISABLED_SKILLS)
    index = json.loads((root / "vexjoy" / "index" / "skills.json").read_text())
    assert not set(index["skills"]) & set(DISABLED_SKILLS)
    if adapter.agents:
        names = _entries(root / adapter.agents)
        assert f"{DISABLED_AGENT}.md" not in names
        assert "a-eng.md" in names
    hooks = root / "hooks"
    if adapter.hooks is None:
        assert not os.path.lexists(hooks)
    else:
        assert not os.path.islink(hooks), "a filtered hooks install is per-entry (install.sh install_component)"
        assert DISABLED_HOOK not in _entries(hooks)
    if adapter.hooks in ("whole", "per-entry"):
        assert {"h2.py", "h3.py", "lib"} <= _entries(hooks)
        assert _entries(hooks / "lib") == {"util.py", "more.py"}


@pytest.mark.parametrize("target", TARGETS)
@pytest.mark.parametrize("mode", MODES)
def test_fresh_apply_skips_disabled_items(world: Env, profile_file: Path, target: str, mode: str) -> None:
    _write_profile(profile_file)
    _ok(world.run("apply", "--target", target, "--mode", mode))
    _assert_filtered(world, target)
    again = world.run("apply", "--target", target, "--mode", mode)
    _ok(again)
    assert again.out[0].startswith(f"[apply] {target}: +0 ~0 -0,"), again.out[0]


@pytest.mark.parametrize("target", TARGETS)
def test_profile_added_then_cleared_round_trips(world: Env, profile_file: Path, target: str) -> None:
    _ok(world.run("apply", "--target", target))
    before = _entries(world.skills(target))
    _write_profile(profile_file)
    plan = world.run("plan", "--target", target, "--json")
    _ok(plan)
    actions = plan.data["targets"][target]["actions"]
    removed = {Path(a["dest"]).name for a in actions if a["op"] == "remove"}
    assert set(DISABLED_SKILLS) <= removed
    assert all(a["reason"] == "disabled by install profile" for a in actions if a["op"] == "remove")
    _ok(world.run("apply", "--target", target))
    _assert_filtered(world, target)

    profile_file.unlink()
    _ok(world.run("apply", "--target", target))
    assert _entries(world.skills(target)) == before
    if ADAPTERS[target].hooks == "whole":
        assert os.path.islink(world.root(target) / "hooks"), "cleared hook profile restores the whole-dir link"
    again = world.run("apply", "--target", target)
    _ok(again)
    assert again.out[0].startswith(f"[apply] {target}: +0 ~0 -0,"), again.out[0]


@pytest.mark.parametrize("target", TARGETS)
def test_profile_removals_are_exempt_from_mass_remove_cap(
    bulk_world: Env, monkeypatch: pytest.MonkeyPatch, target: str
) -> None:
    _ok(bulk_world.run("apply", "--target", target))
    path = _write_profile(bulk_world.work / "profile.yaml", skills=BULK_SKILLS, agents=(), hooks=())
    monkeypatch.setenv("VEXJOY_INSTALL_PROFILE", str(path))
    summary = bulk_world.run("plan", "--target", target, "--json").data["targets"][target]["summary"]
    assert summary["remove"] == len(BULK_SKILLS) and not summary["cap_tripped"], summary
    _ok(bulk_world.run("sync", "--target", target))
    assert not _entries(bulk_world.skills(target)) & set(BULK_SKILLS)


@pytest.mark.parametrize("target", TARGETS)
def test_absent_profile_changes_nothing(world: Env, profile_file: Path, target: str) -> None:
    assert not profile_file.exists()
    _ok(world.run("apply", "--target", target))
    assert _entries(world.skills(target)) == expected_skill_names(target)
    if ADAPTERS[target].hooks == "whole":
        assert os.path.islink(world.root(target) / "hooks")


def test_claude_settings_drop_disabled_hooks(world: Env, profile_file: Path) -> None:
    _write_profile(profile_file, skills=(), agents=())
    _ok(world.run("apply", "--target", "claude"))
    data = json.loads((world.home / ".claude" / "settings.json").read_text())
    commands = [e["command"] for groups in data["hooks"].values() for g in groups for e in g["hooks"]]
    assert not any(DISABLED_HOOK in c for c in commands), commands
    assert any("h2.py" in c for c in commands) and any("h3.py" in c for c in commands)


def test_profile_path_defaults_to_repo_local(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VEXJOY_INSTALL_PROFILE", raising=False)
    assert profile_path(tmp_path) == tmp_path / ".local" / "profile.yaml"
    monkeypatch.setenv("VEXJOY_INSTALL_PROFILE", str(tmp_path / "p.yaml"))
    assert profile_path(tmp_path) == tmp_path / "p.yaml"


@pytest.mark.parametrize(
    ("text", "active"),
    [("", False), ("disabled: [oops\n", False), ("disabled:\n  skills: notalist\n", False), (None, False)],
)
def test_bad_or_missing_profile_is_empty(tmp_path: Path, text: str | None, active: bool) -> None:
    path = tmp_path / "profile.yaml"
    if text is not None:
        path.write_text(text, encoding="utf-8")
    assert load_profile(path).active is active


def test_agent_stem_matching_and_hook_adapter(tmp_path: Path) -> None:
    prof = load_profile(_write_profile(tmp_path / "p.yaml"))
    assert prof.agent_disabled("b-eng.md") and prof.agent_disabled("b-eng")
    assert not prof.agent_disabled("a-eng.md")
    assert effective_adapter(ADAPTERS["claude"], prof).hooks == "per-entry"
    assert effective_adapter(ADAPTERS["claude"], EMPTY).hooks == "whole"
    assert effective_adapter(ADAPTERS["reasonix"], prof).hooks == "allowlist"


def test_filter_settings_hooks_drops_empty_groups(tmp_path: Path) -> None:
    prof = load_profile(_write_profile(tmp_path / "p.yaml"))
    hooks = {
        "SessionStart": [{"hooks": [{"command": 'python3 "$HOME/.claude/hooks/h1.py"'}]}],
        "Stop": [{"hooks": [{"command": "python3 ~/.claude/hooks/h3.py"}, {"command": "echo hi"}]}],
    }
    assert filter_settings_hooks(hooks, prof) == {
        "Stop": [{"hooks": [{"command": "python3 ~/.claude/hooks/h3.py"}, {"command": "echo hi"}]}]
    }
    assert filter_settings_hooks(hooks, EMPTY) is hooks
