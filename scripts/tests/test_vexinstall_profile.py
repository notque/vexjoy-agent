"""vexinstall honors the install.sh profile (.local/profile.yaml / $VEXJOY_INSTALL_PROFILE).

Disabled skills, agents, and hooks are not desired: never installed, removed
when previously owned, absent from the installed index. Fresh apply runs for
all five targets; the rest run on targets with a distinct adapter branch.
Hermetic: temp HOME, fixture repo, temp profile file.
"""

from __future__ import annotations

import functools
import json
import os
import tempfile
import types
from pathlib import Path

import pytest

from scripts.tests.vexinstall_support import (
    ADAPTERS,
    BULK_SKILLS,
    TARGETS,
    Env,
    adapters,
    bulk_world,
    commit_all,
    expected_skill_names,
    fsops,
    plan,
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
ENABLED_HOOKS = {"h2.py", "h3.py", "lib"}  # ~/.claude/hooks while DISABLED_HOOK is disabled
WHOLE_HOOKS = {"h1.py", "h2.py", "h3.py", "lib", "tests"}  # the whole-dir copy of repo hooks/
NEW_H2 = "# hook h2.py v2\n"


def _ok(res) -> None:
    assert res.code == 0, f"exit {res.code}\nout={res.out}\nerr={res.err}"


@functools.cache
def _can_symlink() -> bool:
    with tempfile.TemporaryDirectory() as tmp:
        try:
            os.symlink(tmp, os.path.join(tmp, "probe"))
        except (OSError, NotImplementedError):
            return False
    return True


@pytest.fixture(params=MODES)
def mode(request: pytest.FixtureRequest) -> str:
    """Install mode; symlink mode skips on a host that refuses links (Windows without Developer Mode)."""
    if request.param == "symlink" and not _can_symlink():
        pytest.skip("host cannot create symlinks")
    return request.param


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


@pytest.mark.parametrize(("target", "mode"), [*((t, "symlink") for t in TARGETS), ("claude", "copy")])
def test_fresh_apply_skips_disabled_items(world: Env, profile_file: Path, target: str, mode: str) -> None:
    _write_profile(profile_file)
    _ok(world.run("apply", "--target", target, "--mode", mode))
    _assert_filtered(world, target)
    again = world.run("apply", "--target", target, "--mode", mode)
    _ok(again)
    assert again.out[0].startswith(f"[apply] {target}: +0 ~0 -0,"), again.out[0]


@pytest.mark.parametrize("target", ["claude", "reasonix"])
def test_profile_added_then_cleared_round_trips(world: Env, profile_file: Path, target: str, mode: str) -> None:
    _ok(world.run("apply", "--target", target, "--mode", mode))
    before = _entries(world.skills(target))
    _write_profile(profile_file)
    res = world.run("plan", "--target", target, "--json")
    _ok(res)
    actions = res.data["targets"][target]["actions"]
    removed = {Path(a["dest"]).name for a in actions if a["op"] == "remove"}
    assert set(DISABLED_SKILLS) <= removed
    hooks = world.root(target) / "hooks"
    for a in actions:
        if a["op"] == "remove" and a["reason"] != plan.PROFILE_REASON:
            # A whole-dir hooks copy turned per-entry drops what that layout skips (hooks/tests).
            assert (a["reason"], Path(a["dest"]).parent) == (plan.LEFTOVER_REASON, hooks), a
    _ok(world.run("apply", "--target", target))
    _assert_filtered(world, target)

    profile_file.unlink()
    _ok(world.run("apply", "--target", target))
    assert _entries(world.skills(target)) == before
    if ADAPTERS[target].hooks == "whole":
        assert os.path.islink(hooks) == (mode == "symlink"), "cleared hook profile restores the whole-dir entry"
        assert _entries(hooks) == WHOLE_HOOKS
    again = world.run("apply", "--target", target)
    _ok(again)
    assert again.out[0].startswith(f"[apply] {target}: +0 ~0 -0,"), again.out[0]


# ---------------------------------------------------------------- whole-dir hooks <-> per-entry hooks


def _hook_profile(path: Path) -> Path:
    """A profile that disables only DISABLED_HOOK, which turns claude hooks per-entry."""
    return _write_profile(path, skills=(), agents=())


def _hook_actions(env: Env) -> list[dict]:
    hooks = env.root("claude") / "hooks"
    res = env.run("plan", "--target", "claude", "--json")
    _ok(res)
    return [a for a in res.data["targets"]["claude"]["actions"] if Path(a["dest"]).is_relative_to(hooks)]


def _hook_records(env: Env) -> set[str]:
    hooks = env.root("claude") / "hooks"
    return {d for d in env.ledger_dests("claude") if Path(d).is_relative_to(hooks)}


def _trashed(env: Env) -> set[str]:
    """Original path of every entry this world moved to trash."""
    trash = env.home / ".claude" / "vexjoy" / "trash"
    return {
        item["original"]
        for manifest in trash.glob("*/manifest.json")
        for item in json.loads(manifest.read_text(encoding="utf-8"))["items"]
    }


def _ids(hooks: Path) -> dict[str, int]:
    return {name: os.stat(hooks / name).st_ino for name in ("h2.py", "h3.py", "lib/util.py")}


def _assert_clean_rerun(env: Env) -> None:
    again = env.run("sync", "--target", "claude")
    _ok(again)
    assert again.out[0].startswith("[sync] claude: +0 ~0 -0,"), again.out[0]


def test_a_hook_profile_keeps_every_enabled_hook_installed(world: Env, profile_file: Path, mode: str) -> None:
    """Before, copy mode planned a remove for the whole-dir hooks record beside an adopt for each
    of its files. Removals run first, so the sync trashed ~/.claude/hooks, the SessionStart sync
    hook that could repair it included, and still exited 0."""
    _ok(world.run("apply", "--target", "claude", "--mode", mode))
    hooks = world.root("claude") / "hooks"
    before = _ids(hooks) if mode == "copy" else {}
    _hook_profile(profile_file)
    actions = _hook_actions(world)
    assert not [a for a in actions if a["dest"] == str(hooks) and a["op"] == "remove"], actions
    forget = next(a for a in actions if a["dest"] == str(hooks) and a["op"] == "forget")
    assert forget["reason"] == plan.SPLIT_REASON

    _ok(world.run("sync", "--target", "claude"))
    assert hooks.is_dir() and not hooks.is_symlink()
    assert _entries(hooks) == ENABLED_HOOKS and _entries(hooks / "lib") == {"util.py", "more.py"}
    assert _hook_records(world) == {str(hooks / n) for n in ("h2.py", "h3.py", "lib/util.py", "lib/more.py")}
    if mode == "copy":
        # The enabled files never moved; only what the per-entry layout skips went to trash.
        assert _ids(hooks) == before
        assert _trashed(world) == {str(hooks / DISABLED_HOOK), str(hooks / "tests")}
    else:
        assert (hooks / "h2.py").is_symlink() and _trashed(world) == {str(hooks)}
    _assert_clean_rerun(world)


def test_clearing_the_hook_profile_folds_the_hooks_back_into_one_entry(
    world: Env, profile_file: Path, mode: str
) -> None:
    _hook_profile(profile_file)
    _ok(world.run("apply", "--target", "claude", "--mode", mode))
    hooks = world.root("claude") / "hooks"
    per_entry = _hook_records(world)
    profile_file.unlink()
    actions = _hook_actions(world)
    assert {a["dest"] for a in actions if a["op"] == "remove"} == per_entry
    assert all(a["reason"] == plan.COLLAPSE_REASON for a in actions if a["op"] == "remove")
    [whole] = [a for a in actions if a["dest"] == str(hooks)]
    assert whole["op"] == "replace" and whole["adopt"], whole

    _ok(world.run("sync", "--target", "claude"))
    assert os.path.islink(hooks) == (mode == "symlink") and _entries(hooks) == WHOLE_HOOKS
    assert _hook_records(world) == {str(hooks)}
    # The per-entry files left inside the old dir in one move, not one by one ahead of it.
    assert _trashed(world) == {str(hooks)}
    _assert_clean_rerun(world)


def test_a_hook_changed_in_the_repo_is_updated_by_either_switch(world: Env, profile_file: Path, mode: str) -> None:
    """Before, a per-entry copy older than its source (a pull and a profile change in one sync)
    made the whole-dir entry unadoptable: the sync blocked it, still trashed every per-entry hook,
    and left ~/.claude/hooks empty and blocked from then on."""
    _ok(world.run("apply", "--target", "claude", "--mode", mode))
    hooks = world.root("claude") / "hooks"
    (world.repo / "hooks" / "h2.py").write_text(NEW_H2, encoding="utf-8")
    commit_all(world.repo, "h2 v2")
    _hook_profile(profile_file)
    _ok(world.run("sync", "--target", "claude"))
    assert _entries(hooks) == ENABLED_HOOKS and (hooks / "h2.py").read_text() == NEW_H2

    (world.repo / "hooks" / "h3.py").write_text("# hook h3.py v2\n", encoding="utf-8")
    commit_all(world.repo, "h3 v2")
    profile_file.unlink()
    _ok(world.run("sync", "--target", "claude"))
    assert _entries(hooks) == WHOLE_HOOKS and (hooks / "h3.py").read_text() == "# hook h3.py v2\n"
    assert _hook_records(world) == {str(hooks)}
    _assert_clean_rerun(world)


def test_a_user_edit_keeps_the_hooks_per_entry(world: Env, profile_file: Path) -> None:
    """Before, the fold skipped the edited hook, trashed the rest, and blocked the whole-dir entry."""
    _hook_profile(profile_file)
    _ok(world.run("apply", "--target", "claude", "--mode", "copy"))
    hooks = world.root("claude") / "hooks"
    (hooks / "h2.py").write_text("# my h2\n", encoding="utf-8")
    records = _hook_records(world)
    profile_file.unlink()
    [whole] = _hook_actions(world)
    assert (whole["op"], whole["reason"]) == ("skip", "user-edited copy h2.py inside; not replaced")

    _ok(world.run("sync", "--target", "claude"))
    _ok(world.run("apply", "--target", "claude", "--takeover"))
    assert _entries(hooks) == ENABLED_HOOKS and (hooks / "h2.py").read_text() == "# my h2\n"
    assert _hook_records(world) == records and _trashed(world) == set()


def test_an_unowned_file_blocks_the_fold_until_takeover(world: Env, profile_file: Path, mode: str) -> None:
    _hook_profile(profile_file)
    _ok(world.run("apply", "--target", "claude", "--mode", mode))
    hooks = world.root("claude") / "hooks"
    (hooks / "mine.py").write_text("# mine\n", encoding="utf-8")
    records = _hook_records(world)
    profile_file.unlink()
    [whole] = _hook_actions(world)
    assert (whole["op"], whole["reason"]) == ("blocked", "unowned file mine.py inside")

    _ok(world.run("sync", "--target", "claude"))
    assert _entries(hooks) == ENABLED_HOOKS | {"mine.py"} and _hook_records(world) == records

    _ok(world.run("apply", "--target", "claude", "--takeover"))
    assert _entries(hooks) == WHOLE_HOOKS and _hook_records(world) == {str(hooks)}
    assert _trashed(world) == {str(hooks)}


def test_a_user_edited_whole_dir_copy_stays_as_it_is(world: Env, profile_file: Path) -> None:
    """The engine stops updating a copy the user edited, so the split leaves it alone, takeover included."""
    _ok(world.run("apply", "--target", "claude", "--mode", "copy"))
    hooks = world.root("claude") / "hooks"
    (hooks / "h2.py").write_text("# my h2\n", encoding="utf-8")
    _hook_profile(profile_file)
    actions = _hook_actions(world)
    assert {(Path(a["dest"]).name, a["op"]) for a in actions} == {
        ("hooks", "skip"),
        *((n, "skip") for n in ("h2.py", "h3.py", "util.py", "more.py")),
    }, actions

    _ok(world.run("sync", "--target", "claude"))
    _ok(world.run("apply", "--target", "claude", "--takeover"))
    assert _entries(hooks) == WHOLE_HOOKS and (hooks / "h2.py").read_text() == "# my h2\n"
    assert _hook_records(world) == {str(hooks)} and _trashed(world) == set()


def test_a_fold_that_cannot_place_the_dir_leaves_every_hook_installed(
    world: Env, profile_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Windows keeps ~/.claude/hooks busy while a hook runs in it. The per-entry files and their
    records stay until the whole-dir entry is placed, so a failed move costs nothing."""
    _hook_profile(profile_file)
    _ok(world.run("apply", "--target", "claude", "--mode", "copy"))
    hooks = world.root("claude") / "hooks"
    records = _hook_records(world)
    profile_file.unlink()
    real_rename = os.rename

    def busy(src: object, dst: object) -> None:
        if os.fspath(src) == str(hooks):
            raise type("WinError", (OSError,), {"winerror": 5})(13, "winerror 5")
        real_rename(src, dst)

    monkeypatch.setattr(fsops, "time", types.SimpleNamespace(sleep=lambda _s: None))
    monkeypatch.setattr(os, "rename", busy)
    res = world.run("sync", "--target", "claude")
    _ok(res)
    assert any(f"{hooks} not updated" in line for line in res.err), res.err
    assert _entries(hooks) == ENABLED_HOOKS and _hook_records(world) == records

    monkeypatch.setattr(os, "rename", real_rename)
    _ok(world.run("sync", "--target", "claude"))
    assert _entries(hooks) == WHOLE_HOOKS and _hook_records(world) == {str(hooks)}


@pytest.mark.parametrize("target", ["claude"])
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


@pytest.mark.parametrize("target", ["claude"])
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
