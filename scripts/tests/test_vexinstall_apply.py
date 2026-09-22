"""vexinstall spec 16 matrix: idempotency, layout, shape, collisions, dangling, move, worktree,
missing overlay, uninstall. Every test runs for all five targets."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

from scripts.tests.vexinstall_support import (
    ADAPTERS,
    TARGETS,
    Env,
    bulk_world,
    commit_all,
    expected_skill_names,
    git,
    make_world,
    tree_hash,
    world,
    write_overlays,
)

MODES = ("symlink", "copy")
LOCK = (".claude/vexjoy/lock",)


def _ok(res) -> None:
    assert res.code == 0, f"exit {res.code}\nout={res.out}\nerr={res.err}"


def _summary(env: Env, target: str) -> dict:
    res = env.run("plan", "--target", target, "--json")
    return res.data["targets"][target]["summary"]


def _entries(path: Path) -> set[str]:
    return {p for p in os.listdir(path) if not p.startswith(".")} if path.is_dir() else set()


@pytest.mark.parametrize("target", TARGETS)
@pytest.mark.parametrize("mode", MODES)
def test_apply_is_idempotent(world: Env, target: str, mode: str) -> None:
    _ok(world.run("apply", "--target", target, "--mode", mode))
    s = _summary(world, target)
    assert (s["add"], s["replace"], s["remove"], s["blocked"]) == (0, 0, 0, 0), s
    second = world.run("apply", "--target", target, "--mode", mode)
    _ok(second)
    assert second.out[0].startswith(f"[apply] {target}: +0 ~0 -0,"), second.out[0]


@pytest.mark.parametrize("target", TARGETS)
@pytest.mark.parametrize("mode", MODES)
def test_layout_matches_adapter_table(world: Env, target: str, mode: str) -> None:
    _ok(world.run("apply", "--target", target, "--mode", mode))
    adapter = ADAPTERS[target]
    root = world.root(target)
    skills = world.skills(target)
    assert not skills.is_symlink()
    assert _entries(skills) == expected_skill_names(target)
    for category in ("meta", "process", "content", "old-thing"):
        assert not os.path.lexists(skills / category), f"category/promoted entry {category} installed"
    forced_copy = adapter.skills_mode == "copy"
    for name in ("alpha", "delta", "private-one", "voice-v1"):
        dest = skills / name
        if mode == "symlink" and not forced_copy:
            assert dest.is_symlink() and os.path.isabs(os.readlink(dest))
        else:
            assert dest.is_dir() and not dest.is_symlink()
        assert (dest / "SKILL.md").is_file() or (dest / "skill" / "SKILL.md").is_file()
    assert (skills / "delta" / "references" / "ref.md").is_file()
    if adapter.agents:
        agents = root / adapter.agents
        assert agents.is_dir() and not agents.is_symlink()
        assert _entries(agents) == {"a-eng.md", "b-eng.md", "c-eng.md", "a-eng", "p-agent.md"}
    if adapter.commands:
        assert _entries(root / adapter.commands) == {"cmd-one.md"}  # alpha.md shadowed by skill alpha
    hooks = root / "hooks"
    if adapter.hooks == "whole":
        assert hooks.is_symlink() if mode == "symlink" else (hooks.is_dir() and not hooks.is_symlink())
        assert (hooks / "h1.py").is_file()
    elif adapter.hooks == "per-entry":
        assert not hooks.is_symlink() and _entries(hooks) == {"h1.py", "h2.py", "h3.py", "lib"}
        assert _entries(hooks / "lib") == {"util.py", "more.py"}
    elif adapter.hooks == "allowlist":
        assert _entries(hooks) == {"h1.py", "lib"}
    else:
        assert not os.path.lexists(hooks)
    scripts = root / "scripts"
    if adapter.scripts == "whole":
        assert (scripts / "tool" / "x.py").is_file()
    else:
        assert not scripts.is_symlink()
        assert {"s1.py", "s2.py", "tool"} <= _entries(scripts)
    index = json.loads((root / "vexjoy" / "index" / "skills.json").read_text())
    assert set(index["skills"]) == {
        "alpha",
        "beta",
        "gamma",
        "delta",
        "epsilon",
        "zeta",
        "private-one",
        "private-two",
        "voice-v1",
    }


@pytest.mark.parametrize("target", TARGETS)
def test_copy_and_symlink_modes_have_same_shape(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target: str) -> None:
    a = make_world(tmp_path / "a", monkeypatch)
    b = make_world(tmp_path / "b", monkeypatch)
    _ok(a.run("apply", "--target", target, "--mode", "symlink"))
    _ok(b.run("apply", "--target", target, "--mode", "copy"))
    root_a, root_b = a.root(target), b.root(target)

    def shape(root: Path) -> set[str]:
        out = set()
        for container in ADAPTERS[target].containers(root.parent):
            if container.is_dir():
                out |= {f"{container.relative_to(root)}/{n}" for n in _entries(container)}
        return out

    assert shape(root_a) == shape(root_b)
    for name in ("alpha", "private-one"):
        assert (a.skills(target) / name / "SKILL.md").read_bytes() == (
            b.skills(target) / name / "SKILL.md"
        ).read_bytes()


def _add_clash(env: Env) -> Path:
    clash = env.work / "clash"
    (clash / "cat" / "alpha").mkdir(parents=True)
    (clash / "cat" / "alpha" / "SKILL.md").write_text("---\nname: alpha\ndescription: clash\n---\n")
    cfg = json.loads((env.home / ".claude" / "vexjoy" / "overlays.json").read_text())
    cfg["overlays"].append({"id": "clash", "root": str(clash), "layout": "category"})
    write_overlays(env.home, cfg)
    return clash


@pytest.mark.parametrize("target", TARGETS)
def test_collision_is_error_in_plan_and_apply(world: Env, target: str) -> None:
    clash = _add_clash(world)
    plan = world.run("plan", "--target", target)
    assert plan.code == 3
    msg = "\n".join(plan.err)
    assert str(world.repo / "skills" / "meta" / "alpha") in msg and str(clash / "cat" / "alpha") in msg
    before = tree_hash(world.home, exclude=LOCK)
    res = world.run("apply", "--target", target)
    assert res.code == 3
    assert tree_hash(world.home, exclude=LOCK) == before, "apply wrote despite a collision"


@pytest.mark.parametrize("target", TARGETS)
def test_collision_in_sync_keeps_dest_as_is(world: Env, target: str) -> None:
    _ok(world.run("apply", "--target", target))
    dest = world.skills(target) / "alpha"
    before = tree_hash(dest) if not dest.is_symlink() else os.readlink(dest)
    _add_clash(world)
    (world.repo / "skills" / "meta" / "eta").mkdir()
    (world.repo / "skills" / "meta" / "eta" / "SKILL.md").write_text("---\nname: eta\ndescription: eta\n---\n")
    commit_all(world.repo, "add eta")
    res = world.run("sync", "--target", target)
    assert res.code == 0
    assert any("collision" in line for line in res.err)
    after = tree_hash(dest) if not dest.is_symlink() else os.readlink(dest)
    assert after == before
    assert (world.skills(target) / "eta").exists(), "sync must still apply other entries"


@pytest.mark.parametrize("target", TARGETS)
def test_overrides_key_rejected(world: Env, target: str) -> None:
    cfg = json.loads((world.home / ".claude" / "vexjoy" / "overlays.json").read_text())
    cfg["overrides"] = {"alpha": "private"}
    write_overlays(world.home, cfg)
    for cmd in ("plan", "apply"):
        res = world.run(cmd, "--target", target)
        assert res.code == 2 and "overrides" in res.err[0]
    sync = world.run("sync", "--target", target)
    assert sync.code == 0 and "overrides" in sync.err[0]
    assert not world.root(target).exists() or target == "claude"


@pytest.mark.parametrize("target", TARGETS)
@pytest.mark.parametrize("mode", MODES)
def test_dangling_owned_pruned_unowned_kept(world: Env, target: str, mode: str) -> None:
    _ok(world.run("apply", "--target", target, "--mode", mode))
    git(world.repo, "rm", "-r", "-q", "skills/content/zeta")
    commit_all(world.repo, "drop zeta")
    ghost = world.skills(target) / "ghost"
    os.symlink(str(world.work / "nowhere"), ghost)
    res = world.run("sync", "--target", target)
    _ok(res)
    assert not os.path.lexists(world.skills(target) / "zeta")
    assert os.path.islink(ghost), "unowned dangling link must be left for prune --unowned"
    trash = world.home / ".claude" / "vexjoy" / "trash"
    moved = [p for p in trash.rglob("zeta") if "files" in p.parts]
    assert moved, "removal must land in trash"


@pytest.mark.parametrize("target", TARGETS)
@pytest.mark.parametrize("mode", MODES)
def test_repo_move_repoints_links(world: Env, target: str, mode: str) -> None:
    _ok(world.run("apply", "--target", target, "--mode", mode))
    old = world.repo
    new = world.work / "repo-moved"
    os.rename(old, new)
    world.repo = new
    _ok(world.run("sync", "--target", target, source=new))
    for dest in world.ledger_dests(target):
        p = Path(dest)
        assert os.path.exists(p), f"dangling after move: {p}"
        if os.path.islink(p):
            assert not os.readlink(p).startswith(str(old) + os.sep)
    led = world.ledger()
    assert led["source_root"] == str(new)
    assert all(not e["source"].startswith(str(old) + os.sep) for e in led["entries"])


@pytest.mark.parametrize("target", TARGETS)
@pytest.mark.parametrize("mode", MODES)
def test_worktree_sync_makes_no_changes(world: Env, target: str, mode: str) -> None:
    _ok(world.run("apply", "--target", target, "--mode", mode))
    wt = world.work / "wt"
    git(world.repo, "worktree", "add", "-q", "-b", "wt-branch", str(wt))
    try:
        before = tree_hash(world.home)
        res = world.run("sync", "--target", target, source=wt)
        assert res.code == 0 and any("skipped" in line for line in res.out)
        assert tree_hash(world.home) == before
        assert world.run("apply", "--target", target, source=wt).code == 6
    finally:
        git(world.repo, "worktree", "remove", "--force", str(wt))
        git(world.repo, "branch", "-q", "-D", "wt-branch")


@pytest.mark.parametrize("target", TARGETS)
def test_ephemeral_source_refused_in_symlink_mode(world: Env, target: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VEXINSTALL_EPHEMERAL_PREFIXES", str(world.work))
    assert world.run("apply", "--target", target, "--mode", "symlink").code == 6
    assert not (world.home / ".claude" / "vexjoy" / "ledger.json").exists()
    sync = world.run("sync", "--target", target, "--mode", "symlink")
    assert sync.code == 0 and "skipped" in sync.out[0]
    _ok(world.run("apply", "--target", target, "--mode", "symlink", "--adopt-source"))


@pytest.mark.parametrize("target", TARGETS)
@pytest.mark.parametrize("mode", MODES)
def test_missing_overlay_root_keeps_entries_stale(world: Env, target: str, mode: str) -> None:
    _ok(world.run("apply", "--target", target, "--mode", mode))
    os.rename(world.priv, world.work / "private-skills.unmounted")
    res = world.run("sync", "--target", target)
    _ok(res)
    led = {e["dest"]: e for e in world.ledger()["entries"]}
    for name in ("private-one", "voice-v1"):
        dest = str(world.skills(target) / name)
        assert dest in led and led[dest]["status"] == "stale-source"
        assert os.path.lexists(dest)
    doctor = world.run("doctor", "--target", target)
    assert any("stale-source" in line for line in doctor.out)


@pytest.mark.parametrize("target", TARGETS)
@pytest.mark.parametrize("mode", MODES)
def test_uninstall_removes_owned_leaves_unowned(world: Env, target: str, mode: str) -> None:
    root = world.root(target)
    user = world.skills(target) / "user-skill"
    user.mkdir(parents=True)
    (user / "SKILL.md").write_text("---\nname: user-skill\ndescription: mine\n---\n")
    _ok(world.run("apply", "--target", target, "--mode", mode))
    owned = world.ledger_dests(target)
    assert owned
    _ok(world.run("uninstall", "--target", target))
    for dest in owned:
        assert not os.path.lexists(dest), dest
    assert (user / "SKILL.md").is_file()
    assert world.ledger_dests(target) == set()
    assert root.is_dir()


@pytest.mark.parametrize("target", TARGETS)
def test_report_and_summary_line(world: Env, target: str) -> None:
    res = world.run("sync", "--target", target)
    _ok(res)
    line = res.out[0]
    assert line.startswith(f"[sync] {target}: +"), line
    assert " skills, 0 collisions" in line
    reports = sorted((world.home / ".claude" / "vexjoy" / "reports").glob("*.json"))
    data = json.loads(reports[-1].read_text())
    assert data["command"] == "sync" and data["source_root"] == str(world.repo)
    assert set(data["diff"][target]) >= {"added", "replaced", "removed", "skipped", "collisions"}


@pytest.mark.parametrize("target", TARGETS)
def test_index_only_writes_runtime_dir_only(world: Env, target: str) -> None:
    _ok(world.run("apply", "--target", target))
    idx = world.root(target) / "vexjoy" / "index" / "skills.json"
    idx.unlink()
    before = tree_hash(world.repo, exclude=(".git",))
    _ok(world.run("sync", "--target", target, "--index-only"))
    assert idx.is_file()
    assert tree_hash(world.repo, exclude=(".git",)) == before
    assert not (world.repo / "skills" / "INDEX.local.json").exists()


def test_all_targets_resolve_to_present_runtimes(world: Env) -> None:
    (world.home / ".hermes").mkdir()
    res = world.run("apply", "--target", "all")
    _ok(res)
    assert "claude:" in res.out[0] and "hermes:" in res.out[0] and "codex:" not in res.out[0]


def test_data_dirs_are_never_touched(world: Env) -> None:
    data = world.skills("claude") / "reddit-data" / "sap"
    data.mkdir(parents=True)
    (data / "log.txt").write_text("x")
    _ok(world.run("apply", "--target", "claude"))
    _ok(world.run("uninstall", "--target", "claude"))
    assert (data / "log.txt").read_text() == "x"


def test_source_root_change_needs_adopt_source(world: Env) -> None:
    _ok(world.run("apply", "--target", "claude"))
    clone = world.work / "clone"
    shutil.copytree(world.repo, clone, symlinks=True)
    assert world.run("apply", "--target", "claude", source=clone).code == 6
    _ok(world.run("apply", "--target", "claude", "--adopt-source", source=clone))
    assert os.readlink(world.skills("claude") / "alpha").startswith(str(clone))
